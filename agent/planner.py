from __future__ import annotations

import json
import os
from typing import Dict, List

from openai import OpenAI

from utils.logger import get_logger

logger = get_logger(__name__)


def _extract_plan_json(content: str) -> Dict[str, List[str]]:
    raw = content.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    data = json.loads(raw)
    steps = data.get("steps", [])
    if not isinstance(steps, list) or not all(isinstance(step, str) for step in steps):
        raise ValueError("Planner returned invalid format. Expected {'steps': [str, ...]}.")
    return {"steps": [step.strip() for step in steps if step.strip()]}


def create_plan(user_prompt: str, model: str) -> Dict[str, List[str]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set.")

    selected_model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    base_url = os.getenv("OPENAI_BASE_URL")
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    planner_system_prompt = (
        "You are a planning engine for a Python execution agent. "
        "Break a user task into clear, ordered execution steps. "
        "Return strict JSON only in this format: "
        "{\"steps\": [\"step 1\", \"step 2\"]}. "
        "Do not include markdown or explanations."
    )

    logger.info("creating plan for prompt: %s", user_prompt)
    response = client.chat.completions.create(
        model=selected_model,
        messages=[
            {"role": "system", "content": planner_system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )
    content = response.choices[0].message.content or '{"steps": []}'
    plan = _extract_plan_json(content)
    logger.info("generated plan with %s steps", len(plan["steps"]))
    return plan
