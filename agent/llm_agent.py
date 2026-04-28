from __future__ import annotations

import os
from pathlib import Path
from typing import List

from openai import OpenAI

from utils.logger import get_logger

logger = get_logger(__name__)


def _load_system_prompt() -> str:
    prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "system_prompt.txt"
    return prompt_path.read_text(encoding="utf-8")


def _strip_markdown_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return cleaned


def generate_code(prompt: str, history: List[dict], model: str) -> str:
    """
    Convert natural language prompt into Python code.
    Returns Python code only.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set.")

    selected_model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    base_url = os.getenv("OPENAI_BASE_URL")

    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    system_prompt = _load_system_prompt()

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    logger.info("prompt received: %s", prompt)
    logger.info("Generating Python code with model=%s", selected_model)
    response = client.chat.completions.create(
        model=selected_model,
        messages=messages,
        temperature=0.1,
    )
    content = response.choices[0].message.content or ""
    code = _strip_markdown_code_fence(content)
    logger.info("generated code:\n%s", code)
    return code
