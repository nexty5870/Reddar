#!/bin/bash
# Reddit Intelligence Agent Runner

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

case "$1" in
    agent)
        # Run the agent for a focus area (starts dashboard after)
        shift
        python3 src/agent.py "$@"
        ;;
    web)
        # Start just the web dashboard
        python3 src/agent.py --web-only
        ;;
    scrape)
        # Just scrape, don't analyze
        shift
        python3 src/scraper.py "$@"
        ;;
    analyze)
        # Just analyze existing scrape data (no dashboard)
        shift
        python3 src/analyzer.py "$@"
        ;;
    cron)
        # Run agent without dashboard (for cron jobs)
        shift
        python3 src/agent.py --no-web "$@"
        ;;
    list)
        # List focus areas
        python3 src/agent.py --list
        ;;
    install)
        # Install dependencies
        pip3 install -r requirements.txt
        ;;
    *)
        echo "Reddit Intelligence Agent"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  agent [focus_area]  Run full pipeline + start dashboard"
        echo "  web                 Start web dashboard only"
        echo "  scrape [focus]      Just scrape Reddit data"
        echo "  analyze [focus]     Analyze existing scrape data"
        echo "  cron [focus]        Run agent without dashboard (for cron)"
        echo "  list                List available focus areas"
        echo "  install             Install dependencies"
        echo ""
        echo "Examples:"
        echo "  $0 agent saas_opportunities  # Scrape, analyze, open dashboard"
        echo "  $0 agent dev_tools --no-web  # Scrape & analyze only"
        echo "  $0 web                       # Just view existing reports"
        echo "  $0 cron ai_ml                # For cron jobs"
        ;;
esac
