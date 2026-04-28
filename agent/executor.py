from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List

from utils.logger import get_logger

logger = get_logger(__name__)

BLOCKED_IMPORTS = {"os", "subprocess", "shutil"}
BLOCKED_CALLS = {"exec", "eval", "__import__", "open"}


def _validate_code(code: str) -> None:
    blocked_text_patterns = [
        "import os",
        "import subprocess",
        "import shutil",
        "eval(",
        "exec(",
        "open(",
        "__import__",
    ]
    lowered = code.lower()
    for pattern in blocked_text_patterns:
        if pattern in lowered:
            raise ValueError(f"Blocked code pattern detected: {pattern}")

    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in BLOCKED_IMPORTS:
                    raise ValueError(f"Blocked import detected: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in BLOCKED_IMPORTS:
                raise ValueError(f"Blocked import detected: {node.module}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_CALLS:
                raise ValueError(f"Blocked function detected: {node.func.id}")


def _collect_images(output_path: Path) -> List[str]:
    image_paths = sorted(str(path) for path in output_path.glob("*.png"))
    return image_paths


def run_code(
    code: str,
    memory_globals: Dict[str, Any],
    output_dir: str,
    uploaded_file_path: str | None = None,
    previous_code_cells: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Execute Python code using persisted memory globals.
    Captures stdout and matplotlib plots.
    """
    try:
        _validate_code(code)
        for old_code in previous_code_cells or []:
            _validate_code(old_code)
    except ValueError as exc:
        logger.error("execution blocked: %s", exc)
        return {
            "success": False,
            "stdout": "",
            "error": str(exc),
            "images": [],
            "execution_time_seconds": 0.0,
        }

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    before_images = set(_collect_images(output_path))

    session_payload = {
        "globals": {
            key: value
            for key, value in memory_globals.items()
            if key == "__name__" or isinstance(value, (str, int, float, bool, list, dict, tuple, type(None)))
        }
    }
    replay_code = "\n\n".join(previous_code_cells or [])
    user_code = code
    uploaded_path_literal = repr(uploaded_file_path) if uploaded_file_path else "None"
    output_dir_literal = repr(str(output_path))

    session_json_literal = repr(json.dumps(session_payload))
    script = f"""
import contextlib
import io
import json
import os
import traceback
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

session = json.loads({session_json_literal})
globals_env = session.get("globals", {{}})
globals_env["__name__"] = "__main__"
uploaded_file_path = {uploaded_path_literal}
output_dir = {output_dir_literal}
globals_env["uploaded_file_path"] = uploaded_file_path

def save_plot(filename=None):
    import uuid
    name = filename or f"plot_{{uuid.uuid4().hex[:8]}}.png"
    full_path = os.path.join(output_dir, name)
    plt.savefig(full_path, bbox_inches="tight")
    return full_path

globals_env["save_plot"] = save_plot

stdout_buffer = io.StringIO()
error_text = None
success = True
execution_result = {{}}

try:
    with contextlib.redirect_stdout(stdout_buffer):
{chr(10).join("        " + line for line in replay_code.splitlines()) if replay_code else "        pass"}
{chr(10).join("        " + line for line in user_code.splitlines())}
except Exception:
    success = False
    error_text = traceback.format_exc()
finally:
    for fig_num in plt.get_fignums():
        fig = plt.figure(fig_num)
        save_plot()
    plt.close("all")

safe_globals = {{
    key: value for key, value in globals_env.items()
    if key == "__name__" or isinstance(value, (str, int, float, bool, list, dict, tuple, type(None)))
}}

execution_result = {{
    "success": success,
    "stdout": stdout_buffer.getvalue().strip(),
    "error": error_text,
    "globals": safe_globals
}}
print("___EUREKA_JSON_START___")
print(json.dumps(execution_result))
print("___EUREKA_JSON_END___")
"""
    try:
        start_time = time.perf_counter()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as temp_script:
            temp_script.write(script)
            temp_script_path = temp_script.name

        completed = subprocess.run(
            [sys.executable, temp_script_path],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(output_path),
        )
        end_time = time.perf_counter()
        execution_time = round(end_time - start_time, 4)

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        marker_start = "___EUREKA_JSON_START___"
        marker_end = "___EUREKA_JSON_END___"
        if marker_start in stdout and marker_end in stdout:
            payload = stdout.split(marker_start, 1)[1].split(marker_end, 1)[0].strip()
            data = json.loads(payload)
            memory_globals.clear()
            memory_globals.update(data.get("globals", {"__name__": "__main__"}))
            run_stdout = data.get("stdout", "")
            run_error = data.get("error")
            success = bool(data.get("success"))
        else:
            run_stdout = stdout.strip()
            run_error = stderr.strip() or "Execution failed without structured result."
            success = False

        after_images = set(_collect_images(output_path))
        new_images = sorted(after_images - before_images)

        if success:
            logger.info("execution result: success in %ss", execution_time)
        else:
            logger.error("execution errors: %s", run_error)

        return {
            "success": success,
            "stdout": run_stdout,
            "error": run_error,
            "images": new_images,
            "execution_time_seconds": execution_time,
        }
    except subprocess.TimeoutExpired:
        logger.error("execution errors: timeout after 30 seconds")
        return {
            "success": False,
            "stdout": "",
            "error": "Execution timed out after 30 seconds.",
            "images": [],
            "execution_time_seconds": 30.0,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Code execution failed: %s", exc)
        return {
            "success": False,
            "stdout": "",
            "error": traceback.format_exc(),
            "images": [],
            "execution_time_seconds": 0.0,
        }
    finally:
        temp_file = locals().get("temp_script_path")
        if temp_file:
            try:
                Path(temp_file).unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to delete temp script: %s", temp_file)
