#!/bin/bash
# Reddit Intelligence Agent - Unified Launcher
# Checks model, runs agent, and starts dashboard with real-time token tracking

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  Reddit Intelligence Agent${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
}

check_model() {
    echo -e "${YELLOW}Checking GLM-4.7-Flash...${NC}"
    if curl -s http://localhost:8000/v1/models 2>/dev/null | grep -q "glm-4.7-flash"; then
        echo -e "${GREEN}  Model is running on :8000${NC}"
        return 0
    else
        echo -e "${RED}  Model not running!${NC}"
        echo -e "${YELLOW}  Start it with: curl -X POST http://localhost:8082/launch/glm-4.7-flash${NC}"
        return 1
    fi
}

run_agent() {
    local focus="${1:-saas_opportunities}"
    
    echo ""
    echo -e "${YELLOW}Running agent for: $focus${NC}"
    echo ""
    
    cd "$SCRIPT_DIR"
    python3 src/agent.py --no-web "$focus"
}

start_dashboard() {
    echo ""
    echo -e "${YELLOW}Starting dashboard...${NC}"
    
    cd "$SCRIPT_DIR"
    python3 web/app.py &
    DASHBOARD_PID=$!
    
    sleep 2
    
    if kill -0 $DASHBOARD_PID 2>/dev/null; then
        echo -e "${GREEN}  Dashboard running on :8501${NC}"
        echo ""
        echo -e "${BLUE}============================================${NC}"
        echo -e "  ${GREEN}Dashboard:${NC}  http://localhost:8501"
        echo -e "${BLUE}============================================${NC}"
        echo ""
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        
        # Open browser
        if command -v xdg-open &> /dev/null; then
            xdg-open "http://localhost:8501" 2>/dev/null &
        fi
        
        # Wait for dashboard
        wait $DASHBOARD_PID
    else
        echo -e "${RED}  Dashboard failed to start${NC}"
        return 1
    fi
}

stop_all() {
    echo ""
    echo -e "${YELLOW}Stopping dashboard...${NC}"
    pkill -f "python3 web/app.py" 2>/dev/null || true
    echo -e "${GREEN}Done${NC}"
}

trap stop_all EXIT

# Main
print_header

case "${1:-}" in
    "")
        # Default: check model, run default agent, start dashboard
        check_model || exit 1
        run_agent "saas_opportunities"
        start_dashboard
        ;;
    
    agent)
        # Run agent only (no dashboard)
        shift
        check_model || exit 1
        run_agent "${1:-saas_opportunities}"
        echo ""
        echo -e "${GREEN}Done! View reports: ./start.sh web${NC}"
        ;;
    
    dashboard|web)
        # Dashboard only
        start_dashboard
        ;;
    
    all)
        # Run all focus areas then start dashboard
        check_model || exit 1
        
        for focus in saas_opportunities dev_tools ai_ml; do
            run_agent "$focus"
            echo ""
            sleep 5  # Rate limit between runs
        done
        
        start_dashboard
        ;;
    
    status)
        echo "Service Status:"
        echo ""
        
        if curl -s http://localhost:8000/v1/models 2>/dev/null | grep -q "glm-4.7-flash"; then
            echo -e "  SGLang (GLM-4.7):  ${GREEN}Running${NC} on :8000"
        else
            echo -e "  SGLang (GLM-4.7):  ${RED}Not running${NC}"
        fi
        
        if curl -s http://localhost:8501/ > /dev/null 2>&1; then
            echo -e "  Reddit Dashboard:  ${GREEN}Running${NC} on :8501"
        else
            echo -e "  Reddit Dashboard:  ${RED}Not running${NC}"
        fi
        
        # Show token usage summary
        if [[ -f "$SCRIPT_DIR/data/usage.json" ]]; then
            echo ""
            echo "Token Usage:"
            python3 -c "
import json
with open('$SCRIPT_DIR/data/usage.json') as f:
    data = json.load(f)
totals = data.get('totals', {})
print(f\"  Requests: {totals.get('requests', 0)}\")
print(f\"  Total tokens: {totals.get('total_tokens', 0):,}\")
print(f\"  Prompt: {totals.get('prompt_tokens', 0):,} | Completion: {totals.get('completion_tokens', 0):,}\")
"
        fi
        echo ""
        ;;
    
    stop)
        pkill -f "python3 web/app.py" 2>/dev/null && echo "Stopped dashboard" || true
        ;;
    
    list)
        python3 src/agent.py --list
        ;;
    
    reset-usage)
        rm -f "$SCRIPT_DIR/data/usage.json"
        echo "Token usage reset"
        ;;
    
    help|--help|-h)
        echo "Usage: $0 [command] [options]"
        echo ""
        echo "Commands:"
        echo "  (none)              Run default agent + start dashboard"
        echo "  <focus_area>        Run specific focus area + dashboard"
        echo "  agent [focus]       Run agent only (no dashboard)"
        echo "  all                 Run all focus areas + dashboard"
        echo "  web, dashboard      Start dashboard only"
        echo "  status              Show service status"
        echo "  list                List available focus areas"
        echo "  stop                Stop dashboard"
        echo "  reset-usage         Reset token usage stats"
        echo ""
        echo "Focus areas: saas_opportunities, dev_tools, ai_ml"
        echo ""
        echo "Examples:"
        echo "  $0                  # Run saas scan + open dashboard"
        echo "  $0 dev_tools        # Scan dev_tools + open dashboard"
        echo "  $0 agent ai_ml      # Just scan ai_ml (no dashboard)"
        echo "  $0 all              # Scan everything + open dashboard"
        echo "  $0 web              # Just view existing reports"
        ;;
    
    *)
        # Assume it's a focus area
        check_model || exit 1
        run_agent "$1"
        start_dashboard
        ;;
esac
