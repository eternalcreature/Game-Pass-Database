from datetime import datetime


class XboxStoreParser:
    """
    Parses and normalizes Xbox Store API responses into structured data.
    """

    def __init__(self, store_data: dict):
        self.store_data = store_data or {}
        self.publisher_name = self.store_data.get("publisherName")
        self.platforms = self.store_data.get("availableOn", [])

    def get_platforms(self):
        return self.platforms or []

    def get_categories(self):
        return self.store_data.get("categories", [])

    def get_publisher(self):
        return self.publisher_name

    def get_developer(self, publisher):
        dev = self.store_data.get("developerName")
        return dev or publisher

    def get_store_title(self):
        return self.store_data.get("title")

    def get_capabilities(self):
        return self.store_data.get("capabilities", [])

    def get_release_date(self):
        release_date = self.store_data.get("releaseDate")
        if release_date:
            release_date = release_date.split("T")[0]

    def determine_free_to_play(self, manual_flag):
        try:
            msrp = (
                self.store_data.get("specificPrices", {})
                .get("purchaseable", {})
                .get("msrp", None)
            )
            if msrp is not None:
                return float(msrp) == 0.0
            return manual_flag
        except Exception:
            return manual_flag

    def get_availabilities(self):
        decryption = {
            "CFQ7TTC0K5DJ": "Essential",
            "CFQ7TTC0KHS0": "Ultimate",
            "CFQ7TTC0K6L8": "Console",
            "CFQ7TTC0KGQ8": "PC",
            "CFQ7TTC0P85B": "Premium",
            "CFQ7TTC0QH5H": "Ubisoft+ Premium",
            "nakuconsole": "Ubisoft+ Classics",
            "nakupcgce": "Ubisoft+ Classics PC",
            "CFQ7TTC0K5DH": "EA Play",
        }

        result = {}
        try:
            availabilities = self.store_data.get("passMetadataByPassProductId", {})
            for product_id, meta in availabilities.items():
                if product_id in decryption:
                    name = decryption[product_id]
                    added = meta.get("entryDateUTC")
                    removed = meta.get("exitDateUTC")
                    if added:
                        added = added.split("T")[0]
                    if removed:
                        removed = removed.split("T")[0]
                    result[name] = {"added": added, "removed": removed}

            # Handle EA Play ↔ Ultimate equivalences
            if self.publisher_name == "Electronic Arts":
                if "Ultimate" in result and "EA Play" not in result:
                    result["EA Play"] = result["Ultimate"]
                if "EA Play" in result and "Ultimate" not in result:
                    result["Ultimate"] = result["EA Play"]
                if (
                    "PC" not in result
                    and "EA Play" in result
                    and "pc" in self.platforms
                ):
                    result["PC"] = result["EA Play"]

            # 🔍 Refinement: if Ultimate's 'added' is newer than the oldest, pull it back
            added_dates = [
                datetime.strptime(data["added"], "%Y-%m-%d")
                for data in result.values()
                if data.get("added")
            ]

            if added_dates and "Ultimate" in result:
                oldest = min(added_dates)
                oldest_str = oldest.strftime("%Y-%m-%d")

                ultimate_added = result["Ultimate"].get("added")
                if ultimate_added:
                    try:
                        ultimate_date = datetime.strptime(ultimate_added, "%Y-%m-%d")
                        if ultimate_date > oldest:
                            result["Ultimate"]["added"] = oldest_str
                    except ValueError:
                        pass

        except Exception as e:
            result["error"] = str(e)

        return result

    def to_dict(self, manual_f2p_flag):
        """Aggregate parsed data into a unified dictionary."""
        return {
            "store_title": self.get_store_title(),
            "platforms": self.get_platforms(),
            "release_date": self.get_release_date(),
            "availabilities": self.get_availabilities(),
            "capabilities": self.get_capabilities(),
            "categories": self.get_categories(),
            "publisher": (pub := self.get_publisher()),
            "developer": self.get_developer(pub),
            "f2p": self.determine_free_to_play(manual_f2p_flag),
        }
