# FlowMind

FlowMind is a production-style, LLM-powered Python execution system with:

- Gradio-based user interface
- multi-step planning
- subprocess sandboxed execution
- session-isolated notebook memory
- automatic step-level retry and error correction
- plot and data analysis support via matplotlib and pandas

## Architecture

`User -> Gradio UI -> Planner Agent -> Code Generator -> Subprocess Executor -> Session Memory -> Output`

## Core Features

- **Planner-first execution**: User tasks are decomposed into ordered steps before code generation.
- **Step-by-step runtime**: Each plan step is generated and executed independently.
- **Step-scoped retry**: Only failing steps are retried; successful steps are preserved.
- **Session memory isolation**: Each UI session has its own notebook-style memory and history.
- **Sandboxed code execution**: Generated code runs in a subprocess with timeout and safety checks.
- **Structured visibility**: UI displays execution plan, current step status, generated code, output, and plots.
- **Operational logging**: Runtime events are written to `logs/app.log`.

## Project Structure

```text
eureka_agent/
├── app.py
├── agent/
│   ├── executor.py
│   ├── llm_agent.py
│   ├── memory.py
│   ├── planner.py
│   └── retry_handler.py
├── prompts/
│   └── system_prompt.txt
├── utils/
│   └── logger.py
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.10+
- OpenAI-compatible API key

## Setup

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Configure environment variables:

```powershell
# Required
$env:OPENAI_API_KEY="your_api_key"

# Optional
$env:OPENAI_MODEL="gpt-4o-mini"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"   # or Groq-compatible endpoint
$env:HOST="127.0.0.1"
$env:PORT="7860"
```

`python-dotenv` is enabled, so a local `.env` file is also supported.

## Run

```powershell
python app.py
```

Open the app at `http://127.0.0.1:<PORT>`.

If the configured port is already in use, start with another port:

```powershell
$env:PORT="8900"
python app.py
```

## How It Works

1. User submits a prompt in the UI.
2. `agent/planner.py` creates a JSON execution plan:
   - `{"steps": ["...", "..."]}`
3. `agent/retry_handler.py` loops through each step:
   - generate Python code (`agent/llm_agent.py`)
   - execute safely (`agent/executor.py`)
   - store outputs/history (`agent/memory.py`)
4. On step failure, the same step is retried with error feedback (up to max retries).
5. UI renders final outputs, plan, current step state, and generated plots.

## Security Model (Current)

`agent/executor.py` blocks unsafe patterns and runs code in a subprocess with:

- temporary script file execution
- stdout/stderr capture
- 30-second timeout
- cleanup of temporary artifacts

Blocked patterns include:

- `import os`
- `import subprocess`
- `import shutil`
- `eval(`
- `exec(`
- `open(`
- `__import__`

## Example Prompts

- `Train model on iris dataset and plot results`
- `Load a CSV file and summarize key statistics`
- `Generate random data and visualize histogram`

## Logs and Artifacts

- Runtime logs: `logs/app.log`
- Generated images: `outputs/`

## Production Notes

This project is production-style but still lightweight. For stricter production hardening, consider:

- containerized or microVM isolation for code execution
- resource limits (CPU/RAM) per execution
- stronger allowlist-based import/runtime policy
- asynchronous job queue and execution workers
- centralized monitoring and alerting
