# Changelog

## 2026-01-23: GPT-5 Compatibility & Config Improvements

### GPT-5 Model Support

#### `src/analyzer.py`
- **GPT-5 compatibility**: Use `max_completion_tokens` instead of `max_tokens` for GPT-5 series models
- **Temperature fix**: GPT-5 models only support default temperature (1), so temperature parameter is omitted for these models
- **Better error logging**: Added `HTTPStatusError` handling to show API response body on errors

### Config-Driven Defaults

#### `start.sh`
- **`default_focus` support**: Now reads `default_focus` from config.yaml instead of hardcoding `saas_opportunities`
- **Updated all commands**: `agent`, `scrape`, `analyze` now respect `default_focus` when no argument provided
- **Fixed exit trap**: `stop_all()` now only prints "Stopping dashboard..." when a dashboard was actually started

---

## 2026-01-23: Voice AI Focus Area Expansion

Enhanced voice AI coverage with new subreddits and keywords for tracking voice AI products and discussions.

### Changes

#### `config.yaml`
- **User-Agent fix**: Changed from `"RedditIntel/1.0 (Research Bot)"` to Chrome browser User-Agent to fix 403 Forbidden errors from Reddit's bot detection
- **New subreddits** added to `voice_ai` and `voice_ai_news`:
  - `elevenlabs` (21k members) - ElevenLabs voice AI community
  - `grok` (142k members) - xAI Grok with voice mode
  - `GeminiAI` (223k members) - Google Gemini including Gemini Live
- **New keywords** added to both focus areas:
  - `Vapi` - Voice AI platform
  - `Retell` - Retell AI voice agents
  - `Ultravox` - Fixie's real-time voice model
  - `Gemini Live` - Google's live voice AI
  - `OpenAI Realtime` - OpenAI's realtime voice API
  - `Grok voice` - xAI's voice features
  - `voice mode` - General voice mode discussions

### Products Without Dedicated Subreddits

The following products don't have dedicated subreddits but are now tracked via keywords in existing AI/voice subreddits:
- Vapi
- Retell AI
- Ultravox
- OpenAI Realtime API

---

## 2026-01-22: Multi-Provider LLM Support

Added support for multiple LLM backends (Ollama, SGLang, vLLM, OpenAI) with provider-aware configuration.

### New Features

- **Provider presets**: Auto-configured defaults for common LLM backends
- **Ollama support**: Native integration with Ollama's OpenAI-compatible API
- **API key support**: Optional authentication for OpenAI and secured endpoints
- **Dynamic model detection**: start.sh verifies correct endpoint based on provider

### Files Changed

#### `src/analyzer.py`
- Added `PROVIDER_PRESETS` dictionary with defaults for ollama, sglang, vllm, openai, openai-compatible
- Updated `call_llm()` to resolve provider presets and apply them as defaults
- Added `api_key` support with proper Authorization headers
- Updated `httpx.post()` call to include headers
- Updated module docstring to reflect multi-provider support

#### `config.yaml`
- Added `provider` field (set to "ollama" for local setup)
- Changed model to `qwen2.5:7b` (available locally)
- Added commented `api_key` field for authenticated endpoints

#### `config.yaml.example` (new file)
- Template configuration for new users
- Documents all provider options with examples

#### `.gitignore`
- Added `config.yaml` to prevent committing local configurations

#### `start.sh`
- Complete rewrite for provider-awareness
- `get_llm_config()`: Reads config.yaml using Python for proper YAML parsing
- `check_model()`: Verifies correct endpoint based on provider type
  - Ollama: Checks `/api/tags` endpoint, lists available models if configured model missing
  - SGLang/vLLM/OpenAI-compatible: Checks `/v1/models` endpoint
- `show_status()`: Displays current LLM configuration (provider, model, endpoint)
- `help`: Shows current LLM in use
- Removed all hardcoded GLM-4.7-Flash references

#### `web/app.py`
- Updated analysis log message to show dynamic model name from config
- Updated `index()` route to pass LLM info to template

#### `web/templates/index.html`
- Footer now shows dynamic model/provider: `{{ llm.model }} ({{ llm.provider }})`

#### `README.md`
- Updated Quick Start to reference `config.yaml.example`
- Added "LLM Providers" section documenting:
  - Ollama configuration
  - SGLang/vLLM configuration
  - OpenAI configuration (with api_key)
  - Generic OpenAI-compatible endpoint

### Configuration Examples

**Ollama:**
```yaml
llm:
  provider: "ollama"
  model: "qwen2.5:7b"
```

**SGLang/vLLM:**
```yaml
llm:
  provider: "sglang"
  model: "your-model"
```

**OpenAI:**
```yaml
llm:
  provider: "openai"
  model: "gpt-4o-mini"
  api_key: "sk-..."
```

### Breaking Changes

None. Existing configurations without a `provider` field default to `openai-compatible` behavior.

---

## 2026-01-22: Consolidate Shell Scripts

Merged `run.sh` into `start.sh` and deleted `run.sh`.

### New Commands in `start.sh`

- `scrape [focus]` - Just scrape Reddit without analysis
- `analyze [focus]` - Analyze existing scrape data without scraping
- `install` - Install dependencies (creates venv if needed)

### Removed Files

- `run.sh` - Functionality merged into `start.sh`

---

## 2026-01-22: Venv Auto-Detection

Updated `start.sh` to automatically detect and use virtual environment.

### Changes

#### `start.sh`
- Added `detect_python()` function that tries system Python first, falls back to `venv/bin/python`
- All Python calls now use `$PYTHON` variable instead of hardcoded `python3`
- Shows helpful error message if neither system nor venv has required packages

---

## 2026-01-22: README Overhaul

Updated README.md to accurately reflect how to run the platform.

### Changes

#### `README.md`
- **Quick Start**: Now uses `./start.sh install` and `./start.sh`
- **Requirements**: Added Ollama as easiest option
- **Architecture**: Added `start.sh`, `config.yaml.example`, `venv/` to diagram
- **Usage**: Complete command reference for all `start.sh` subcommands
- Removed outdated raw `python` command examples

---

## 2026-01-22: Gitignore Updates

#### `.gitignore`
- Added `*.backup` and `*.bak` for local backup files

---

## 2026-01-22: Scraper Rate Limiting & Retry Logic

Added robust rate limiting and retry logic to handle Reddit's 429 errors.

### Changes

#### `src/scraper.py`
- Added `fetch_with_retry()` function with exponential backoff for 429 errors
- Added `rate_limit_delay()` with random jitter to avoid predictable patterns
- Updated `fetch_subreddit()` and `fetch_comments()` to use retry logic
- Configurable delays via `config.yaml`
- Better progress output during scraping

#### `config.yaml`
- Added `delay_between_requests` (default 3.0s) - delay between comment fetches
- Added `delay_between_subreddits` (default 6.0s) - delay between subreddits

### Retry Behavior
- Max 3 retries on 429 errors
- Exponential backoff: 10s, 20s, 40s (plus random jitter)
- Gracefully skips failed requests instead of crashing
