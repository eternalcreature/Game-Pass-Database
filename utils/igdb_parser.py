from datetime import datetime


class IGDBParser:
    """Parser for IGDB game data with convenient accessors and safe lookups."""

    PLATFORM_NAMES = {
        6: "PC",
        12: "Xbox 360",
        49: "Xbox One",
        169: "Xbox Series X|S",
    }

    GAME_TYPE_MAP = {
        0: "main_game",
        1: "dlc_addon",
        2: "expansion",
        3: "bundle",
        4: "standalone_expansion",
        5: "mod",
        6: "episode",
        7: "season",
        8: "remake",
        9: "remaster",
        10: "expanded_game",
        11: "port",
        12: "fork",
        13: "pack",
        14: "update",
    }

    def __init__(self, data: dict):
        self._data = data or {}

    # === Internal helpers ===

    @staticmethod
    def _fmt_date(ts: int) -> str:
        """Format UNIX timestamp as YYYY-MM-DD (UTC)."""
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

    def _extract_names(self, key: str) -> list[str]:
        """Safely extract a list of 'name' values from a list of dicts under key."""
        section = self._data.get("general", {})
        return [
            item["name"]
            for item in section.get(key, [])
            if isinstance(item, dict) and "name" in item
        ]

    def _extract_companies(self, role_key: str) -> list[str]:
        """Extract unique company names from 'involved_companies' with given role flag."""
        section = self._data.get("general", {})
        companies = {
            c.get("company", {}).get("name")
            for c in section.get("involved_companies", [])
            if c.get(role_key)
        }
        return sorted(filter(None, companies))

    def _extract_game_type(self) -> str | None:
        """Return game type as human-readable string, or None if unavailable."""
        section = self._data.get("general", {})
        code = section.get("game_type")
        return self.GAME_TYPE_MAP.get(code)

    # === Release date parsing ===

    def parse_release_date_info(self) -> dict:
        """Parse and normalize release date information."""
        result = {
            "release_date": None,
            "PC": {"release_date_ea": None, "release_date_1_0": None},
            "Xbox One": {"release_date_ea": None, "release_date_1_0": None},
            "Xbox Series X|S": {"release_date_ea": None, "release_date_1_0": None},
            "Xbox 360": {"release_date_ea": None, "release_date_1_0": None},
        }

        release_dates = self._data.get("release_dates", [])
        all_dates = []

        for entry in release_dates:
            ts = entry.get("date")
            if not ts:
                continue
            all_dates.append(ts)

            platform_name = self.PLATFORM_NAMES.get(entry.get("platform"))
            if not platform_name:
                continue

            status = entry.get("status", 6)  # Default to full release (1.0)
            date_str = self._fmt_date(ts)

            if status == 3:  # Early access
                current = result[platform_name]["release_date_ea"]
                if (
                    not current
                    or ts < datetime.strptime(current, "%Y-%m-%d").timestamp()
                ):
                    result[platform_name]["release_date_ea"] = date_str

            else:  # Full release (6) or unspecified
                current = result[platform_name]["release_date_1_0"]
                if (
                    not current
                    or ts < datetime.strptime(current, "%Y-%m-%d").timestamp()
                ):
                    result[platform_name]["release_date_1_0"] = date_str

        if all_dates:
            result["release_date"] = self._fmt_date(min(all_dates))

        return result

    # === Field accessors ===

    def get_id(self) -> int | None:
        return self._data.get("general", {}).get("id")

    def get_name(self) -> str | None:
        return self._data.get("general", {}).get("name")

    def get_url(self) -> str | None:
        return self._data.get("general", {}).get("url")

    def get_developers(self) -> list[str]:
        return self._extract_companies("developer")

    def get_publishers(self) -> list[str]:
        return self._extract_companies("publisher")

    def get_genres(self) -> list[str]:
        return self._extract_names("genres")

    def get_themes(self) -> list[str]:
        return self._extract_names("themes")

    def get_game_modes(self) -> list[str]:
        return self._extract_names("game_modes")

    def get_player_perspectives(self) -> list[str]:
        return self._extract_names("player_perspectives")

    def get_engine(self) -> list[str]:
        return self._extract_names("game_engines")

    def get_game_type(self) -> str | None:
        return self._extract_game_type()

    # === Export helpers ===

    def to_dict(self) -> dict:
        """Aggregate parsed data into a unified, JSON-friendly dictionary."""
        return {
            "id": self.get_id(),
            "name": self.get_name(),
            "url": self.get_url(),
            "publishers": self.get_publishers(),
            "developers": self.get_developers(),
            "genres": self.get_genres(),
            "themes": self.get_themes(),
            "game_modes": self.get_game_modes(),
            "player_perspectives": self.get_player_perspectives(),
            "engine": self.get_engine(),
            "game_type": self.get_game_type(),
            "release_dates": self.parse_release_date_info(),
        }

    def get_raw(self) -> dict:
        """Return the raw IGDB data for debugging or incremental enrichment."""
        return self._data

    def __repr__(self) -> str:
        return f"IGDBParser(name={self.get_name()!r}, id={self.get_id()})"


# # for testing
# from igdb_retriever import get_IGDB_data
# from pprint import pprint


# def main():

#     lst = [
#         "136604",  # control ue
#         "252828",  # 33 Immortals
#         "219126",  # Abiotic Factor
#         "256017",  # Grinch base
#         "370827",  # Grinch special
#     ]
#     for title in lst:
#         data, _ = get_IGDB_data(
#             title, display=True, output_dir="yolo", overwrite="True"
#         )
#         # pprint(data)
#         result = IGDBParser(data).to_dict()
#         pprint(result)
#         input()


# if __name__ == "__main__":
#     main()
