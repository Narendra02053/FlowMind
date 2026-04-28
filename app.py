from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Generator, List, Tuple

import gradio as gr
from dotenv import load_dotenv

from agent.memory import get_or_create_memory, reset_memory
from agent.retry_handler import execute_with_retry
from utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

APP_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = APP_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

def _format_output(result: dict) -> str:
    output = result.get("output") or "(no stdout)"
    attempts = result.get("attempts", 1)
    execution_time = result.get("execution_time_seconds", 0.0)
    error = result.get("error")
    if error:
        return (
            "Status: FAILED\n"
            f"Retry Attempts Used: {attempts}\n"
            f"Execution Time (s): {execution_time}\n\n"
            "Execution Output:\n"
            f"{output}\n\n"
            "Error Details:\n"
            f"{error}"
        )
    return (
        "Status: SUCCESS\n"
        f"Retry Attempts Used: {attempts}\n"
        f"Execution Time (s): {execution_time}\n\n"
        "Execution Output:\n"
        f"{output}"
    )


def _format_plan(steps: List[str]) -> str:
    if not steps:
        return "No plan generated."
    return "\n".join(f"Step {idx}: {step}" for idx, step in enumerate(steps, start=1))


def _ensure_session(session_id: str | None) -> str:
    return session_id or uuid.uuid4().hex


def handle_prompt(
    user_prompt: str,
    selected_model: str,
    uploaded_file,
    session_id: str | None,
) -> Generator[Tuple[str, str, List[str], str, str, str], None, None]:
    session_id = _ensure_session(session_id)
    if not user_prompt or not user_prompt.strip():
        yield "", "Please enter a prompt.", [], session_id, "", "Idle"
        return

    file_path = None
    if uploaded_file is not None:
        file_path = uploaded_file.name

    memory = get_or_create_memory(session_id)
    logger.info("prompt received for session=%s", session_id)

    yield "", "Planning task...", [], session_id, "Generating plan...", "Planning"

    result = execute_with_retry(
        prompt=user_prompt.strip(),
        memory=memory,
        output_dir=str(OUTPUT_DIR),
        model=selected_model,
        uploaded_file_path=file_path,
        max_retries=3,
    )
    plan_steps = result.get("plan_steps", [])
    plan_text = _format_plan(plan_steps)
    failed_step_index = result.get("failed_step_index")
    if failed_step_index:
        current_step_text = f"Failed at Step {failed_step_index}: {result.get('failed_step_text', '')}"
    else:
        current_step_text = "Completed all steps."

    if result.get("error"):
        formatted_output = (
            _format_output(result)
            + "\n\nFailed Code:\n"
            + (result.get("code") or "(no code)")
        )
    else:
        formatted_output = _format_output(result)

    yield (
        result["code"],
        formatted_output,
        result.get("images", []),
        session_id,
        plan_text,
        current_step_text,
    )


def handle_reset(session_id: str | None) -> Tuple[str, str, List[str], str, str, str]:
    session_id = _ensure_session(session_id)
    reset_memory(session_id)
    logger.info("memory reset for session=%s", session_id)
    return "", "Session memory reset successfully.", [], session_id, "", "Idle"


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Eureka Agent") as demo:
        gr.Markdown("# Eureka Agent\nNatural-language to executable Python with memory.")
        session_state = gr.State("")

        with gr.Row():
            prompt_input = gr.Textbox(
                label="Task Prompt",
                placeholder="Example: Plot histogram of random data",
                lines=4,
            )
            file_input = gr.File(label="Optional File Upload")
            model_dropdown = gr.Dropdown(
                choices=["gpt-4o-mini", "gpt-4.1-mini", "llama3-70b"],
                value="gpt-4o-mini",
                label="Model",
            )

        with gr.Row():
            run_button = gr.Button("Run Task", variant="primary")
            reset_button = gr.Button("Reset Memory")

        code_output = gr.Code(label="Generated Python Code", language="python")
        text_output = gr.Textbox(label="Execution Output", lines=12)
        image_output = gr.Gallery(label="Generated Plots", height=300)
        plan_output = gr.Textbox(label="Execution Plan", lines=8)
        current_step_output = gr.Textbox(label="Current Step", lines=2, value="Idle")

        run_button.click(
            fn=handle_prompt,
            inputs=[prompt_input, model_dropdown, file_input, session_state],
            outputs=[code_output, text_output, image_output, session_state, plan_output, current_step_output],
        )

        reset_button.click(
            fn=handle_reset,
            inputs=[session_state],
            outputs=[code_output, text_output, image_output, session_state, plan_output, current_step_output],
        )

    return demo


if __name__ == "__main__":
    app = build_app()
    app.launch(server_name=os.getenv("HOST", "127.0.0.1"), server_port=int(os.getenv("PORT", "7860")))
