"""LLM-powered analyzer - Uses local Morpheus endpoint to analyze scraped data."""

import json
import httpx
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import yaml


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def log_usage(
    usage: dict,
    model: str,
    latency_ms: int,
    messages: list[dict] = None,
    response_content: str = None,
    reasoning_content: str = None,
) -> None:
    """Log token usage to a JSON file for dashboard display."""
    import uuid

    usage_file = Path(__file__).parent.parent / "data" / "usage.json"
    usage_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing usage data
    if usage_file.exists():
        with open(usage_file) as f:
            data = json.load(f)
    else:
        data = {
            "requests": [],
            "totals": {
                "requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }

    # Generate unique ID for this request
    request_id = str(uuid.uuid4())[:8]

    # Add new request with full content
    request_log = {
        "id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "latency_ms": latency_ms,
        "messages": messages or [],
        "response": response_content or "",
        "reasoning": reasoning_content or "",
    }

    # Keep last 100 requests
    data["requests"] = [request_log] + data["requests"][:99]

    # Update totals
    data["totals"]["requests"] += 1
    data["totals"]["prompt_tokens"] += request_log["prompt_tokens"]
    data["totals"]["completion_tokens"] += request_log["completion_tokens"]
    data["totals"]["total_tokens"] += request_log["total_tokens"]

    with open(usage_file, "w") as f:
        json.dump(data, f, indent=2)


def call_llm(
    prompt: str, system_prompt: str = "", config: Optional[dict] = None, json_mode: bool = False
) -> tuple[str, str]:
    """Call the local LLM endpoint."""
    import time

    if config is None:
        config = load_config()

    llm_config = config.get("llm", {})
    base_url = llm_config.get("base_url", "http://localhost:8000/v1")
    model = llm_config.get("model", "glm-4.7-flash")
    max_tokens = llm_config.get("max_tokens", 8000)
    temperature = llm_config.get("temperature", 0.7)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        start_time = time.time()
        response = httpx.post(
            f"{base_url}/chat/completions",
            json=payload,
            timeout=300,  # 5 min timeout for large context
        )
        latency_ms = int((time.time() - start_time) * 1000)
        response.raise_for_status()
        data = response.json()

        # Handle reasoning models - get content from the right place
        choice = data["choices"][0]
        content = choice["message"].get("content") or ""
        reasoning = choice["message"].get("reasoning_content") or ""

        # Log usage with full content
        usage = data.get("usage", {})
        if usage:
            log_usage(
                usage=usage,
                model=model,
                latency_ms=latency_ms,
                messages=messages,
                response_content=content,
                reasoning_content=reasoning,
            )

        return content, reasoning

    except Exception as e:
        print(f"LLM call failed: {e}")
        raise


ANALYSIS_SYSTEM_PROMPT = """You are a business intelligence analyst specializing in identifying market opportunities from online discussions.

Your task is to analyze Reddit posts and extract actionable business insights. Focus on:
1. Pain points and unmet needs
2. Existing solutions and their shortcomings  
3. Market signals (demand, willingness to pay, market size hints)
4. Competitive landscape mentions
5. Specific business/product ideas with validation signals

Be specific and cite the source posts. Quantify when possible (upvotes, comments as engagement signals).
Output structured JSON that can be parsed programmatically."""


ANALYSIS_USER_PROMPT = """Analyze the following Reddit data from the "{focus_name}" focus area.

Focus Keywords: {keywords}

Here are {total_posts} posts from subreddits: {subreddits}

---
{posts_content}
---

Analyze this data and return a JSON object with this structure:
{{
  "executive_summary": "2-3 sentence overview of key findings",
  "opportunities": [
    {{
      "title": "Opportunity name",
      "description": "What the opportunity is",
      "evidence": ["List of specific posts/comments that support this"],
      "demand_signals": "Why there's demand (upvotes, frequency, sentiment)",
      "competition": "Known competitors or alternatives mentioned",
      "difficulty": "low/medium/high",
      "potential": "low/medium/high",
      "tags": ["relevant", "tags"]
    }}
  ],
  "pain_points": [
    {{
      "problem": "The pain point",
      "frequency": "How often mentioned",
      "severity": "low/medium/high",
      "current_solutions": "What people currently do",
      "source_posts": ["post IDs or titles"]
    }}
  ],
  "market_insights": [
    {{
      "insight": "The insight",
      "evidence": "Supporting evidence",
      "actionable": true/false
    }}
  ],
  "trending_topics": ["list", "of", "trending", "topics"],
  "recommended_actions": [
    "Specific action 1",
    "Specific action 2"
  ]
}}

Return ONLY valid JSON, no markdown code blocks or other text."""


# News/Intel mode prompts
NEWS_SYSTEM_PROMPT = """You are a tech intelligence analyst specializing in AI, machine learning, and open source ecosystems.

Your task is to analyze Reddit discussions and extract key news, developments, and insights that would be valuable to share with a technical community. Focus on:
1. New releases, launches, and announcements
2. Significant updates to popular tools/models
3. Emerging trends and technologies
4. Notable benchmarks and comparisons
5. Community sentiment and adoption patterns
6. Controversies or important debates

Be specific, cite sources, and prioritize recency and impact.
Output structured JSON that can be parsed programmatically."""


NEWS_USER_PROMPT = """Analyze the following Reddit data from "{focus_name}".

Focus Keywords: {keywords}

Here are {total_posts} posts from subreddits: {subreddits}

---
{posts_content}
---

Extract key intelligence and return a JSON object with this structure:
{{
  "executive_summary": "2-3 sentence overview of what's happening in the space right now",
  "top_stories": [
    {{
      "headline": "Concise news headline",
      "summary": "2-3 sentence summary of what happened",
      "reddit_url": "The full Reddit URL from the post (e.g. https://reddit.com/r/...)",
      "subreddit": "Where it was posted",
      "engagement": "Upvotes/comments as social proof",
      "importance": "high/medium/low",
      "category": "release/update/research/tool/discussion/drama",
      "tags": ["relevant", "tags"],
      "links": ["Any external URLs mentioned (GitHub, papers, announcements)"]
    }}
  ],
  "notable_releases": [
    {{
      "name": "Project/model name",
      "description": "What it is",
      "why_notable": "Why it matters",
      "reddit_url": "Reddit URL where this was discussed",
      "links": ["Project URL if mentioned"]
    }}
  ],
  "trending_discussions": [
    {{
      "topic": "What people are debating",
      "summary": "Key viewpoints",
      "sentiment": "positive/negative/mixed",
      "reddit_url": "Main discussion URL"
    }}
  ],
  "tools_mentioned": [
    {{
      "name": "Tool name",
      "mentions": "How many times/posts",
      "sentiment": "How people feel about it",
      "url": "Tool/project URL if available"
    }}
  ],
  "key_takeaways": [
    "Bullet point 1 - shareable insight",
    "Bullet point 2 - shareable insight"
  ]
}}

IMPORTANT: Include the actual Reddit URLs from each post (they look like https://reddit.com/r/subreddit/comments/...). These are provided in the "URL:" field of each post above.

Return ONLY valid JSON, no markdown code blocks or other text."""


def format_posts_for_analysis(posts: list[dict]) -> str:
    """Format posts for LLM consumption."""

    formatted = []
    for i, post in enumerate(posts, 1):
        entry = f"""
### Post {i}: {post["title"]}
- Subreddit: r/{post["subreddit"]}
- Upvotes: {post["upvotes"]} | Comments: {post["num_comments"]}
- Flair: {post.get("flair", "None")}
- URL: {post["url"]}

Content:
{post.get("selftext", "(no text)")[:1500]}
"""

        if post.get("comments"):
            entry += "\nTop Comments:\n"
            for j, comment in enumerate(post["comments"][:5], 1):
                entry += f"  {j}. [{comment['upvotes']} upvotes] {comment['body'][:300]}\n"

        formatted.append(entry)

    return "\n---\n".join(formatted)


def analyze_batch(
    posts: list[dict],
    scrape_data: dict,
    config: dict,
    batch_num: int = 1,
    total_batches: int = 1,
) -> dict:
    """Analyze a single batch of posts."""

    posts_content = format_posts_for_analysis(posts)
    mode = scrape_data.get("mode", "opportunities")

    if mode == "news":
        system_prompt = NEWS_SYSTEM_PROMPT
        user_prompt_template = NEWS_USER_PROMPT
    else:
        system_prompt = ANALYSIS_SYSTEM_PROMPT
        user_prompt_template = ANALYSIS_USER_PROMPT

    # Get unique subreddits in this batch
    batch_subreddits = list(set(p["subreddit"] for p in posts))

    prompt = user_prompt_template.format(
        focus_name=scrape_data["focus_name"],
        keywords=", ".join(scrape_data.get("keywords", [])),
        total_posts=len(posts),
        subreddits=", ".join(batch_subreddits),
        posts_content=posts_content,
    )

    print(f"  Batch {batch_num}/{total_batches}: Analyzing {len(posts)} posts...")

    content, reasoning = call_llm(
        prompt=prompt,
        system_prompt=system_prompt,
        config=config,
        json_mode=False,
    )

    # Parse JSON
    try:
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            return json.loads(content[json_start:json_end])
        else:
            return {"error": "Could not parse JSON", "raw_response": content[:500]}
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}", "raw_response": content[:500]}


def merge_batch_analyses(analyses: list[dict], mode: str = "opportunities") -> dict:
    """Merge multiple batch analyses into one."""

    if mode == "news":
        # News mode merging
        merged = {
            "executive_summary": "",
            "top_stories": [],
            "notable_releases": [],
            "trending_discussions": [],
            "tools_mentioned": [],
            "key_takeaways": [],
        }

        summaries = []
        for analysis in analyses:
            if "executive_summary" in analysis:
                summaries.append(analysis["executive_summary"])
            merged["top_stories"].extend(analysis.get("top_stories", []))
            merged["notable_releases"].extend(analysis.get("notable_releases", []))
            merged["trending_discussions"].extend(analysis.get("trending_discussions", []))
            merged["tools_mentioned"].extend(analysis.get("tools_mentioned", []))
            merged["key_takeaways"].extend(analysis.get("key_takeaways", []))

        # Combine summaries
        if summaries:
            merged["executive_summary"] = " ".join(summaries[:3])  # Take first 3

        # Deduplicate top stories by headline
        seen_headlines = set()
        unique_stories = []
        for story in merged["top_stories"]:
            headline = story.get("headline", "").lower().strip()
            if headline and headline not in seen_headlines:
                seen_headlines.add(headline)
                unique_stories.append(story)
        merged["top_stories"] = unique_stories[:15]  # Keep top 15

        # Deduplicate releases by name
        seen_releases = set()
        unique_releases = []
        for release in merged["notable_releases"]:
            name = release.get("name", "").lower().strip()
            if name and name not in seen_releases:
                seen_releases.add(name)
                unique_releases.append(release)
        merged["notable_releases"] = unique_releases[:10]

        # Deduplicate tools
        seen_tools = set()
        unique_tools = []
        for tool in merged["tools_mentioned"]:
            name = tool.get("name", "").lower().strip()
            if name and name not in seen_tools:
                seen_tools.add(name)
                unique_tools.append(tool)
        merged["tools_mentioned"] = unique_tools[:15]

        # Dedupe takeaways
        merged["key_takeaways"] = list(set(merged["key_takeaways"]))[:10]

    else:
        # Opportunities mode merging
        merged = {
            "executive_summary": "",
            "opportunities": [],
            "pain_points": [],
            "market_insights": [],
            "trending_topics": [],
            "recommended_actions": [],
        }

        summaries = []
        for analysis in analyses:
            if "executive_summary" in analysis:
                summaries.append(analysis["executive_summary"])
            merged["opportunities"].extend(analysis.get("opportunities", []))
            merged["pain_points"].extend(analysis.get("pain_points", []))
            merged["market_insights"].extend(analysis.get("market_insights", []))
            merged["trending_topics"].extend(analysis.get("trending_topics", []))
            merged["recommended_actions"].extend(analysis.get("recommended_actions", []))

        if summaries:
            merged["executive_summary"] = " ".join(summaries[:3])

        # Deduplicate opportunities by title
        seen_titles = set()
        unique_opps = []
        for opp in merged["opportunities"]:
            title = opp.get("title", "").lower().strip()
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_opps.append(opp)
        merged["opportunities"] = unique_opps

        # Deduplicate pain points
        seen_problems = set()
        unique_pains = []
        for pain in merged["pain_points"]:
            problem = pain.get("problem", "").lower().strip()
            if problem and problem not in seen_problems:
                seen_problems.add(problem)
                unique_pains.append(pain)
        merged["pain_points"] = unique_pains

        # Dedupe trending topics and actions
        merged["trending_topics"] = list(set(merged["trending_topics"]))[:20]
        merged["recommended_actions"] = list(dict.fromkeys(merged["recommended_actions"]))[:10]

    return merged


def analyze_scrape_data(
    scrape_data: dict,
    config: Optional[dict] = None,
    batch_size: int = 50,
    progress_callback: Optional[callable] = None,
) -> dict:
    """Analyze scraped data using the LLM, with batching for large datasets."""

    if config is None:
        config = load_config()

    posts = scrape_data["posts"]
    total_posts = len(posts)
    mode = scrape_data.get("mode", "opportunities")

    print(f"Analyzing {total_posts} posts...")

    # If small enough, analyze in one go
    if total_posts <= batch_size:
        analysis = analyze_batch(posts, scrape_data, config, 1, 1)
        if progress_callback:
            progress_callback(100, "Analysis complete")
    else:
        # Split into batches
        batches = [posts[i : i + batch_size] for i in range(0, total_posts, batch_size)]
        total_batches = len(batches)
        print(f"Splitting into {total_batches} batches of ~{batch_size} posts each")

        batch_analyses = []
        for i, batch in enumerate(batches, 1):
            if progress_callback:
                pct = int((i - 1) / total_batches * 100)
                progress_callback(pct, f"Analyzing batch {i}/{total_batches}")

            batch_result = analyze_batch(batch, scrape_data, config, i, total_batches)
            if "error" not in batch_result:
                batch_analyses.append(batch_result)
            else:
                print(f"  Batch {i} had error: {batch_result.get('error')}")

        # Merge all batch results
        if batch_analyses:
            print(f"Merging {len(batch_analyses)} batch results...")
            analysis = merge_batch_analyses(batch_analyses, mode)
        else:
            analysis = {"error": "All batches failed", "opportunities": [], "pain_points": []}

        if progress_callback:
            progress_callback(100, "Analysis complete")

    # Build the report
    report = {
        "id": f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "focus_area": scrape_data["focus_area"],
        "focus_name": scrape_data["focus_name"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_scraped_at": scrape_data["scraped_at"],
        "subreddits_analyzed": scrape_data["subreddits"],
        "posts_analyzed": total_posts,
        "analysis": analysis,
        "metadata": {
            "model": config.get("llm", {}).get("model", "unknown"),
            "source_file": scrape_data.get("source_file", "unknown"),
            "batches_used": (total_posts + batch_size - 1) // batch_size
            if total_posts > batch_size
            else 1,
        },
    }

    return report


def get_report_path(focus_area: str, output_dir: Optional[Path] = None) -> Path:
    """Get the canonical path for a focus area's report."""
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "reports"
    return output_dir / f"report_{focus_area}.json"


def load_existing_report(focus_area: str, output_dir: Optional[Path] = None) -> Optional[dict]:
    """Load existing report for a focus area if it exists."""
    path = get_report_path(focus_area, output_dir)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def merge_reports(existing: dict, new_report: dict) -> dict:
    """Merge new analysis into existing report, deduplicating items."""

    existing_analysis = existing.get("analysis", {})
    new_analysis = new_report.get("analysis", {})

    # Detect if this is news mode (has top_stories) or opportunities mode
    is_news_mode = "top_stories" in new_analysis or "top_stories" in existing_analysis

    # Helper for deduplication by field similarity
    def is_duplicate(new_item, existing_list, field):
        new_val = new_item.get(field, "").lower().strip()
        if not new_val:
            return False
        for existing in existing_list:
            existing_val = existing.get(field, "").lower().strip()
            if new_val == existing_val:
                return True
            new_words = set(new_val.split())
            existing_words = set(existing_val.split())
            if new_words and existing_words:
                overlap = len(new_words & existing_words) / max(len(new_words), len(existing_words))
                if overlap > 0.7:
                    return True
        return False

    def merge_list(existing_list, new_list, dedup_field, limit=None):
        """Merge two lists with deduplication."""
        merged = list(existing_list)
        new_count = 0
        for item in new_list:
            if not is_duplicate(item, merged, dedup_field):
                item["added_at"] = new_report.get(
                    "generated_at", datetime.now(timezone.utc).isoformat()
                )
                merged.append(item)
                new_count += 1
        if limit:
            merged = merged[:limit]
        return merged, new_count

    new_item_count = 0
    new_secondary_count = 0

    if is_news_mode:
        # NEWS MODE: Merge news-specific fields
        merged_stories, new_stories = merge_list(
            existing_analysis.get("top_stories", []),
            new_analysis.get("top_stories", []),
            "headline",
            limit=30,
        )
        merged_releases, new_releases = merge_list(
            existing_analysis.get("notable_releases", []),
            new_analysis.get("notable_releases", []),
            "name",
            limit=20,
        )
        merged_discussions, _ = merge_list(
            existing_analysis.get("trending_discussions", []),
            new_analysis.get("trending_discussions", []),
            "topic",
            limit=20,
        )
        merged_tools, _ = merge_list(
            existing_analysis.get("tools_mentioned", []),
            new_analysis.get("tools_mentioned", []),
            "name",
            limit=25,
        )

        # Merge key takeaways (simple dedup)
        existing_takeaways = existing_analysis.get("key_takeaways", [])
        new_takeaways = new_analysis.get("key_takeaways", [])
        merged_takeaways = list(existing_takeaways)
        for t in new_takeaways:
            if t not in merged_takeaways:
                merged_takeaways.append(t)
        merged_takeaways = merged_takeaways[:15]

        analysis = {
            "executive_summary": new_analysis.get(
                "executive_summary", existing_analysis.get("executive_summary", "")
            ),
            "top_stories": merged_stories,
            "notable_releases": merged_releases,
            "trending_discussions": merged_discussions,
            "tools_mentioned": merged_tools,
            "key_takeaways": merged_takeaways,
        }
        new_item_count = new_stories
        new_secondary_count = new_releases
    else:
        # OPPORTUNITIES MODE: Merge opportunity-specific fields
        merged_opps, new_opps = merge_list(
            existing_analysis.get("opportunities", []),
            new_analysis.get("opportunities", []),
            "title",
        )
        merged_pains, new_pains = merge_list(
            existing_analysis.get("pain_points", []), new_analysis.get("pain_points", []), "problem"
        )

        # Merge insights
        existing_insights = existing_analysis.get("market_insights", [])
        new_insights = new_analysis.get("market_insights", [])
        merged_insights = list(existing_insights)
        existing_insight_texts = {i.get("insight", "").lower() for i in existing_insights}
        for insight in new_insights:
            if insight.get("insight", "").lower() not in existing_insight_texts:
                merged_insights.append(insight)

        analysis = {
            "executive_summary": new_analysis.get(
                "executive_summary", existing_analysis.get("executive_summary", "")
            ),
            "opportunities": merged_opps,
            "pain_points": merged_pains,
            "market_insights": merged_insights,
            "trending_topics": list(
                set(
                    existing_analysis.get("trending_topics", [])
                    + new_analysis.get("trending_topics", [])
                )
            ),
            "recommended_actions": new_analysis.get(
                "recommended_actions", existing_analysis.get("recommended_actions", [])
            ),
        }
        new_item_count = new_opps
        new_secondary_count = new_pains

    # Build scan history
    scan_history = existing.get("scan_history", [])
    scan_history.append(
        {
            "scanned_at": new_report.get("generated_at"),
            "posts_analyzed": new_report.get("posts_analyzed", 0),
            "new_items": new_item_count,
            "new_secondary": new_secondary_count,
            "subreddits": new_report.get("subreddits_analyzed", []),
        }
    )

    # Build merged report
    merged = {
        "id": f"report_{existing.get('focus_area', 'unknown')}",
        "focus_area": existing.get("focus_area"),
        "focus_name": existing.get("focus_name"),
        "created_at": existing.get("created_at", existing.get("generated_at")),
        "updated_at": new_report.get("generated_at"),
        "total_scans": len(scan_history),
        "subreddits_analyzed": list(
            set(existing.get("subreddits_analyzed", []) + new_report.get("subreddits_analyzed", []))
        ),
        "total_posts_analyzed": existing.get(
            "total_posts_analyzed", existing.get("posts_analyzed", 0)
        )
        + new_report.get("posts_analyzed", 0),
        "analysis": analysis,
        "scan_history": scan_history,
        "metadata": new_report.get("metadata", {}),
    }

    return merged, new_item_count, new_secondary_count


def save_report(
    report: dict, output_dir: Optional[Path] = None, merge: bool = True
) -> tuple[Path, int, int]:
    """Save the analysis report, optionally merging with existing."""

    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "reports"

    output_dir.mkdir(parents=True, exist_ok=True)

    focus_area = report.get("focus_area", "unknown")
    new_opps = 0
    new_pains = 0

    if merge:
        existing = load_existing_report(focus_area, output_dir)
        if existing:
            report, new_opps, new_pains = merge_reports(existing, report)
            print(
                f"Merged with existing report: +{new_opps} opportunities, +{new_pains} pain points"
            )
        else:
            # First report for this focus area
            report["id"] = f"report_{focus_area}"
            report["created_at"] = report.get("generated_at")
            report["updated_at"] = report.get("generated_at")
            report["total_scans"] = 1
            report["total_posts_analyzed"] = report.get("posts_analyzed", 0)
            report["scan_history"] = [
                {
                    "scanned_at": report.get("generated_at"),
                    "posts_analyzed": report.get("posts_analyzed", 0),
                    "new_opportunities": len(report.get("analysis", {}).get("opportunities", [])),
                    "new_pain_points": len(report.get("analysis", {}).get("pain_points", [])),
                    "subreddits": report.get("subreddits_analyzed", []),
                }
            ]
            new_opps = len(report.get("analysis", {}).get("opportunities", []))
            new_pains = len(report.get("analysis", {}).get("pain_points", []))

    # Always save to canonical path for focus area
    output_path = get_report_path(focus_area, output_dir)

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Saved report to {output_path}")
    return output_path, new_opps, new_pains


def get_latest_scrape(focus_area: str, data_dir: Optional[Path] = None) -> Optional[Path]:
    """Get the most recent scrape file for a focus area."""

    if data_dir is None:
        data_dir = Path(__file__).parent.parent / "data"

    pattern = f"scrape_{focus_area}_*.json"
    files = sorted(data_dir.glob(pattern), reverse=True)

    return files[0] if files else None


def load_scrape_data(path: Path) -> dict:
    """Load scrape data from a file."""
    with open(path) as f:
        data = json.load(f)
    data["source_file"] = str(path)
    return data


if __name__ == "__main__":
    import sys

    focus = sys.argv[1] if len(sys.argv) > 1 else "saas_opportunities"

    # Find latest scrape
    scrape_file = get_latest_scrape(focus)
    if not scrape_file:
        print(f"No scrape data found for {focus}. Run scraper first.")
        sys.exit(1)

    print(f"Loading scrape data from {scrape_file}")
    scrape_data = load_scrape_data(scrape_file)

    print("Analyzing with LLM...")
    report = analyze_scrape_data(scrape_data)

    save_report(report)
    print("Done!")
