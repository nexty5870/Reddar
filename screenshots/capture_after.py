#!/usr/bin/env python3
"""Capture after screenshots of the redesigned UI."""

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8501"

PAGES = [
    ("/", "after-dashboard.png"),
    ("/run", "after-run.png"),
    ("/usage", "after-usage.png"),
]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        for path, filename in PAGES:
            url = f"{BASE_URL}{path}"
            print(f"Capturing {url} -> screenshots/{filename}")
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(1000)
            page.screenshot(path=f"screenshots/{filename}", full_page=True)

        browser.close()
        print("Done!")


if __name__ == "__main__":
    main()
