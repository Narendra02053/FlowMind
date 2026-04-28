# Eureka Agent (Minimal Production-Style)

AI-powered Python execution agent with notebook-style memory and auto-retry.

## Architecture

User -> Gradio UI -> LLM Agent -> Code Generator -> Python Executor -> Memory -> Output

## Project Structure

```
eureka_agent/
├── app.py
├── agent/
│   ├── llm_agent.py
│   ├── memory.py
│   ├── executor.py
│   ├── retry_handler.py
├── prompts/
│   └── system_prompt.txt
├── utils/
│   └── logger.py
├── requirements.txt
└── README.md
```

## Setup

1. Create and activate a virtual environment:

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set environment variables:

```bash
# Required
$env:OPENAI_API_KEY="your_api_key"

# Optional
$env:OPENAI_MODEL="gpt-4o-mini"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"  # or Groq-compatible base URL
$env:HOST="127.0.0.1"
$env:PORT="7860"
```

You can also use a `.env` file because `python-dotenv` is enabled.

## Run

```bash
python app.py
```

Then open `http://127.0.0.1:7860`.

## How It Works

- `agent/llm_agent.py`: Converts natural language tasks to Python code using a system prompt.
- `agent/memory.py`: Persists globals and execution history across runs (notebook-style memory).
- `agent/executor.py`: Executes code, captures stdout, blocks risky operations, and saves matplotlib plots.
- `agent/retry_handler.py`: Retries up to 3 times by feeding execution errors back to the LLM.
- `app.py`: Gradio interface with prompt input, optional file upload, generated code panel, output panel, and plots gallery.

## Example Prompts

- `Load iris dataset and train classification model`
- `Plot histogram of random data`
- `Analyze uploaded CSV file`

## Notes

- Uploaded files are accessible to generated code via `uploaded_file_path`.
- Plots are automatically saved in `outputs/` and displayed in the UI.
- For production hardening, run execution in a stronger sandbox (container or isolated worker).
