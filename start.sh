#!/bin/bash
# Reddit Intelligence Agent - Unified Launcher
# Supports multiple LLM providers: Ollama, SGLang, vLLM, OpenAI-compatible

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Detect Python environment - try system first, fall back to venv
detect_python() {
    # Check if system Python has required packages
    if python3 -c "import yaml, flask, httpx" 2>/dev/null; then
        PYTHON="python3"
        return 0
    fi

    # Try venv if it exists
    if [[ -f "$SCRIPT_DIR/venv/bin/python" ]]; then
        if "$SCRIPT_DIR/venv/bin/python" -c "import yaml, flask, httpx" 2>/dev/null; then
            PYTHON="$SCRIPT_DIR/venv/bin/python"
            return 0
        fi
    fi

    # No working Python found
    echo -e "${RED}Error: Required Python packages not found${NC}"
    echo -e "${YELLOW}Install dependencies with:${NC}"
    echo "  python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    return 1
}

# Initialize Python
detect_python || exit 1

print_header() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  Reddit Intelligence Agent${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
}

# Read LLM config using Python (handles YAML properly)
get_llm_config() {
    $PYTHON -c "
import yaml
from pathlib import Path

config_path = Path('$SCRIPT_DIR/config.yaml')
if not config_path.exists():
    print('provider=openai-compatible')
    print('base_url=http://localhost:8000/v1')
    print('model=default')
    exit(0)

with open(config_path) as f:
    config = yaml.safe_load(f)

llm = config.get('llm', {})
provider = llm.get('provider', 'openai-compatible')

# Provider presets
presets = {
    'ollama': {'base_url': 'http://localhost:11434/v1', 'default_model': 'llama3.2'},
    'sglang': {'base_url': 'http://localhost:8000/v1', 'default_model': 'default'},
    'vllm': {'base_url': 'http://localhost:8000/v1', 'default_model': 'default'},
    'openai': {'base_url': 'https://api.openai.com/v1', 'default_model': 'gpt-4o-mini'},
    'openai-compatible': {'base_url': 'http://localhost:8000/v1', 'default_model': 'default'},
}

preset = presets.get(provider, presets['openai-compatible'])
base_url = llm.get('base_url', preset['base_url'])
model = llm.get('model', preset.get('default_model', 'default'))

default_focus = config.get('default_focus', 'saas_opportunities')

print(f'provider={provider}')
print(f'base_url={base_url}')
print(f'model={model}')
print(f'default_focus={default_focus}')
"
}

# Load config into variables
load_config() {
    eval "$(get_llm_config)"
}

check_model() {
    load_config

    echo -e "${YELLOW}Checking LLM endpoint...${NC}"
    echo -e "  Provider: ${CYAN}${provider}${NC}"
    echo -e "  Model: ${CYAN}${model}${NC}"
    echo -e "  Endpoint: ${CYAN}${base_url}${NC}"

    # Extract host:port from base_url for checking
    local endpoint_check="${base_url}/models"

    # For Ollama, also check the native API
    if [[ "$provider" == "ollama" ]]; then
        local ollama_api="${base_url%/v1}/api/tags"
        if curl -s "$ollama_api" 2>/dev/null | grep -q "models"; then
            echo -e "${GREEN}  Ollama is running${NC}"

            # Check if specific model is available
            if curl -s "$ollama_api" 2>/dev/null | grep -q "\"name\":\"${model}\""; then
                echo -e "${GREEN}  Model '${model}' is available${NC}"
                return 0
            else
                echo -e "${YELLOW}  Model '${model}' not found. Available models:${NC}"
                curl -s "$ollama_api" 2>/dev/null | $PYTHON -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('models', []):
    print(f\"    - {m['name']}\")
" 2>/dev/null || echo "    (could not list models)"
                echo -e "${YELLOW}  Pull it with: ollama pull ${model}${NC}"
                return 1
            fi
        else
            echo -e "${RED}  Ollama not responding at ${base_url%/v1}${NC}"
            echo -e "${YELLOW}  Make sure Ollama is running: ollama serve${NC}"
            return 1
        fi
    fi

    # For SGLang/vLLM/OpenAI-compatible, check the models endpoint
    if curl -s "$endpoint_check" 2>/dev/null | grep -q "data\|model\|id"; then
        echo -e "${GREEN}  LLM endpoint is responding${NC}"
        return 0
    else
        echo -e "${RED}  LLM endpoint not responding at ${base_url}${NC}"

        case "$provider" in
            sglang)
                echo -e "${YELLOW}  Start SGLang with your model${NC}"
                ;;
            vllm)
                echo -e "${YELLOW}  Start vLLM with your model${NC}"
                ;;
            openai)
                echo -e "${YELLOW}  Check your OpenAI API key in config.yaml${NC}"
                ;;
            *)
                echo -e "${YELLOW}  Start your LLM server at ${base_url}${NC}"
                ;;
        esac
        return 1
    fi
}

run_agent() {
    local focus="${1:-$default_focus}"

    echo ""
    echo -e "${YELLOW}Running agent for: $focus${NC}"
    echo ""

    cd "$SCRIPT_DIR"
    $PYTHON src/agent.py --no-web "$focus"
}

start_dashboard() {
    echo ""
    echo -e "${YELLOW}Starting dashboard...${NC}"

    cd "$SCRIPT_DIR"
    $PYTHON web/app.py &
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
    if [[ -n "${DASHBOARD_PID:-}" ]] && kill -0 "$DASHBOARD_PID" 2>/dev/null; then
        echo ""
        echo -e "${YELLOW}Stopping dashboard...${NC}"
        pkill -f "$PYTHON web/app.py" 2>/dev/null || true
        echo -e "${GREEN}Done${NC}"
    fi
}

show_status() {
    load_config

    echo "Service Status:"
    echo ""
    echo -e "LLM Configuration:"
    echo -e "  Provider: ${CYAN}${provider}${NC}"
    echo -e "  Model: ${CYAN}${model}${NC}"
    echo -e "  Endpoint: ${CYAN}${base_url}${NC}"
    echo ""

    # Check LLM endpoint
    if [[ "$provider" == "ollama" ]]; then
        local ollama_api="${base_url%/v1}/api/tags"
        if curl -s "$ollama_api" 2>/dev/null | grep -q "models"; then
            echo -e "  LLM (${provider}):  ${GREEN}Running${NC}"
        else
            echo -e "  LLM (${provider}):  ${RED}Not running${NC}"
        fi
    else
        if curl -s "${base_url}/models" 2>/dev/null | grep -q "data\|model\|id"; then
            echo -e "  LLM (${provider}):  ${GREEN}Running${NC}"
        else
            echo -e "  LLM (${provider}):  ${RED}Not running${NC}"
        fi
    fi

    # Check dashboard
    if curl -s http://localhost:8501/ > /dev/null 2>&1; then
        echo -e "  Dashboard:  ${GREEN}Running${NC} on :8501"
    else
        echo -e "  Dashboard:  ${RED}Not running${NC}"
    fi

    # Show token usage summary
    if [[ -f "$SCRIPT_DIR/data/usage.json" ]]; then
        echo ""
        echo "Token Usage:"
        $PYTHON -c "
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
}

trap stop_all EXIT

# Main
print_header
load_config

case "${1:-}" in
    "")
        # Default: check model, run default agent, start dashboard
        check_model || exit 1
        run_agent
        start_dashboard
        ;;

    agent)
        # Run agent only (no dashboard)
        shift
        check_model || exit 1
        run_agent "${1:-$default_focus}"
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
        show_status
        ;;

    stop)
        pkill -f "$PYTHON web/app.py" 2>/dev/null && echo "Stopped dashboard" || true
        ;;

    list)
        $PYTHON src/agent.py --list
        ;;

    reset-usage)
        rm -f "$SCRIPT_DIR/data/usage.json"
        echo "Token usage reset"
        ;;

    scrape)
        # Just scrape Reddit, no analysis
        shift
        echo -e "${YELLOW}Scraping only (no analysis)...${NC}"
        $PYTHON src/scraper.py "${1:-$default_focus}"
        echo -e "${GREEN}Done! Analyze with: ./start.sh analyze${NC}"
        ;;

    analyze)
        # Just analyze existing scrape data
        shift
        check_model || exit 1
        echo -e "${YELLOW}Analyzing existing scrape data...${NC}"
        $PYTHON src/analyzer.py "${1:-$default_focus}"
        echo -e "${GREEN}Done! View reports: ./start.sh web${NC}"
        ;;

    install)
        # Install dependencies
        echo -e "${YELLOW}Installing dependencies...${NC}"
        if [[ -d "$SCRIPT_DIR/venv" ]]; then
            "$SCRIPT_DIR/venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
        else
            echo "Creating virtual environment..."
            python3 -m venv "$SCRIPT_DIR/venv"
            "$SCRIPT_DIR/venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
        fi
        echo -e "${GREEN}Done! Dependencies installed in venv/${NC}"
        ;;

    help|--help|-h)
        load_config
        echo "Usage: $0 [command] [options]"
        echo ""
        echo "Current LLM: ${provider} (${model})"
        echo ""
        echo "Commands:"
        echo "  (none)              Run default agent + start dashboard"
        echo "  <focus_area>        Run specific focus area + dashboard"
        echo "  agent [focus]       Run agent only (no dashboard)"
        echo "  all                 Run all focus areas + dashboard"
        echo "  web, dashboard      Start dashboard only"
        echo "  scrape [focus]      Just scrape Reddit (no analysis)"
        echo "  analyze [focus]     Just analyze existing scrape data"
        echo "  status              Show service status"
        echo "  list                List available focus areas"
        echo "  stop                Stop dashboard"
        echo "  reset-usage         Reset token usage stats"
        echo "  install             Install dependencies in venv"
        echo ""
        echo "Focus areas: saas_opportunities, dev_tools, ai_ml, ai_opensource_news"
        echo ""
        echo "Examples:"
        echo "  $0                  # Run saas scan + open dashboard"
        echo "  $0 dev_tools        # Scan dev_tools + open dashboard"
        echo "  $0 agent ai_ml      # Just scan ai_ml (no dashboard)"
        echo "  $0 scrape dev_tools # Just scrape, analyze later"
        echo "  $0 all              # Scan everything + open dashboard"
        echo "  $0 web              # Just view existing reports"
        echo "  $0 install          # Install/update dependencies"
        ;;

    *)
        # Assume it's a focus area
        check_model || exit 1
        run_agent "$1"
        start_dashboard
        ;;
esac
