import asyncio
import json
import os
import re
from pprint import pprint
from typing import Any, Optional
from playwright.async_api import Page

WAIT_TIME = 3


class XboxStoreScraper:
    """
    Scrapes product metadata from the Xbox Store by extracting preloaded JSON data.

    Example:
        scraper = XboxStoreScraper(pid="9NBLGGH6C7RM", page=page)
        await scraper.fetch_and_save()

    Args:
        pid (str): The Xbox product ID (e.g., "9NBLGGH6C7RM").
        page (Page): A Playwright Page instance used for navigation and HTML retrieval.
        display (bool, optional): Whether to pretty-print extracted product data. Defaults to False.
        output_dir (str, optional): Directory path to save extracted JSON files.
            Defaults to "mnt/xbox/store_meta/".
        overwrite(bool, optional): Whether to overwrite the existing JSON file.
    """

    def __init__(
        self,
        pid: str,
        page: Page,
        display: bool = False,
        output_dir: str = "mnt/xbox/store_meta/",
        overwrite: bool = False,
    ) -> None:
        self._pid: str = pid
        self._page: Page = page
        self._display: bool = display
        self._output_dir: str = output_dir
        self._overwrite: bool = overwrite

        # Internal state
        self._url: Optional[str] = None
        self._html: Optional[str] = None
        self._product_data: Optional[dict[str, Any]] = None

    async def load_html(self, wait_time: int = WAIT_TIME) -> None:
        """
        Loads the Xbox Store product page HTML into memory.

        Args:
            wait_time (int, optional): Seconds to wait after navigation.
                Defaults to global WAIT_TIME.

        Raises:
            RuntimeError: If the page content fails to load.
        """
        self._url = f"https://www.xbox.com/en-us/games/store/a/{self._pid.upper()}?ocid=storeforweb"
        print(f"Loading {self._url} ...")

        await self._page.goto(self._url)
        await asyncio.sleep(wait_time)

        self._html = await self._page.content()
        if not self._html:
            raise RuntimeError(f"Failed to load HTML for {self._pid}")

    def extract_product_data(self) -> Optional[dict[str, Any]]:
        """
        Extracts product data from the preloaded JSON embedded in the HTML.

        Returns:
            Optional[dict[str, Any]]: Extracted product data if successful, otherwise None.

        Raises:
            ValueError: If called before `load_html()`.
        """
        if not self._html:
            raise ValueError(
                "HTML content not loaded. Did you forget to call load_html()?"
            )

        pattern = r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*;\s*window\.env"
        match = re.search(pattern, self._html, re.DOTALL)
        if not match:
            print(f"No embedded JSON found for {self._pid}")
            return None

        raw_json = match.group(1)
        data = json.loads(raw_json)

        try:
            product = data["core2"]["products"]["productSummaries"][self._pid.upper()]
        except KeyError:
            print(f"Could not locate product data for PID: {self._pid}")
            return None

        # Clean up bulky or unneeded sections
        for key in [
            "images",
            "languagesSupported",
            "systemRequirements",
            "videos",
            "cmsVideos",
        ]:
            product.pop(key, None)

        if self._display:
            pprint(data)

        return product

    async def fetch(self) -> Optional[dict[str, Any]]:
        """
        Asynchronously fetches and parses product data without saving to disk.

        Returns:
            Optional[dict[str, Any]]: Extracted product data, or None if extraction failed.
        """
        await self.load_html()
        return self.extract_product_data()

    def save_to_file(self) -> str:
        """
        Saves extracted data to a JSON file in the configured output directory.

        Returns:
            str: The full path to the saved JSON file.
        """
        os.makedirs(self._output_dir, exist_ok=True)
        output_file = os.path.join(self._output_dir, f"{self._pid}.json")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self._product_data, f, indent=2, ensure_ascii=False)

        print(f"Saved extracted product JSON to {output_file}")
        return output_file

    async def fetch_and_save(self) -> Optional[str]:
        """
        Fetches, extracts, and saves Xbox Store product metadata to a JSON file.

        Returns:
            Optional[str]: Path to the saved JSON file, or None if skipped or failed.
        """
        output_file = os.path.join(self._output_dir, f"{self._pid}.json")

        if os.path.exists(output_file):
            if not self._overwrite:
                print(f"Output file {output_file} already exists, retrieving data...")
                with open(output_file, "r", encoding="utf") as file:
                    self._product_data = json.load(file)
                if self._display:
                    pprint(self._product_data)
                return output_file
            else:
                print("Overwriting existing file...")

        self._product_data = await self.fetch()
        if not self._product_data:
            print(f"Failed to extract product data for {self._pid}")
            return None

        return self.save_to_file()


# ---------------------------------------------------------------------------
# 🟢 Convenience function for one-line use
# ---------------------------------------------------------------------------


async def xbox_scrape(
    pid: str,
    page: Page,
    display: bool = False,
    output_dir: str = "mnt/xbox/store_meta/",
    overwrite: bool = False,
) -> Optional[dict[str, Any]]:
    """
    Convenience wrapper for one-line Xbox Store scraping.

    This helper performs all steps:
        1. Create a scraper
        2. Fetch and extract product data
        3. Save the JSON file
        4. Return the extracted dictionary

    Args:
        pid (str): The Xbox product ID (e.g., "9NBLGGH6C7RM").
        page (Page): A Playwright Page instance.
        display (bool, optional): Whether to pretty-print extracted product data. Defaults to False.
        output_dir (str, optional): Directory path to save extracted JSON files.
            Defaults to "mnt/xbox/store_meta/".
        overwrite(bool, optional): Whether to overwrite the existing JSON file.

    Returns:
        Optional[dict[str, Any]]: The extracted product data, or None if failed or skipped.
    """
    scraper = XboxStoreScraper(
        pid, page, display=display, output_dir=output_dir, overwrite=overwrite
    )
    await scraper.fetch_and_save()
    return scraper._product_data
