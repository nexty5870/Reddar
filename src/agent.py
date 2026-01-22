#!/usr/bin/env python3
"""Reddit Intelligence Agent - Autonomous scraping and analysis pipeline."""

import argparse
import json
import subprocess
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

# Add parent dir to path for imports when run directly
sys.path.insert(0, str(Path(__file__).parent))

from scraper import scrape_focus_area, save_scrape_data, load_config, get_available_subreddits
from analyzer import analyze_scrape_data, save_report


def run_pipeline(focus_area: str, verbose: bool = True) -> dict:
    """Run the full scrape -> analyze pipeline."""

    config = load_config()

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"Reddit Intelligence Agent")
        print(f"Focus Area: {focus_area}")
        print(f"Started: {datetime.now().isoformat()}")
        print(f"{'=' * 60}\n")

    # Step 1: Scrape
    if verbose:
        print("[1/3] Scraping Reddit...")

    scrape_data = scrape_focus_area(focus_area, config)
    scrape_path = save_scrape_data(scrape_data)
    scrape_data["source_file"] = str(scrape_path)

    if verbose:
        print(
            f"      Scraped {scrape_data['total_posts']} posts from {len(scrape_data['subreddits'])} subreddits"
        )

    # Step 2: Analyze
    if verbose:
        print("\n[2/3] Analyzing with LLM...")

    report = analyze_scrape_data(scrape_data, config)
    report_path, new_opps, new_pains = save_report(report)

    if verbose:
        analysis = report.get("analysis", {})
        total_opps = len(analysis.get("opportunities", []))
        total_pains = len(analysis.get("pain_points", []))
        print(
            f"      Found {new_opps} new opportunities (+{total_opps} total), {new_pains} new pain points (+{total_pains} total)"
        )

    # Step 3: Summary
    if verbose:
        print("\n[3/3] Pipeline complete!")
        print(f"\n{'=' * 60}")
        print("Results Summary:")
        print(f"{'=' * 60}")

        if "analysis" in report and "executive_summary" in report["analysis"]:
            print(f"\n{report['analysis']['executive_summary']}\n")

        if "analysis" in report and "opportunities" in report["analysis"]:
            print("Top Opportunities:")
            for i, opp in enumerate(report["analysis"]["opportunities"][:5], 1):
                print(
                    f"  {i}. {opp.get('title', 'Untitled')} [{opp.get('potential', '?')} potential]"
                )

        print(f"\nFull report: {report_path}")

    return {
        "success": True,
        "scrape_file": str(scrape_path),
        "report_file": str(report_path),
        "posts_analyzed": scrape_data["total_posts"],
        "opportunities_found": new_opps,
        "total_opportunities": len(report.get("analysis", {}).get("opportunities", [])),
        "report": report,
    }


def list_focus_areas():
    """List available focus areas."""
    areas = get_available_subreddits()
    print("\nAvailable Focus Areas:")
    print("-" * 40)
    for area_id, info in areas.items():
        print(f"\n{area_id}:")
        print(f"  Name: {info['name']}")
        print(f"  Description: {info['description']}")
        print(f"  Subreddits: {', '.join(info['subreddits'])}")


def start_dashboard(open_browser: bool = True):
    """Start the web dashboard."""
    config = load_config()
    web_config = config.get("web", {})
    port = web_config.get("port", 8501)

    base_dir = Path(__file__).parent.parent
    web_app = base_dir / "web" / "app.py"

    print(f"\nStarting dashboard on http://localhost:{port}")

    if open_browser:
        # Open browser after a short delay
        webbrowser.open(f"http://localhost:{port}")

    # Run Flask in foreground (blocking)
    subprocess.run([sys.executable, str(web_app)], cwd=str(base_dir))


def main():
    parser = argparse.ArgumentParser(
        description="Reddit Intelligence Agent - Autonomous opportunity discovery"
    )
    parser.add_argument(
        "focus_area",
        nargs="?",
        default=None,
        help="Focus area to analyze (use --list to see options)",
    )
    parser.add_argument("--list", "-l", action="store_true", help="List available focus areas")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument(
        "--no-web", action="store_true", help="Don't start web dashboard after analysis"
    )
    parser.add_argument("--web-only", action="store_true", help="Just start the web dashboard")

    args = parser.parse_args()

    if args.list:
        list_focus_areas()
        return

    if args.web_only:
        start_dashboard()
        return

    # Get focus area
    focus_area = args.focus_area
    if not focus_area:
        config = load_config()
        focus_area = config.get("default_focus", "saas_opportunities")

    # Run pipeline
    try:
        result = run_pipeline(focus_area, verbose=not args.quiet)

        if args.json:
            # Output just the essential info as JSON
            output = {
                "success": result["success"],
                "focus_area": focus_area,
                "posts_analyzed": result["posts_analyzed"],
                "opportunities_found": result["opportunities_found"],
                "report_file": result["report_file"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            print(json.dumps(output, indent=2))

        # Start web dashboard unless --no-web or --json
        if not args.no_web and not args.json:
            start_dashboard()

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
