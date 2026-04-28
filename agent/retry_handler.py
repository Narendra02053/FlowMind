from __future__ import annotations

from typing import Any, Dict, List

from agent.executor import run_code
from agent.llm_agent import generate_code
from agent.memory import NotebookMemory
from agent.planner import create_plan
from utils.logger import get_logger

logger = get_logger(__name__)


def execute_with_retry(
    prompt: str,
    memory: NotebookMemory,
    output_dir: str,
    model: str,
    uploaded_file_path: str | None = None,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Plan and execute task step-by-step, retrying only failed steps.
    """
    try:
        plan_data = create_plan(prompt, model=model)
        steps = plan_data.get("steps", [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("planner failed, falling back to single-step execution: %s", exc)
        steps = []
    if not steps:
        steps = [prompt]

    memory.store_plan(steps)

    all_outputs: List[str] = []
    all_images: List[str] = []
    all_codes: List[str] = []
    total_attempts = 0
    total_exec_time = 0.0

    for idx, step in enumerate(steps, start=1):
        history_messages: List[dict] = []
        step_prompt = f"Task context: {prompt}\nCurrent step {idx}: {step}"
        code = generate_code(step_prompt, history_messages, model=model)
        all_codes.append(code)
        step_result: Dict[str, Any] = {}
        success = False

        for attempt in range(max_retries):
            total_attempts += 1
            logger.info("retry attempt: %s for step %s", attempt + 1, idx)
            step_result = run_code(
                code=code,
                memory_globals=memory.globals,
                output_dir=output_dir,
                uploaded_file_path=uploaded_file_path,
                previous_code_cells=memory.code_cells,
            )
            total_exec_time += step_result.get("execution_time_seconds", 0.0)
            if step_result["success"]:
                success = True
                break

            error_text = step_result["error"] or "Unknown execution error"
            logger.warning("retry attempt %s failed for step %s", attempt + 1, idx)
            history_messages.extend(
                [
                    {"role": "user", "content": step_prompt},
                    {"role": "assistant", "content": code},
                    {
                        "role": "user",
                        "content": (
                            "Your previous code failed with this error:\n"
                            f"{error_text}\n"
                            "Return corrected Python code only."
                        ),
                    },
                ]
            )
            code = generate_code(step_prompt, history_messages, model=model)
            all_codes[-1] = code

        step_stdout = step_result.get("stdout", "")
        step_error = step_result.get("error")
        step_images = step_result.get("images", [])
        memory.store_step_result(idx, step_stdout if success else (step_error or "Step failed"))
        memory.add_record(
            prompt=f"{prompt} [Step {idx}: {step}]",
            code=code,
            output=step_stdout,
            error=None if success else step_error,
            images=step_images,
        )

        all_outputs.append(f"Step {idx}: {step}\n{step_stdout or '(no stdout)'}")
        all_images.extend(step_images)

        if not success:
            return {
                "plan_steps": steps,
                "code": code,
                "all_codes": all_codes,
                "output": "\n\n".join(all_outputs),
                "error": step_error,
                "images": all_images,
                "attempts": total_attempts,
                "execution_time_seconds": round(total_exec_time, 4),
                "failed_step_index": idx,
                "failed_step_text": step,
            }

    return {
        "plan_steps": steps,
        "code": all_codes[-1] if all_codes else "",
        "all_codes": all_codes,
        "output": "\n\n".join(all_outputs),
        "error": None,
        "images": all_images,
        "attempts": total_attempts,
        "execution_time_seconds": round(total_exec_time, 4),
    }
