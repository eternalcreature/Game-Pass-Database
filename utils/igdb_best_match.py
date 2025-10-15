import os
import re
import json
import time
import requests
from models import get_session, connection_params, GameData
from datetime import datetime, timezone
from dotenv import load_dotenv
from rapidfuzz import fuzz
from pprint import pprint

# ---------------------------------------------------------------------
# DB session
# ---------------------------------------------------------------------
session = get_session(connection_params)

# ---------------------------------------------------------------------
# Environment setup
# ---------------------------------------------------------------------
load_dotenv()
TWITCH_CLIENT_ID = os.getenv("IGDB_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("IGDB_CLIENT_SECRET")

if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
    raise RuntimeError("Missing IGDB_CLIENT_ID or IGDB_CLIENT_SECRET in .env")

# ---------------------------------------------------------------------
# Token cache
# ---------------------------------------------------------------------
TOKEN_PATH = "mnt/xbox/igdb/token.json"


def _load_cached_token() -> str | None:
    """Load cached IGDB token from disk if valid."""
    if not os.path.exists(TOKEN_PATH):
        return None

    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("token") and data.get("expiry", 0) > time.time():
            return data["token"]
    except Exception:
        return None
    return None


def _save_token_to_disk(token: str, expires_in: int) -> None:
    """Save IGDB token to disk with expiry timestamp."""
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    data = {"token": token, "expiry": time.time() + expires_in - 60}
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


def get_igdb_token() -> str:
    """Retrieve or refresh the IGDB API token."""
    cached = _load_cached_token()
    if cached:
        return cached

    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }
    resp = requests.post(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    token = data["access_token"]
    expires_in = data.get("expires_in", 3600)
    _save_token_to_disk(token, expires_in)
    return token


# Global token (cached automatically)
TOKEN = get_igdb_token()


# ---------------------------------------------------------------------
# IGDB search utilities
# ---------------------------------------------------------------------
def search_igdb(title: str) -> None:
    """Perform a basic IGDB search and print the top 15 matches."""
    url = "https://api.igdb.com/v4/games"
    headers = {"Client-ID": TWITCH_CLIENT_ID, "Authorization": f"Bearer {TOKEN}"}

    body = f"""
    search "{title}";
    fields id, name, first_release_date, platforms.name;
    limit 15;
    """

    try:
        resp = requests.post(url, headers=headers, data=body)
        resp.raise_for_status()
        data = resp.json()
        pprint(data)
    except Exception as e:
        print(f"IGDB lookup failed for {title}: {e}")
        return

    time.sleep(0.3)  # stay under IGDB rate limit


def title_similarity(query: str, candidate: str) -> float:
    """Improved fuzzy matching with substring bonuses and length penalties."""
    query_l = query.lower().strip()
    cand_l = candidate.lower().strip()

    base = fuzz.ratio(query_l, cand_l)

    # Bonus if query appears as standalone word sequence
    if re.search(rf"\b{re.escape(query_l)}\b", cand_l, flags=re.IGNORECASE):
        base += 10

    # Penalize much longer candidates
    ratio = len(query_l) / len(cand_l)
    if ratio < 0.5:
        base *= ratio + 0.5

    return min(base, 100)


PLATFORM_PATTERN = re.compile(
    r"(\b|\s|[-–—()|:])(?:Xbox(?:\s(?:One|Series\sX\|S))?|PC|Windows)(\b|\s|[-–—()|:])",
    flags=re.IGNORECASE,
)


def clean_title(title: str) -> str:
    """Remove platform-related terms like 'Xbox', 'PC', etc. from the title."""
    title = re.sub(r"[®™©]", "", title)
    cleaned = PLATFORM_PATTERN.sub(" ", title)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)  # collapse multiple spaces
    return cleaned.strip()


def _igdb_search_core(
    title: str, release_date: datetime | None
) -> tuple[int | None, float]:
    """Internal helper: performs IGDB search and returns (id, best_score)."""
    url = "https://api.igdb.com/v4/games"
    headers = {"Client-ID": TWITCH_CLIENT_ID, "Authorization": f"Bearer {TOKEN}"}
    body = f"""
    search "{title}";
    fields id, name, first_release_date, platforms.name, url;
    limit 15;
    """

    try:
        resp = requests.post(url, headers=headers, data=body)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"IGDB lookup failed for {title}: {e}")
        return None, 0

    if not data:
        print(f"No IGDB results for {title}")
        return None, 0

    release_year = release_date.year if release_date else None
    target_platforms = {
        "PC (Microsoft Windows)",
        "Xbox One",
        "Xbox Series X|S",
        "Xbox 360",
    }

    best = None
    best_score = 0

    for c in data:
        name = c["name"]
        fuzz_score = title_similarity(title, clean_title(name))

        igdb_year = (
            datetime.fromtimestamp(c["first_release_date"], timezone.utc).year
            if c.get("first_release_date")
            else None
        )
        year_score = (
            20
            if release_year and igdb_year == release_year
            else (
                10
                if release_year and igdb_year and abs(igdb_year - release_year) <= 1
                else 0
            )
        )

        platform_names = {
            p["name"] for p in c.get("platforms", []) if isinstance(p, dict)
        }
        platform_score = 15 if target_platforms & platform_names else 0

        total = fuzz_score + year_score  # + platform_score  # optional

        if total > best_score:
            best = c
            best_score = total

    time.sleep(0.3)

    if best:
        igdb_year = (
            datetime.fromtimestamp(best["first_release_date"], timezone.utc).year
            if best.get("first_release_date")
            else "?"
        )
        print(
            f"Best match for '{title}': {best['name']} ({best_score:.1f}) "
            f"(id={best['id']}, year={igdb_year})"
        )
        print(best.get("url"))

        return (best["id"] if best_score >= 80 else None), best_score

    return None, 0


def search_igdb_best(title: str, release_date: datetime | None) -> int | None:
    """
    Searches IGDB for the best match, cleaning platform names first,
    and allows manual retry if automatic search fails.
    """
    cleaned_title = clean_title(title)
    igdb_id, best_score = _igdb_search_core(cleaned_title, release_date)

    if igdb_id:
        print(f"✅ {title} matched successfully.")
        return igdb_id

    # # Offer a manual fallback
    # print(f"⚠️ No confident match for '{title}' (best={best_score:.1f}).")
    return None


# async def main():
#     today = date.today()
#     games = (
#         session.query(GameData)
#         .filter(GameData.release <= today)
#         .filter(GameData.igdb == None)
#         .order_by(GameData.game)
#         .all()
#     )
#     pprint(games)
#     # print(f"Found {len(games)} games eligible for IGDB lookup.")
#     # for game in games:
#     #     print(f"\n🎮 {game.game}")
#     #     id = search_igdb_best(game.game, game.release)
#     #     if id:
#     #         game.igdb = id
#     #         session.add(game)
#     #         session.commit()
#     #         print(f"  ✅ Saved {id} for {game.game}.")
#     #     else:
#     #         print("  ⏩ Skipped.")


# if __name__ == "__main__":
#     asyncio.run(main())
