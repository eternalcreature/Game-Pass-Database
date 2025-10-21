from utils.json_maker import JSONMaker

from playwright.async_api import async_playwright
from models import get_session, connection_params, GameData
from datetime import datetime, date
from collections import defaultdict
import asyncio
import json
import sys
import os
import webbrowser


# ---- Main conversion ----
async def async_main():
    async with async_playwright() as p:

        # -------Playwright setup---------
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = await context.new_page()
        # --------------------------------

        # ------DB data load------------
        session = get_session(connection_params)

        today = date.today()
        games = (
            session.query(GameData)
            .filter(GameData.release <= today)
            .order_by(GameData.game)
            .all()
        )

        for game in games:
            a = JSONMaker(game, page)
            await a.compose_jsons()
            print("")
            print("Next...")


if __name__ == "__main__":
    # if len(sys.argv) < 2:
    #     print("Usage: python script_name.py <pid>")
    #     sys.exit(1)

    # pid = sys.argv[1]
    asyncio.run(async_main())
