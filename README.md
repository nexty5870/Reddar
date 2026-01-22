# Reddar

> Reddit Intelligence Agent - Autonomous scanning and analysis of Reddit for business opportunities and tech news.

Reddar scrapes Reddit, analyzes posts with a local LLM, and presents actionable insights through a clean web dashboard.

## This is a Fork of: https://github.com/nexty5870/Reddar

## Features

- **Multi-mode Analysis**: Opportunity discovery or news/intel gathering
- **Batch Processing**: Handles large datasets by splitting into manageable chunks
- **Report Merging**: Accumulates insights across multiple scans, deduplicating automatically
- **LLM Usage Tracking**: Full visibility into token consumption and request history
- **Clean Dashboard**: Modern UI with real-time progress streaming

## Screenshots

### Dashboard
![Dashboard](screenshots/dashboard.png)

### Run Agent
![Run Agent](screenshots/run-agent.png)

### Report View
![Report](screenshots/report.png)

### LLM Usage
![Usage](screenshots/usage.png)

## Requirements

- Python 3.10+
- Local LLM server (SGLang, vLLM, or OpenAI-compatible API)
- ~8GB+ VRAM for recommended models

## Quick Start

```bash
# Clone the repo
git clone https://github.com/nexty5870/Reddar.git
cd Reddar

# Install dependencies
pip install -r requirements.txt

# Configure your LLM endpoint in config.yaml
# Default expects SGLang on localhost:8000

# Start the dashboard
python web/app.py
```

Visit `http://localhost:8501` to access the dashboard.

## Configuration

Edit `config.yaml` to customize:

```yaml
# LLM Settings
llm:
  base_url: "http://localhost:8000/v1"
  model: "glm-4.7-flash"  # or any OpenAI-compatible model
  max_tokens: 8000
  temperature: 0.7

# Focus Areas - define what to scan
focus_areas:
  saas_opportunities:
    name: "SaaS & Business Opportunities"
    description: "Identify SaaS ideas and market gaps"
    subreddits:
      - Entrepreneur
      - SaaS
      - startups
    keywords:
      - "I wish there was"
      - "looking for a tool"

  ai_opensource_news:
    name: "AI & Opensource Intel"
    mode: "news"  # Different analysis mode
    subreddits:
      - LocalLLaMA
      - MachineLearning
      - opensource
```

## Modes

### Opportunities Mode (default)
Extracts:
- Business opportunities with demand signals
- Pain points and unmet needs
- Market insights
- Recommended actions

### News Mode
Extracts:
- Top stories with importance ranking
- Notable releases
- Trending discussions
- Tools mentioned with sentiment

## Architecture

```
reddar/
├── src/
│   ├── scraper.py      # Reddit JSON API scraper
│   ├── analyzer.py     # LLM analysis with batching
│   └── agent.py        # CLI pipeline orchestrator
├── web/
│   ├── app.py          # Flask dashboard
│   └── templates/      # Jinja2 templates
├── data/               # Scrape data (gitignored)
├── reports/            # Generated reports (gitignored)
└── config.yaml         # Configuration
```

## Usage

### Web Dashboard
```bash
python web/app.py
```

### CLI
```bash
# Run specific focus area
python src/agent.py saas_opportunities

# List available focus areas
python src/agent.py --list

# Run without starting web dashboard
python src/agent.py ai_opensource_news --no-web
```

## License

MIT
