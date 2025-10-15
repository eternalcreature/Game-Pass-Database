class IGDBParser:
    """Parser for IGDB game data with convenient accessors and safe lookups."""

    def __init__(self, data: dict):
        self._data = data or {}

    # === Internal helper methods ===

    def _extract_names(self, key: str) -> list[str]:
        """Safely extract a list of 'name' values from a list of dicts under key."""
        return [
            item["name"]
            for item in self._data.get(key, [])
            if isinstance(item, dict) and "name" in item
        ]

    def _extract_companies(self, role_key: str) -> list[str]:
        """Extract unique company names from 'involved_companies' with given role flag."""
        companies = {
            c.get("company", {}).get("name")
            for c in self._data.get("involved_companies", [])
            if c.get(role_key)
        }
        return sorted(filter(None, companies))  # Remove None and sort alphabetically

    # === Field accessors ===

    def get_id(self):
        return self._data.get("id")

    def get_name(self):
        return self._data.get("name")

    def get_url(self):
        return self._data.get("url")

    def get_developers(self):
        return self._extract_companies("developer")

    def get_publishers(self):
        return self._extract_companies("publisher")

    def get_genres(self):
        return self._extract_names("genres")

    def get_themes(self):
        return self._extract_names("themes")

    def get_game_modes(self):
        return self._extract_names("game_modes")

    def get_player_perspectives(self):
        return self._extract_names("player_perspectives")

    # === Export helpers ===

    def to_dict(self):
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
        }

    def get_raw(self):
        """Return the raw IGDB data for debugging or incremental enrichment."""
        return self._data

    def __repr__(self):
        return f"IGDBParser(name={self.get_name()!r}, id={self.get_id()})"
