from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
from datetime import datetime
from utils.igdb_updater import update_igdb
import subprocess

app = Flask(__name__, template_folder="templates_json/")
app.config["JSON_SORT_KEYS"] = False

DATA_DIR = "mnt/xbox/gp_new"
SEARCH_INDEX_FILE = os.path.join(DATA_DIR, "_search_index.json")

TIER_NAMES = [
    "Essential",
    "Ultimate",
    "Console",
    "PC",
    "Premium",
    "Ubisoft+ Premium",
    "Ubisoft+ Classics",
    "Ubisoft+ Classics PC",
    "EA Play",
]


def build_search_index():
    """Build or rebuild the search index from all JSON files"""
    index = {}
    if not os.path.exists(DATA_DIR):
        return index

    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json") and filename != "_search_index.json":
            pid = filename[:-5]
            filepath = os.path.join(DATA_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    title = data.get("basic_info", {}).get("title", "")
                    store_title = data.get("basic_info", {}).get("store_title", "")
                    index[pid] = {"title": title, "store_title": store_title}
            except Exception as e:
                print(f"Error reading {filename}: {e}")

    # Save index to file
    with open(SEARCH_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    return index


def load_search_index():
    """Load the search index from file, or build it if it doesn't exist"""
    if os.path.exists(SEARCH_INDEX_FILE):
        with open(SEARCH_INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return build_search_index()


def load_game_data(pid):
    """Load game data from JSON file"""
    filepath = os.path.join(DATA_DIR, f"{pid}.json")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_game_data(pid, data):
    """Save game data to JSON file"""
    filepath = os.path.join(DATA_DIR, f"{pid}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Update search index
    index = load_search_index()
    index[pid] = {
        "title": data.get("basic_info", {}).get("title", ""),
        "store_title": data.get("basic_info", {}).get("store_title", ""),
    }
    with open(SEARCH_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


@app.route("/")
def index():
    """Main view with PID input"""
    return render_template("index.html")


@app.route("/api/search")
def search():
    """Search for games by title"""
    query = request.args.get("q", "").lower().strip()
    if not query:
        return jsonify([])

    index = load_search_index()
    results = []

    for pid, info in index.items():
        title = info.get("title", "").lower()
        store_title = info.get("store_title", "").lower()

        if query in title or query in store_title:
            results.append(
                {
                    "pid": pid,
                    "title": info.get("title", ""),
                    "store_title": info.get("store_title", ""),
                }
            )

    # Sort by relevance (exact match first, then starts with, then contains)
    def sort_key(item):
        title = item["title"].lower()
        if title == query:
            return 0
        elif title.startswith(query):
            return 1
        else:
            return 2

    results.sort(key=sort_key)
    return jsonify(results[:50])  # Limit to 50 results


@app.route("/api/rebuild_index", methods=["POST"])
def rebuild_index():
    """Rebuild the search index"""
    try:
        build_search_index()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def get_all_pids():
    """Get all PIDs from the data directory"""
    if not os.path.exists(DATA_DIR):
        return []
    files = [
        f[:-5]
        for f in os.listdir(DATA_DIR)
        if f.endswith(".json") and f != "_search_index.json"
    ]
    return sorted(files)


def get_adjacent_pids(current_pid):
    """Get previous and next PIDs"""
    all_pids = get_all_pids()
    if not all_pids or current_pid not in all_pids:
        return None, None

    current_index = all_pids.index(current_pid)
    prev_pid = all_pids[current_index - 1] if current_index > 0 else None
    next_pid = (
        all_pids[current_index + 1] if current_index < len(all_pids) - 1 else None
    )

    return prev_pid, next_pid


@app.route("/edit/<pid>")
def edit(pid):
    """Edit view for a specific game"""
    data = load_game_data(pid)
    if not data:
        return f"Game with PID {pid} not found", 404

    prev_pid, next_pid = get_adjacent_pids(pid)

    return render_template(
        "edit.html",
        pid=pid,
        data=data,
        tier_names=TIER_NAMES,
        prev_pid=prev_pid,
        next_pid=next_pid,
    )


@app.route("/api/save/<pid>", methods=["POST"])
def save(pid):
    """Save changes to the game data"""
    try:
        data = load_game_data(pid)
        if not data:
            return jsonify({"success": False, "error": "Game not found"}), 404

        updates = request.json
        tab = updates.get("tab")

        if tab == "basic_info":
            # Update editable fields
            basic_info = data["basic_info"]

            # Fields that propagate to related SKUs
            propagate_fields = [
                "base_id",
                "title",
                "original_release_date",
            ]
            propagate_data = {}

            for field in propagate_fields:
                if field in updates:
                    basic_info[field] = updates[field]
                    propagate_data[field] = updates[field]

            # Fields that don't propagate
            if "release_date" in updates:
                basic_info["release_date"] = updates["release_date"]

            if "platforms" in updates:
                basic_info["platforms"] = updates["platforms"]
            if "specific_id" in updates:
                basic_info["specific_id"] = updates["specific_id"]

            # Save main file
            data["basic_info"] = basic_info
            save_game_data(pid, data)

            # Propagate changes to related SKUs
            if propagate_data and "related_skus" in basic_info:
                for sku in basic_info["related_skus"]:
                    if sku != pid:  # Don't re-save the current file
                        sku_data = load_game_data(sku)
                        if sku_data:
                            for field, value in propagate_data.items():
                                sku_data["basic_info"][field] = value
                            save_game_data(sku, sku_data)

        elif tab == "availabilities":
            # Update availabilities
            data["availabilities"] = updates.get("availabilities", [])
            save_game_data(pid, data)

        elif tab == "flags":
            # Update flags
            for flag, value in updates.get("flags", {}).items():
                data["flags"][flag] = value
            save_game_data(pid, data)

        elif tab == "igdb":
            # Update IGDB data
            igdb_id = updates.get("igdb_id")
            is_main = updates.get("is_main", True)

            if igdb_id:
                # Call the IGDB updater
                success = update_igdb(pid, igdb_id, is_main)
                if not success:
                    return (
                        jsonify(
                            {"success": False, "error": "Failed to update IGDB data"}
                        ),
                        500,
                    )

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/open_in_vscode/<pid>", methods=["POST"])
def open_in_vscode(pid):
    filepath = os.path.join(DATA_DIR, f"{pid}.json")
    if os.path.exists(filepath):
        try:
            subprocess.Popen(["code", filepath], shell=True)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    else:
        return jsonify({"success": False, "error": "File not found"})


if __name__ == "__main__":
    # Create data directory if it doesn't exist
    os.makedirs(DATA_DIR, exist_ok=True)
    # Build search index on startup
    if not os.path.exists(SEARCH_INDEX_FILE):
        print("Building search index...")
        build_search_index()
        print("Search index built!")
    app.run(debug=True)
