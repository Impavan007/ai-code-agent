# AI Coding Agent Harness

A modular, type-safe Python harness for running the autonomous AI Coding Agent. The harness exposes a set of sandboxed filesystem and command-execution tools to the LLM (targeting `qwen3-coder:480b-cloud` via Ollama Cloud) and orchestrates the complete exploration, planning, implementation, verification, and summary loop.

## Project Structure

- `requirements.txt`: Project package dependencies.
- `config.py`: Configuration and environment validation (supports `.env`).
- `llm_client.py`: Ollama Client wrapper with tool-calling schemas.
- `tools.py`: Sandboxed tool implementations (read, write, search, command execution, finish) with path safety limits.
- `logger.py`: Structured JSONLines logs and CLI formatting.
- `agent.py`: Agent loop controller (explore, decide, plan, implement, verify, summarize).
- `main.py`: Command-line and Interactive entry point.

## Installation

```bash
pip install -r requirements.txt
```

## Configuration & Authentication

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Configure settings inside `.env` (such as `TARGET_REPO_PATH` and `OLLAMA_API_KEY`).

Alternatively, sign in via Ollama CLI:
```bash
ollama signin
```

## Running the Harness

The harness supports two modes of execution:

### 1. Interactive Mode (Continuous Shell)
To start a continuous interactive prompt shell that prompts for settings and waits for tasks sequentially:
```bash
python main.py
```
This loop will ask for the repository path (defaulting to the one in `.env`), prompt for your task, execute it, display results, and wait for a new task.

### 2. One-Shot Mode (CLI Command)
To run a single task as a one-shot CLI execution:
```bash
python main.py --repo /path/to/target/repository --task "Add a new endpoint to get user profile by ID"
```

### CLI Command Options:
- `--repo`: Absolute path to the repository directory to modify (Optional if defined in `.env`).
- `--task`: Plain English request of what to implement (If omitted, triggers Interactive Mode).
- `--model`: Model to use (default: `qwen3-coder:480b-cloud`).
- `--temp`: Temperature for execution (default: `0.2`).
- `--log-dir`: Directory for log output (default: `logs`).
