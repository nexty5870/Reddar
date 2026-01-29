"""Chat functionality for discussing report insights with LLM."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from analyzer import call_llm, load_config

DATA_DIR = Path(__file__).parent.parent / "data"
CHATS_FILE = DATA_DIR / "chats.json"


def load_chats() -> dict:
    """Load all chat conversations from disk."""
    if CHATS_FILE.exists():
        with open(CHATS_FILE) as f:
            return json.load(f)
    return {"conversations": {}}


def save_chats(data: dict) -> None:
    """Save chat conversations to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHATS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_conversation(report_id: str) -> Optional[dict]:
    """Get conversation history for a specific report."""
    chats = load_chats()
    return chats["conversations"].get(report_id)


def add_message(report_id: str, role: str, content: str) -> dict:
    """Add a message to a conversation."""
    chats = load_chats()

    if report_id not in chats["conversations"]:
        chats["conversations"][report_id] = {
            "report_id": report_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "messages": [],
        }

    message = {
        "id": f"msg_{uuid.uuid4().hex[:8]}",
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    chats["conversations"][report_id]["messages"].append(message)
    chats["conversations"][report_id]["updated_at"] = message["timestamp"]

    save_chats(chats)
    return message


def clear_conversation(report_id: str) -> bool:
    """Clear conversation history for a specific report."""
    chats = load_chats()
    if report_id in chats["conversations"]:
        del chats["conversations"][report_id]
        save_chats(chats)
        return True
    return False


def format_report_context(report: dict) -> str:
    """Format report data into system prompt context."""
    analysis = report.get("analysis", {})
    is_news_mode = "top_stories" in analysis

    if is_news_mode:
        return _format_news_context(report, analysis)
    else:
        return _format_opportunities_context(report, analysis)


def _format_opportunities_context(report: dict, analysis: dict) -> str:
    """Format opportunities-mode report for context."""
    # Format opportunities
    opps = analysis.get("opportunities", [])
    opps_text = "\n".join(
        [
            f"- **{o['title']}**: {o.get('description', '')[:200]}... "
            f"(Potential: {o.get('potential', 'unknown')}, Difficulty: {o.get('difficulty', 'unknown')})"
            for o in opps[:10]
        ]
    )

    # Format pain points
    pains = analysis.get("pain_points", [])
    pains_text = "\n".join(
        [
            f"- **{p['problem']}**: Severity {p.get('severity', 'unknown')}, "
            f"Current solutions: {p.get('current_solutions', 'N/A')[:100]}..."
            for p in pains[:10]
        ]
    )

    # Format insights
    insights = analysis.get("market_insights", [])
    insights_text = "\n".join([f"- {i['insight']}" for i in insights[:5]])

    # Format recommended actions
    actions = analysis.get("recommended_actions", [])
    actions_text = "\n".join([f"- {a}" for a in actions[:5]])

    subreddits = report.get("subreddits_analyzed", [])

    return f"""You are an intelligent assistant for the Reddar Reddit Intelligence platform. You help users understand and explore business opportunity reports extracted from Reddit discussions.

## Report: {report.get('focus_name', 'Unknown')}
**Last Updated:** {report.get('updated_at', report.get('generated_at', 'Unknown'))[:16]}
**Posts Analyzed:** {report.get('total_posts_analyzed', report.get('posts_analyzed', 0))}
**Subreddits:** {', '.join(subreddits[:8])}{'...' if len(subreddits) > 8 else ''}

## Executive Summary
{analysis.get('executive_summary', 'No summary available.')}

## Opportunities ({len(opps)} identified)
{opps_text or 'None identified yet.'}

## Pain Points ({len(pains)} identified)
{pains_text or 'None identified yet.'}

## Market Insights
{insights_text or 'None available.'}

## Trending Topics
{', '.join(analysis.get('trending_topics', [])[:10]) or 'None identified.'}

## Recommended Actions
{actions_text or 'None available.'}

---
You have full knowledge of this report. Answer questions thoroughly, cite specific opportunities or pain points when relevant, and provide actionable business insights. If asked about something not covered in the report, acknowledge that and offer your best general guidance."""


def _format_news_context(report: dict, analysis: dict) -> str:
    """Format news-mode report for context."""
    stories = analysis.get("top_stories", [])
    stories_text = "\n".join(
        [
            f"- **{s['headline']}** [{s.get('category', 'general')}]: {s.get('summary', '')[:150]}..."
            for s in stories[:10]
        ]
    )

    releases = analysis.get("notable_releases", [])
    releases_text = "\n".join(
        [f"- **{r['name']}**: {r.get('description', 'N/A')[:100]}..." for r in releases[:8]]
    )

    discussions = analysis.get("trending_discussions", [])
    discussions_text = "\n".join(
        [
            f"- **{d.get('topic', 'Unknown')}**: {d.get('summary', '')[:100]}... (Sentiment: {d.get('sentiment', 'neutral')})"
            for d in discussions[:5]
        ]
    )

    tools = analysis.get("tools_mentioned", [])
    tools_text = "\n".join(
        [f"- **{t['name']}**: {t.get('mentions', 'N/A')} mentions, sentiment: {t.get('sentiment', 'neutral')}" for t in tools[:10]]
    )

    takeaways = analysis.get("key_takeaways", [])
    takeaways_text = "\n".join([f"- {t}" for t in takeaways[:5]])

    return f"""You are an intelligent assistant for the Reddar Reddit Intelligence platform. You help users understand AI, ML, and open-source news and developments extracted from Reddit discussions.

## Report: {report.get('focus_name', 'Unknown')}
**Last Updated:** {report.get('updated_at', report.get('generated_at', 'Unknown'))[:16]}
**Posts Analyzed:** {report.get('total_posts_analyzed', report.get('posts_analyzed', 0))}

## Executive Summary
{analysis.get('executive_summary', 'No summary available.')}

## Top Stories ({len(stories)} found)
{stories_text or 'None identified yet.'}

## Notable Releases ({len(releases)} found)
{releases_text or 'None identified yet.'}

## Trending Discussions
{discussions_text or 'None identified yet.'}

## Tools & Projects Mentioned ({len(tools)} found)
{tools_text or 'None mentioned.'}

## Key Takeaways
{takeaways_text or 'None available.'}

---
You have full knowledge of this news report. Help users understand the latest developments, compare tools and models, identify trends, and provide context about the AI/ML ecosystem. Cite specific stories or releases when relevant."""


def build_messages_for_llm(report: dict, conversation: Optional[dict], new_message: str) -> tuple[str, str]:
    """Build system prompt and user prompt for LLM call.

    Returns (system_prompt, user_prompt) tuple.
    """
    system_prompt = format_report_context(report)

    # Build conversation history as part of user prompt
    history_parts = []
    if conversation and conversation.get("messages"):
        # Keep last 20 messages to stay within context limits
        recent_messages = conversation["messages"][-20:]
        for msg in recent_messages:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            history_parts.append(f"{role_label}: {msg['content']}")

    # Add the new message
    history_parts.append(f"User: {new_message}")
    history_parts.append("Assistant:")

    user_prompt = "\n\n".join(history_parts)

    return system_prompt, user_prompt


def chat_with_report(
    report_id: str, report: dict, user_message: str, config: Optional[dict] = None
) -> tuple[dict, dict]:
    """Send a message and get LLM response.

    Returns (user_message_obj, assistant_message_obj) tuple.
    """
    if config is None:
        config = load_config()

    # Save user message first
    user_msg = add_message(report_id, "user", user_message)

    # Get updated conversation (includes the message we just added)
    conversation = get_conversation(report_id)

    # Build prompts - exclude the message we just added from history
    # since we'll add it explicitly
    temp_conv = {
        "messages": conversation["messages"][:-1]  # Exclude last (current) message
    } if conversation and len(conversation.get("messages", [])) > 1 else None

    system_prompt, user_prompt = build_messages_for_llm(report, temp_conv, user_message)

    # Call LLM
    response_content, reasoning = call_llm(
        prompt=user_prompt,
        system_prompt=system_prompt,
        config=config,
        json_mode=False,
    )

    # Save assistant response
    assistant_msg = add_message(report_id, "assistant", response_content)

    return user_msg, assistant_msg
