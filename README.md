# Vision

> Self-improving AI agent — Python, FastAPI, SQLite, Ollama

## Features

- **Self-improving skills** — agent creates and improves skills from experience
- **Tool calling** — file, bash, browser, memory, cron, delegation
- **Multi-step reasoning** — agent chains multiple tool calls autonomously
- **WebSocket streaming** — real-time token-by-token responses
- **Memory system** — FTS5 full-text search, user profiling
- **Agent delegation** — parallel subagents for complex tasks (DAG support)
- **RAG pipeline** — document indexing, embedding, retrieval
- **Telegram bot** — chat via Telegram messenger
- **94 tests** — unit + integration coverage

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com/) with `qwen2.5:14b` model (or any chat model)

## Quick Start

### 1. Install

```bash
cd Vision
pip install -e .
```

Or use the installer:
```bash
scripts\install.bat
```

### 2. Start

**CLI mode** (terminal chat):
```bash
python run.py
```
Or double-click `start_vision.bat`

**Gateway mode** (API + Telegram bot):
```bash
python run.py gateway
```

### 3. Chat

In CLI mode — just type messages after the `You:` prompt.

Gateway mode serves:
- `http://127.0.0.1:8080/` — Web chat UI
- `http://127.0.0.1:8080/docs` — Swagger API
- `http://127.0.0.1:8080/ws` — WebSocket endpoint

### 4. Telegram (optional)

Set your bot token in `config.json`:
```json
{
  "gateway": {
    "auth_token": "YOUR_TELEGRAM_BOT_TOKEN"
  }
}
```

Then start gateway mode — bot will auto-connect.

## Configuration

`config.json` (created by installer or manually):
```json
{
  "llm": {
    "provider": "ollama",
    "base_url": "http://127.0.0.1:11434",
    "model": "qwen2.5:14b",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "gateway": {
    "port": 8080,
    "auth_token": ""
  }
}
```

## Architecture

```
CLI / WebSocket / Telegram
         │
    Gateway (FastAPI)
         │
    Agent (self-improving loop)
         │
    ┌────┴────┐
    │  Tools  │
    ├─────────┤
    │ file    │ read/write/edit/list/search
    │ bash    │ PowerShell execution
    │ browser │ DuckDuckGo search, URL fetch
    │ memory  │ save/recall knowledge
    │ cron    │ scheduled tasks
    │ delegate│ subagent spawning (parallel/DAG)
    └─────────┘
         │
    SQLite (FTS5) + RAG + Skills
```

## Available Tools

| Tool | Description |
|------|-------------|
| `read_file(path)` | Read file contents |
| `write_file(path, content)` | Write to file |
| `edit_file(path, old, new)` | Edit file by string replace |
| `list_directory(path)` | List directory entries |
| `search_files(dir, pattern)` | Glob search |
| `execute_bash(command)` | Run PowerShell command |
| `search_web(query)` | DuckDuckGo search |
| `fetch_url(url)` | Fetch URL content |
| `save_memory(key, content)` | Save knowledge |
| `get_system_info()` | CPU, RAM, disk |
| `delegate_task(prompt)` | Spawn subagent |

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Project Structure

```
Vision/
├── vision/
│   ├── agent/          # Core agent loop, LLM client, context, delegation
│   ├── tools/          # Tool implementations + registry
│   ├── core/           # Config, database (SQLite FTS5), memory
│   ├── gateway/        # FastAPI server + WebSocket + Telegram
│   ├── rag/            # RAG pipeline (loader, embedder, vector store, retriever)
│   ├── cron/           # Task scheduler
│   └── cli.py          # Rich terminal UI
├── tests/              # 94 tests
├── run.py              # Entry point (CLI or gateway)
├── start_vision.bat    # Windows launcher
├── scripts/            # Installer
└── pyproject.toml      # Package config
```

## License

MIT

## Troubleshooting

### Ollama не отвечает / 503 ошибка
```
Connection refused / 503 Service Unavailable
```
**Решение:**
```bash
# Проверить Ollama
ollama list

# Запустить
ollama serve

# Скачать модель
ollama pull qwen2.5:14b
```
Важно: URL должен быть `127.0.0.1`, НЕ `localhost` (localhost перехватывается прокси).

### Python не найден
```
'python' is not recognized
```
**Решение:** Установить Python 3.11+ с [python.org](https://python.org/downloads/), поставить галочку "Add Python to PATH".

### Telegram bot не запускается
```
telegram bot token not configured
```
**Решение:** Получите токен у [@BotFather](https://t.me/BotFather), добавьте в `config.json`:
```json
{ "gateway": { "auth_token": "YOUR_TOKEN" } }
```

### Gateway не стартует
```
Address already in use: 8080
```
**Решение:**
```bash
netstat -ano | findstr :8080
taskkill /PID <PID> /F
```

### Другой порт
```bash
# Изменить порт в config.json
{ "gateway": { "port": 9090 } }
```

### Нет интернета — не работает
**Решение:** Vision работает полностью офлайн через Ollama. Проверьте:
1. Ollama запущен: `ollama list`
2. URL: `127.0.0.1:11434` (не localhost)
3. Модель скачана: `ollama pull qwen2.5:14b`
