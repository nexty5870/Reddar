"""Reddit Scraper - Fetches posts and comments from subreddits."""

import json
import random
import time
import httpx
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import yaml


# Rate limiting defaults
DEFAULT_DELAY_BETWEEN_REQUESTS = 3.0  # seconds
DEFAULT_DELAY_BETWEEN_SUBREDDITS = 6.0  # seconds
MAX_RETRIES = 3
BACKOFF_FACTOR = 2  # exponential backoff multiplier


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def rate_limit_delay(base_delay: float = DEFAULT_DELAY_BETWEEN_REQUESTS) -> None:
    """Sleep with jitter to avoid predictable request patterns."""
    jitter = random.uniform(0.5, 1.5)
    time.sleep(base_delay * jitter)


def fetch_with_retry(
    url: str,
    headers: dict,
    params: dict,
    max_retries: int = MAX_RETRIES,
) -> Optional[dict]:
    """Fetch URL with exponential backoff retry on rate limits."""

    for attempt in range(max_retries + 1):
        try:
            response = httpx.get(url, headers=headers, params=params, timeout=30, follow_redirects=True)

            # Handle rate limiting
            if response.status_code == 429:
                if attempt < max_retries:
                    # Exponential backoff with jitter
                    wait_time = (BACKOFF_FACTOR ** attempt) * 10 + random.uniform(1, 5)
                    print(f"  Rate limited (429). Waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"  Rate limited (429). Max retries exceeded, skipping.")
                    return None

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            print(f"  HTTP error: {e}")
            return None
        except Exception as e:
            print(f"  Error: {e}")
            return None

    return None


def fetch_subreddit(
    subreddit: str, limit: int = 25, min_upvotes: int = 5, user_agent: str = "RedditIntel/1.0"
) -> list[dict]:
    """Fetch posts from a subreddit using Reddit's JSON API."""

    url = f"https://www.reddit.com/r/{subreddit}.json"
    headers = {"User-Agent": user_agent}
    params = {"limit": min(limit * 2, 100)}  # Fetch extra to filter

    data = fetch_with_retry(url, headers, params)
    if data is None:
        print(f"  Failed to fetch r/{subreddit}")
        return []

    posts = []
    for child in data.get("data", {}).get("children", []):
        post = child.get("data", {})

        # Filter by upvotes
        if post.get("ups", 0) < min_upvotes:
            continue

        # Skip stickied/pinned posts
        if post.get("stickied"):
            continue

        posts.append(
            {
                "id": post.get("id"),
                "subreddit": subreddit,
                "title": post.get("title"),
                "selftext": post.get("selftext", "")[:2000],  # Truncate long posts
                "author": post.get("author"),
                "upvotes": post.get("ups"),
                "num_comments": post.get("num_comments"),
                "url": f"https://reddit.com{post.get('permalink')}",
                "created_utc": post.get("created_utc"),
                "created_date": datetime.fromtimestamp(
                    post.get("created_utc", 0), tz=timezone.utc
                ).isoformat(),
                "flair": post.get("link_flair_text"),
            }
        )

        if len(posts) >= limit:
            break

    return posts


def fetch_comments(
    subreddit: str, post_id: str, max_comments: int = 10, user_agent: str = "RedditIntel/1.0"
) -> list[dict]:
    """Fetch top comments for a post."""

    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
    headers = {"User-Agent": user_agent}
    params = {"limit": max_comments, "sort": "top"}

    data = fetch_with_retry(url, headers, params)
    if data is None:
        return []

    comments = []
    if isinstance(data, list) and len(data) > 1:
        for child in data[1].get("data", {}).get("children", [])[:max_comments]:
            if child.get("kind") != "t1":
                continue
            comment = child.get("data", {})
            comments.append(
                {
                    "id": comment.get("id"),
                    "body": comment.get("body", "")[:1000],
                    "author": comment.get("author"),
                    "upvotes": comment.get("ups"),
                }
            )

    return comments


def scrape_focus_area(focus_area: str, config: Optional[dict] = None) -> dict:
    """Scrape all subreddits for a focus area."""

    if config is None:
        config = load_config()

    focus_config = config["focus_areas"].get(focus_area)
    if not focus_config:
        raise ValueError(f"Unknown focus area: {focus_area}")

    scraper_config = config.get("scraper", {})
    user_agent = scraper_config.get("user_agent", "RedditIntel/1.0")
    posts_per_sub = scraper_config.get("posts_per_subreddit", 25)
    include_comments = scraper_config.get("include_comments", True)
    max_comments = scraper_config.get("max_comments_per_post", 10)
    min_upvotes = scraper_config.get("min_upvotes", 5)
    delay_between_requests = scraper_config.get("delay_between_requests", DEFAULT_DELAY_BETWEEN_REQUESTS)
    delay_between_subreddits = scraper_config.get("delay_between_subreddits", DEFAULT_DELAY_BETWEEN_SUBREDDITS)

    all_posts = []
    total_subreddits = len(focus_config["subreddits"])

    for idx, subreddit in enumerate(focus_config["subreddits"], 1):
        print(f"Scraping r/{subreddit}... ({idx}/{total_subreddits})")
        posts = fetch_subreddit(
            subreddit, limit=posts_per_sub, min_upvotes=min_upvotes, user_agent=user_agent
        )

        if include_comments and posts:
            print(f"  Fetching comments for {len(posts)} posts...")
            for post in posts:
                # Rate limit between comment fetches
                rate_limit_delay(delay_between_requests)
                post["comments"] = fetch_comments(
                    subreddit, post["id"], max_comments=max_comments, user_agent=user_agent
                )

        all_posts.extend(posts)
        print(f"  Got {len(posts)} posts from r/{subreddit}")

        # Rate limit between subreddits (longer delay)
        if idx < total_subreddits:
            rate_limit_delay(delay_between_subreddits)

    result = {
        "focus_area": focus_area,
        "focus_name": focus_config["name"],
        "focus_description": focus_config["description"],
        "keywords": focus_config.get("keywords", []),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "subreddits": focus_config["subreddits"],
        "total_posts": len(all_posts),
        "posts": all_posts,
    }

    return result


def save_scrape_data(data: dict, output_dir: Optional[Path] = None) -> Path:
    """Save scraped data to a JSON file."""

    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "data"

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scrape_{data['focus_area']}_{timestamp}.json"
    output_path = output_dir / filename

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved scrape data to {output_path}")
    return output_path


def get_available_subreddits(config: Optional[dict] = None) -> dict:
    """Get all available subreddits grouped by focus area."""

    if config is None:
        config = load_config()

    result = {}
    for area_id, area_config in config["focus_areas"].items():
        result[area_id] = {
            "name": area_config["name"],
            "description": area_config["description"],
            "subreddits": area_config["subreddits"],
        }

    return result


if __name__ == "__main__":
    import sys

    focus = sys.argv[1] if len(sys.argv) > 1 else "saas_opportunities"

    print(f"Scraping focus area: {focus}")
    data = scrape_focus_area(focus)
    save_scrape_data(data)
    print(f"Done! Scraped {data['total_posts']} posts.")
