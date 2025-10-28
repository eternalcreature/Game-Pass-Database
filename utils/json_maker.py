from utils.xbox_store_scraper import xbox_scrape
from utils.igdb_retriever import get_IGDB_data
from utils.igdb_best_match import search_igdb_best
from utils.xbox_store_parser import XboxStoreParser
from utils.igdb_parser import IGDBParser
import webbrowser

from typing import Dict, List, Optional
from collections import defaultdict

import logging
import pandas as pd

import os, json

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class JSONMaker:
    """
    Coordinates data retrieval and integration for a game entry.
    Fetches Xbox store data, IGDB data, and (optionally) Steam data,
    then composes them into a unified JSON structure.
    """

    def __init__(self, row, page, overwrite: bool = False):
        self._row = row
        self._pids = [
            pid for pid in (row.pid1, row.pid2, row.pid3, row.pid4, row.pid5) if pid
        ]
        self._name = row.game
        self._page = page
        self._overwrite = overwrite

        self._store_data_list: List[dict] = []
        self._IGDB_data: Optional[dict] = None
        self._IGDB_version_data: Optional[dict] = None
        self._steam_data: Optional[dict] = None

        self._basic_data_df = None  # Lazy-loaded cache for alternate title IDs

    async def fetch_store_data(self):
        """Fetch all Xbox store pages asynchronously for associated product IDs."""
        logging.info(f"Fetching store data for {self._name} ({', '.join(self._pids)})")

        data_list = [
            await xbox_scrape(pid, self._page, overwrite=self._overwrite)
            for pid in self._pids
        ]
        platforms_dict = {
            pid: data.get("availableOn", [])
            for (pid, data) in zip(self._pids, data_list)
        }
        groups = self.group_skus_by_platform(platforms_dict)
        return data_list, groups

    def fetch_IGDB_data(self, id):
        """Fetch metadata from IGDB using stored IGDB ID."""
        logging.info(f"Fetching IGDB data for {self._row.game} : IGDB ID: {id}")
        data, _ = get_IGDB_data(id, overwrite=self._overwrite)
        return data

    @staticmethod
    def group_skus_by_platform(sku_platforms: Dict[str, List[str]]) -> List[List[str]]:
        """
        Group Xbox product IDs (SKUs) into clusters based on identical platform sets,
        ignoring xCloud availability.
        """
        groups: Dict[frozenset[str], List[str]] = defaultdict(list)

        for sku, platforms in sku_platforms.items():
            key = frozenset(p.lower() for p in platforms if p.lower() != "xcloud")
            groups[key].append(sku)

        sorted_groups = [
            sorted(group)
            for _, group in sorted(groups.items(), key=lambda x: sorted(x[1])[0])
        ]
        return sorted_groups

    def get_alternate_title_id(self, pid):
        """Lookup alternate title ID from basic_data.csv."""
        if self._basic_data_df is None:
            self._basic_data_df = pd.read_csv("mnt/xbox/basic_data.csv", index_col=None)
        result = self._basic_data_df.loc[self._basic_data_df.pid == pid]
        print(result)
        if result.empty:
            return None

    async def compose_jsons(self):
        """Fetch, parse, and integrate all data sources into final JSON objects."""
        self._store_data_list, sku_groups = await self.fetch_store_data()
        self._IGDB_data = self.fetch_IGDB_data(self._row.igdb)

        all_jsons = []

        for pid, store_data in zip(self._pids, self._store_data_list):
            if os.path.exists(f"mnt/xbox/gp_new/{pid}.json"):
                print(f"mnt/xbox/gp_new/{pid}.json already exists")
                continue
            print(f"Generating json for {pid}...")
            xbox_data = XboxStoreParser(store_data).to_dict(self._row.f2p)
            igdb_match = search_igdb_best(xbox_data["store_title"], self._row.release)
            if not igdb_match:
                print("Assigning parent igdb to the SKU IGDB")
                igdb_match = self._row.igdb

            self._IGDB_version_data = self.fetch_IGDB_data(igdb_match)

            igdb_parent_data = IGDBParser(self._IGDB_data).to_dict()
            igdb_version_data = IGDBParser(self._IGDB_version_data).to_dict()

            related_skus = [p for p in self._pids if p != pid]
            alternate_xbox_id = self.get_alternate_title_id(pid)

            data = {
                "basic_info": {
                    "base_id": igdb_parent_data.get("id"),
                    "specific_id": igdb_match,
                    "title": igdb_parent_data.get("name"),
                    "store_title": xbox_data["store_title"],
                    "pid": pid,
                    "alternate_xbox_id": alternate_xbox_id,
                    "related_skus": related_skus,
                    "sku_groups": sku_groups,
                    "original_release_date": self._row.release.strftime("%Y-%m-%d"),
                    "release_date": xbox_data["release_date"],
                    "platforms": xbox_data["platforms"],
                },
                "availabilities": [xbox_data["availabilities"]],
                "flags": {
                    "indie": self._row.indie,
                    "first_party": self._row.first_party,
                    "f2p": xbox_data["f2p"],
                },
                "xbox_store_meta": {
                    "capabilities": xbox_data["capabilities"],
                    "categories": xbox_data["categories"],
                    "publisher": xbox_data["publisher"],
                    "developer": xbox_data["developer"],
                },
                "igdb_meta": {
                    "main": igdb_parent_data,
                    "specific": igdb_version_data,
                },  # IGDBParser placeholder
                "steam_store_meta": {},  # SteamParser placeholder
            }

            with open(f"mnt/xbox/gp_new/{pid}.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            webbrowser.open(f"http://127.0.0.1:5000/edit/{pid}")
            input()

        return all_jsons
