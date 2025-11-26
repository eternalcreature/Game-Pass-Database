""" "Flask app for adding and editing entries in the SQL DB"""

from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime, date
from sqlalchemy import or_
from models import GameData, get_session, connection_params, create_engine

app = Flask(__name__, template_folder="templates_sql/")
app.secret_key = "supersecret"  # change in production
session = get_session(connection_params)


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_int(s):
    try:
        return int(s) if s not in (None, "") else None
    except ValueError:
        return None


@app.route("/", methods=["GET", "POST"])
def search():
    if request.method == "POST":
        term = request.form["term"].strip()
        q = session.query(GameData)
        conditions = [GameData.game.ilike(f"%{term}%")]
        if term.isdigit():
            conditions.append(GameData.id == int(term))
        # add pid matches
        for pid_attr in ("pid1", "pid2", "pid3", "pid4", "pid5"):
            conditions.append(getattr(GameData, pid_attr) == term)

        result = q.filter(or_(*conditions)).first()
        if result:
            return redirect(url_for("edit", game_id=result.id))
        else:
            flash("No matching entry found.", "warning")

    return render_template("search.html")


@app.route("/edit/<int:game_id>", methods=["GET", "POST"])
def edit(game_id):
    game = session.get(GameData, game_id)  # SQLAlchemy 1.4+ recommended way
    if not game:
        flash("Game not found", "danger")
        return redirect(url_for("search"))

    if request.method == "POST":
        # basic fields
        game.game = request.form["game"]
        game.announced = parse_date(request.form.get("announced"))
        game.added = parse_date(request.form.get("added"))
        game.removed = parse_date(request.form.get("removed"))
        game.release = parse_date(request.form.get("release"))

        # pids
        for i in range(1, 6):
            v = request.form.get(f"pid{i}")
            setattr(game, f"pid{i}", v.strip() if v and v.strip() else None)

        # booleans
        game.indie = bool(request.form.get("indie"))
        game.f2p = bool(request.form.get("f2p"))
        game.first_party = bool(request.form.get("first_party"))

        # numeric ids
        game.igdb = parse_int(request.form.get("igdb"))
        game.steam = parse_int(request.form.get("steam"))
        game.opencritic = parse_int(request.form.get("opencritic"))

        session.commit()
        flash("Game updated successfully!", "success")
        return redirect(url_for("search"))

    # GET - prepare simple values for template
    pid_values = [getattr(game, f"pid{i}") or "" for i in range(1, 6)]
    dates = {
        "announced": game.announced.isoformat() if game.announced else "",
        "added": game.added.isoformat() if game.added else "",
        "removed": game.removed.isoformat() if game.removed else "",
        "release": game.release.isoformat() if game.release else "",
    }
    return render_template("edit.html", game=game, pid_values=pid_values, dates=dates)


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        ng = GameData(
            game=request.form["game"],
            announced=parse_date(request.form.get("announced")),
            added=parse_date(request.form.get("added")),
            removed=parse_date(request.form.get("removed")),
            release=parse_date(request.form.get("release")),
            indie=bool(request.form.get("indie")),
            f2p=bool(request.form.get("f2p")),
            first_party=bool(request.form.get("first_party")),
            igdb=parse_int(request.form.get("igdb")),
            steam=parse_int(request.form.get("steam")),
            opencritic=parse_int(request.form.get("opencritic")),
        )
        # pids
        for i in range(1, 6):
            v = request.form.get(f"pid{i}")
            if v and v.strip():
                setattr(ng, f"pid{i}", v.strip())
        session.add(ng)
        session.commit()
        flash("New game added successfully!", "success")
        return redirect(url_for("search"))

    # render form with empty values
    pid_values = ["" for _ in range(5)]
    dates = {"announced": "", "added": "", "removed": "", "release": ""}
    return render_template("edit.html", game=None, pid_values=pid_values, dates=dates)


from sqlalchemy.orm import Session


@app.route("/completion")
def completion():
    with session:
        games = session.query(GameData).order_by(GameData.game).all()
        completion_data = []
        today = date.today()

        for g in games:
            # Skip if release date is in the future
            if g.release and g.release > today:
                continue

            fields = [
                g.pid1,
                g.announced,
                g.added,
                g.release,
                g.igdb,
                g.steam,
                g.opencritic,
            ]

            def is_filled(value):
                # Treat 0 as filled (used as sentinel for "no page")
                if value == 0:
                    return True
                return value not in [None, "", False]

            total = len(fields)
            filled = sum(1 for f in fields if is_filled(f))
            percent = round(100 * filled / total)

            if percent == 100:
                continue  # skip fully complete entries

            missing = []
            if not g.pid1:
                missing.append("PID1")
            if not g.announced:
                missing.append("Announced")
            if not g.added:
                missing.append("Added")
            if not g.release:
                missing.append("Release")
            if g.igdb in [None, ""]:
                missing.append("IGDB")
            if g.steam in [None, ""]:
                missing.append("Steam")
            if g.opencritic in [None, ""]:
                missing.append("OpenCritic")

            completion_data.append(
                {
                    "game": g,
                    "filled": filled,
                    "total": total,
                    "percent": percent,
                    "missing": missing,
                }
            )

        completion_data.sort(key=lambda x: x["percent"], reverse=True)
        return render_template("completion.html", completion_data=completion_data)


if __name__ == "__main__":
    # Use environment variable for port (Render provides this)
    import os

    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
