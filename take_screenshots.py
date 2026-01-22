#!/usr/bin/env python3
"""Take screenshots of the Reddar dashboard for README."""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright


def take_screenshots(base_url: str = "http://localhost:8501"):
    """Take screenshots of all dashboard pages."""

    screenshots_dir = Path(__file__).parent / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        screenshots = [
            ("dashboard.png", "/", 1),
            ("run-agent.png", "/run", 1),
            ("usage.png", "/usage", 1),
        ]

        for filename, path, wait_secs in screenshots:
            url = f"{base_url}{path}"
            print(f"Capturing {filename} from {url}...")
            page.goto(url)
            time.sleep(wait_secs)  # Wait for JS to load
            page.screenshot(path=screenshots_dir / filename, full_page=True)
            print(f"  Saved {filename}")

        # For report, we need to find an existing report
        page.goto(base_url)
        time.sleep(1)

        # Try to find a report link
        report_link = page.query_selector('a[href^="/report/"]')
        if report_link:
            report_url = report_link.get_attribute("href")
            print(f"Capturing report.png from {report_url}...")
            page.goto(f"{base_url}{report_url}")
            time.sleep(1)
            page.screenshot(path=screenshots_dir / "report.png", full_page=True)
            print("  Saved report.png")
        else:
            print("  No report found - skipping report.png")

        browser.close()

    print(f"\nScreenshots saved to {screenshots_dir}")


if __name__ == "__main__":
    import sys

    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"
    take_screenshots(base_url)
