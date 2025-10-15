import json
import os
import time
import requests
from pprint import pprint
from dotenv import load_dotenv
from typing import Any, Dict, List, Optional, Tuple
from time import sleep

# ---- Load .env ----
load_dotenv()
TWITCH_CLIENT_ID = os.getenv("IGDB_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("IGDB_CLIENT_SECRET")

if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
    raise RuntimeError("Missing IGDB_CLIENT_ID or IGDB_CLIENT_SECRET in .env")


class IGDBRetriever:
    """
    Retrieves and caches game metadata from IGDB (via Twitch API).

    Features:
        - Automatically manages and caches OAuth token (in memory and on disk).
        - Fetches game metadata by IGDB ID.
        - Saves results as JSON to local cache.
    """

    # ---- Class-level token cache ----
    _token_cache: Optional[str] = None
    _token_expiry: float = 0.0
    _token_file: str = "mnt/xbox/igdb/token.json"

    def __init__(
        self,
        igdb_id: int,
        display: bool = False,
        output_dir: str = "mnt/xbox/igdb/",
        overwrite: bool = False,
    ) -> None:
        """
        Initialize an IGDBRetriever instance for a specific game ID.

        Args:
            igdb_id: IGDB numeric game ID to fetch.
            display: Whether to print the retrieved data to stdout.
            output_dir: Directory to store JSON files.
            overwrite: Whether to overwrite an existing cached file.
        """
        self._id = igdb_id
        self._output_dir = output_dir
        self._overwrite = overwrite
        self._display = display
        self._product_data: Optional[List[Dict[str, Any]]] = None

    # ------------------------------------------------------------------

    @classmethod
    def _load_token_from_disk(cls) -> Optional[str]:
        """
        Load a previously saved OAuth token from disk, if it exists and is still valid.
        """
        if not os.path.exists(cls._token_file):
            return None

        try:
            with open(cls._token_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if time.time() < data.get("expiry", 0):
                cls._token_cache = data["token"]
                cls._token_expiry = data["expiry"]
                return cls._token_cache
        except Exception:
            pass
        return None

    @classmethod
    def _save_token_to_disk(cls, token: str, expires_in: int) -> None:
        """
        Save the current OAuth token to disk for reuse across sessions.
        """
        os.makedirs(os.path.dirname(cls._token_file), exist_ok=True)
        expiry = time.time() + expires_in - 60  # renew 1 minute early
        with open(cls._token_file, "w", encoding="utf-8") as f:
            json.dump({"token": token, "expiry": expiry}, f)

        cls._token_cache = token
        cls._token_expiry = expiry

    @classmethod
    def _get_igdb_token(cls) -> str:
        """
        Retrieve a valid OAuth access token (cached or from Twitch).

        Returns:
            A valid access token string.
        """
        # Check in-memory cache
        if cls._token_cache and time.time() < cls._token_expiry:
            return cls._token_cache

        # Check disk cache
        token = cls._load_token_from_disk()
        if token:
            return token

        # Request new token
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
        cls._save_token_to_disk(token, expires_in)

        return token

    # ------------------------------------------------------------------

    def fetch_data(self) -> List[Dict[str, Any]]:
        """
        Fetch game metadata from IGDB for this retriever's game ID.

        Returns:
            A list of dictionaries (usually a single-element list).
        """
        token = self._get_igdb_token()

        url = "https://api.igdb.com/v4/release_dates"
        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}",
        }

        body = f"fields *; where game = {self._id} & status = 6 &platform=6;"

        # body = (
        #     f"fields name, url, parent_game, "
        #     f"involved_companies.company.name, involved_companies.developer, involved_companies.publisher, "
        #     f"genres.name, game_modes.name, player_perspectives.name, themes.name;"
        #     f" where id = {self._id};"
        # )

        resp = requests.post(url, headers=headers, data=body)
        resp.raise_for_status()
        data = resp.json()
        if self._display:
            pprint(data)

        return data[0]

    # ------------------------------------------------------------------

    def request_and_save_data(self) -> str:
        """
        Retrieve IGDB data and save it as a JSON file in the local cache.

        Returns:
            The path to the JSON file.
        """
        os.makedirs(self._output_dir, exist_ok=True)
        output_file = os.path.join(self._output_dir, f"{self._id}.json")

        # Load from cache if allowed
        if os.path.exists(output_file) and not self._overwrite:
            print("Data already exists. Loading from cache...")
            with open(output_file, "r", encoding="utf-8") as f:
                self._product_data = json.load(f)
            return output_file

        if os.path.exists(output_file):
            print("Overwriting existing file...")

        # Fetch new data
        self._product_data = self.fetch_data()

        # Save to JSON
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self._product_data, f, indent=2, ensure_ascii=False)
        sleep(0.2)
        return output_file


# ----------------------------------------------------------------------


def get_IGDB_data(
    igdb_id: int,
    display: bool = False,
    output_dir: str = "mnt/xbox/igdb/",
    overwrite: bool = False,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Convenience wrapper for one-off IGDB retrievals.

    Returns:
        (parsed_data, file_path)
    """
    retriever = IGDBRetriever(
        igdb_id=igdb_id,
        display=display,
        output_dir=output_dir,
        overwrite=overwrite,
    )
    output_file = retriever.request_and_save_data()
    return retriever._product_data, output_file
