#!/usr/bin/env python3
"""Reddit Intelligence Dashboard - Web interface for viewing reports."""

import json
import sys
import time
import threading
import queue
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify, request, Response
import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

app = Flask(__name__, template_folder="templates", static_folder="static")

# Paths
BASE_DIR = Path(__file__).parent.parent
REPORTS_DIR = BASE_DIR / "reports"
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = BASE_DIR / "config.yaml"


def load_config() -> dict:
    """Load configuration."""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_reports() -> list[dict]:
    """Get all reports (one per focus area), sorted by last update."""
    reports = []

    for path in REPORTS_DIR.glob("report_*.json"):
        try:
            with open(path) as f:
                data = json.load(f)

            # Extract summary info
            analysis = data.get("analysis", {})

            # Handle both old and new report formats
            updated_at = data.get("updated_at") or data.get("generated_at", "")
            created_at = data.get("created_at") or data.get("generated_at", "")
            total_posts = data.get("total_posts_analyzed") or data.get("posts_analyzed", 0)
            total_scans = data.get("total_scans", 1)

            reports.append(
                {
                    "id": data.get("id", path.stem),
                    "focus_area": data.get("focus_area", "unknown"),
                    "focus_name": data.get("focus_name", "Unknown"),
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "total_scans": total_scans,
                    "posts_analyzed": total_posts,
                    "opportunities_count": len(analysis.get("opportunities", [])),
                    "pain_points_count": len(analysis.get("pain_points", [])),
                    "executive_summary": analysis.get("executive_summary", ""),
                    "scan_history": data.get("scan_history", []),
                    "file": str(path),
                }
            )
        except Exception as e:
            print(f"Error loading {path}: {e}")

    # Sort by last update, newest first
    reports.sort(key=lambda x: x["updated_at"], reverse=True)
    return reports


def get_report(report_id: str) -> dict | None:
    """Get a specific report by ID."""
    path = REPORTS_DIR / f"{report_id}.json"
    if not path.exists():
        return None

    with open(path) as f:
        return json.load(f)


@app.route("/")
def index():
    """Dashboard home - list of reports."""
    reports = get_reports()
    config = load_config()
    focus_areas = config.get("focus_areas", {})
    llm_config = config.get("llm", {})
    llm_info = {
        "provider": llm_config.get("provider", "openai-compatible"),
        "model": llm_config.get("model", "default"),
    }

    return render_template(
        "index.html", reports=reports, focus_areas=focus_areas, total_reports=len(reports), llm=llm_info
    )


@app.route("/report/<report_id>")
def view_report(report_id: str):
    """View a specific report."""
    report = get_report(report_id)
    if not report:
        return "Report not found", 404

    return render_template("report.html", report=report)


@app.route("/api/reports")
def api_reports():
    """API: Get all reports."""
    return jsonify(get_reports())


@app.route("/api/report/<report_id>")
def api_report(report_id: str):
    """API: Get a specific report."""
    report = get_report(report_id)
    if not report:
        return jsonify({"error": "Not found"}), 404
    return jsonify(report)


@app.route("/api/focus-areas")
def api_focus_areas():
    """API: Get available focus areas."""
    config = load_config()
    return jsonify(config.get("focus_areas", {}))


@app.route("/api/stats")
def api_stats():
    """API: Get overall statistics."""
    reports = get_reports()

    total_opportunities = sum(r["opportunities_count"] for r in reports)
    total_pain_points = sum(r["pain_points_count"] for r in reports)
    total_posts = sum(r["posts_analyzed"] for r in reports)

    # Group by focus area
    by_focus = {}
    for r in reports:
        fa = r["focus_area"]
        if fa not in by_focus:
            by_focus[fa] = {"count": 0, "opportunities": 0}
        by_focus[fa]["count"] += 1
        by_focus[fa]["opportunities"] += r["opportunities_count"]

    return jsonify(
        {
            "total_reports": len(reports),
            "total_opportunities": total_opportunities,
            "total_pain_points": total_pain_points,
            "total_posts_analyzed": total_posts,
            "by_focus_area": by_focus,
            "latest_report": reports[0] if reports else None,
        }
    )


@app.route("/api/token-usage")
def api_token_usage():
    """API: Get token usage from local usage tracking file."""
    usage_file = DATA_DIR / "usage.json"

    try:
        if not usage_file.exists():
            return jsonify(
                {
                    "connected": True,
                    "total_requests": 0,
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "avg_latency_ms": 0,
                    "recent_logs": [],
                }
            )

        with open(usage_file) as f:
            data = json.load(f)

        totals = data.get("totals", {})
        requests = data.get("requests", [])

        # Calculate average latency
        total_latency = sum(r.get("latency_ms", 0) for r in requests)
        avg_latency = total_latency / len(requests) if requests else 0

        # Format recent logs (return all, let frontend limit if needed)
        recent_logs = []
        for i, req in enumerate(requests):
            recent_logs.append(
                {
                    "id": req.get("id", f"{i + 1:03d}"),
                    "timestamp": req.get("timestamp", ""),
                    "model": req.get("model", ""),
                    "status": "success",
                    "latency_ms": req.get("latency_ms", 0),
                    "prompt_tokens": req.get("prompt_tokens", 0),
                    "completion_tokens": req.get("completion_tokens", 0),
                    "total_tokens": req.get("total_tokens", 0),
                    "messages": req.get("messages", []),
                    "response": req.get("response", ""),
                    "reasoning": req.get("reasoning", ""),
                }
            )

        return jsonify(
            {
                "connected": True,
                "total_requests": totals.get("requests", 0),
                "total_tokens": totals.get("total_tokens", 0),
                "prompt_tokens": totals.get("prompt_tokens", 0),
                "completion_tokens": totals.get("completion_tokens", 0),
                "avg_latency_ms": round(avg_latency),
                "recent_logs": recent_logs,
            }
        )

    except Exception as e:
        return jsonify(
            {
                "connected": False,
                "error": str(e),
                "total_requests": 0,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "avg_latency_ms": 0,
                "recent_logs": [],
            }
        )


@app.route("/run")
def run_page():
    """Run agent page."""
    config = load_config()
    focus_areas = config.get("focus_areas", {})
    return render_template("run.html", focus_areas=focus_areas)


@app.route("/usage")
def usage_page():
    """LLM Usage details page."""
    return render_template("usage.html")


@app.route("/api/run/<focus_area>")
def api_run_agent(focus_area: str):
    """Run agent with SSE streaming output."""
    from scraper import scrape_focus_area, save_scrape_data
    from analyzer import analyze_scrape_data, save_report

    def generate():
        try:
            config = load_config()
            focus_config = config.get("focus_areas", {}).get(focus_area)

            if not focus_config:
                err = {"type": "error", "message": f"Unknown focus area: {focus_area}"}
                yield f"data: {json.dumps(err)}\n\n"
                return

            # Step 1: Scraping
            def sse(data):
                return f"data: {json.dumps(data)}\n\n"

            yield sse({"type": "progress", "step": 1, "percent": 0, "status": "SCRAPING REDDIT"})
            focus_name = focus_config.get("name", focus_area)
            yield sse(
                {"type": "log", "message": f"Starting scan: {focus_name}", "level": "highlight"}
            )

            subreddits = focus_config.get("subreddits", [])
            total_subs = len(subreddits)
            all_posts = []

            for i, subreddit in enumerate(subreddits):
                yield sse({"type": "log", "message": f"Scraping r/{subreddit}..."})
                pct = int((i / total_subs) * 100)
                yield sse(
                    {
                        "type": "progress",
                        "step": 1,
                        "percent": pct,
                        "status": f"SCRAPING r/{subreddit}",
                    }
                )
                yield sse({"type": "stats", "subreddits": i + 1})

                # Import and use scraper functions
                from scraper import fetch_subreddit

                posts = fetch_subreddit(subreddit, limit=25, min_upvotes=5)
                all_posts.extend(posts)

                yield sse(
                    {"type": "log", "message": f"  Found {len(posts)} posts", "level": "success"}
                )
                yield sse({"type": "stats", "posts": len(all_posts)})

                time.sleep(1)  # Rate limit

            # Save scrape data
            scrape_data = {
                "focus_area": focus_area,
                "focus_name": focus_name,
                "focus_description": focus_config.get("description", ""),
                "keywords": focus_config.get("keywords", []),
                "mode": focus_config.get("mode", "opportunities"),  # Pass mode for analysis
                "scraped_at": datetime.now().isoformat(),
                "subreddits": subreddits,
                "total_posts": len(all_posts),
                "posts": all_posts,
            }
            scrape_path = save_scrape_data(scrape_data)
            scrape_data["source_file"] = str(scrape_path)

            yield sse(
                {"type": "progress", "step": 1, "percent": 100, "status": "SCRAPING COMPLETE"}
            )
            yield sse(
                {
                    "type": "log",
                    "message": f"Scraped {len(all_posts)} total posts",
                    "level": "success",
                }
            )

            # Step 2: Analysis with batching
            from analyzer import analyze_batch, merge_batch_analyses

            yield sse({"type": "progress", "step": 2, "percent": 0, "status": "ANALYZING WITH LLM"})

            total_posts = len(all_posts)
            batch_size = 50
            mode = scrape_data.get("mode", "opportunities")

            if total_posts > batch_size:
                # Batched analysis with streaming progress
                batches = [all_posts[i : i + batch_size] for i in range(0, total_posts, batch_size)]
                num_batches = len(batches)

                yield sse(
                    {
                        "type": "log",
                        "message": f"Large dataset ({total_posts} posts) - analyzing in {num_batches} batches",
                        "level": "highlight",
                    }
                )

                batch_analyses = []
                for i, batch in enumerate(batches, 1):
                    pct = int((i - 1) / num_batches * 100)
                    yield sse(
                        {
                            "type": "progress",
                            "step": 2,
                            "percent": pct,
                            "status": f"BATCH {i}/{num_batches}",
                        }
                    )
                    yield sse(
                        {
                            "type": "log",
                            "message": f"Analyzing batch {i}/{num_batches} ({len(batch)} posts)...",
                        }
                    )

                    batch_result = analyze_batch(batch, scrape_data, config, i, num_batches)

                    if "error" not in batch_result:
                        batch_analyses.append(batch_result)
                        yield sse(
                            {
                                "type": "log",
                                "message": f"  Batch {i} complete",
                                "level": "success",
                            }
                        )
                    else:
                        yield sse(
                            {
                                "type": "log",
                                "message": f"  Batch {i} error: {batch_result.get('error', 'unknown')[:100]}",
                                "level": "warning",
                            }
                        )

                # Merge results
                if batch_analyses:
                    yield sse(
                        {
                            "type": "log",
                            "message": f"Merging {len(batch_analyses)} batch results...",
                        }
                    )
                    analysis = merge_batch_analyses(batch_analyses, mode)
                else:
                    analysis = {
                        "error": "All batches failed",
                        "opportunities": [],
                        "pain_points": [],
                    }

                # Build the report
                report = {
                    "id": f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "focus_area": scrape_data["focus_area"],
                    "focus_name": scrape_data["focus_name"],
                    "generated_at": datetime.now().isoformat(),
                    "data_scraped_at": scrape_data["scraped_at"],
                    "subreddits_analyzed": scrape_data["subreddits"],
                    "posts_analyzed": total_posts,
                    "analysis": analysis,
                    "metadata": {
                        "model": config.get("llm", {}).get("model", "unknown"),
                        "source_file": scrape_data.get("source_file", "unknown"),
                        "batches_used": num_batches,
                    },
                }
            else:
                # Small dataset - single analysis
                model_name = config.get("llm", {}).get("model", "LLM")
                yield sse(
                    {
                        "type": "log",
                        "message": f"Sending to {model_name} for analysis...",
                        "level": "highlight",
                    }
                )
                report = analyze_scrape_data(scrape_data, config)

            report_path, new_opps, new_pains = save_report(report)

            # Reload the merged report
            with open(report_path) as f:
                report = json.load(f)

            # Get token usage
            usage_file = DATA_DIR / "usage.json"
            tokens = 0
            if usage_file.exists():
                with open(usage_file) as f:
                    usage_data = json.load(f)
                tokens = usage_data.get("totals", {}).get("total_tokens", 0)

            yield sse({"type": "stats", "tokens": tokens})
            yield sse(
                {"type": "progress", "step": 2, "percent": 100, "status": "ANALYSIS COMPLETE"}
            )

            # Get results - handle both news and opportunities mode
            analysis = report.get("analysis", {})

            # Check if this is news mode
            is_news_mode = "top_stories" in analysis

            if is_news_mode:
                total_stories = len(analysis.get("top_stories", []))
                total_releases = len(analysis.get("notable_releases", []))

                yield sse({"type": "stats", "opportunities": total_stories})  # Reuse field for UI

                yield sse(
                    {
                        "type": "log",
                        "message": f"Found {total_stories} stories, {total_releases} releases",
                        "level": "success",
                    }
                )

                # Step 3: Complete
                yield sse({"type": "progress", "step": 3, "percent": 100, "status": "COMPLETE"})
                report_id = report.get("id", "unknown")
                yield sse(
                    {
                        "type": "complete",
                        "report_id": report_id,
                        "opportunities": total_stories,
                        "pain_points": total_releases,
                        "new_opportunities": total_stories,
                        "new_pain_points": total_releases,
                        "posts": len(all_posts),
                        "mode": "news",
                    }
                )
            else:
                total_opps = len(analysis.get("opportunities", []))
                total_pains = len(analysis.get("pain_points", []))

                yield sse({"type": "stats", "opportunities": total_opps})

                # Show what's new vs total
                if new_opps > 0 or new_pains > 0:
                    yield sse(
                        {
                            "type": "log",
                            "message": f"Added {new_opps} new opportunities, {new_pains} new pain points",
                            "level": "success",
                        }
                    )
                yield sse(
                    {
                        "type": "log",
                        "message": f"Total: {total_opps} opportunities, {total_pains} pain points",
                        "level": "highlight",
                    }
                )

                # Step 3: Complete
                yield sse({"type": "progress", "step": 3, "percent": 100, "status": "COMPLETE"})
                report_id = report.get("id", "unknown")
                yield sse(
                    {
                        "type": "complete",
                        "report_id": report_id,
                        "opportunities": total_opps,
                        "pain_points": total_pains,
                        "new_opportunities": new_opps,
                        "new_pain_points": new_pains,
                        "posts": len(all_posts),
                        "mode": "opportunities",
                    }
                )

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            import traceback

            traceback.print_exc()

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    config = load_config()
    web_config = config.get("web", {})

    # Ensure directories exist
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    app.run(host=web_config.get("host", "0.0.0.0"), port=web_config.get("port", 8501), debug=True)
