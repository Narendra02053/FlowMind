from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ExecutionRecord:
    prompt: str
    code: str
    output: str
    error: str | None = None
    images: List[str] = field(default_factory=list)


class NotebookMemory:
    """
    Notebook-style memory that persists Python globals and execution history.
    """

    def __init__(self) -> None:
        self._globals: Dict[str, Any] = {
            "__name__": "__main__",
        }
        self._history: List[ExecutionRecord] = []
        self._code_cells: List[str] = []
        self._plan_history: List[List[str]] = []
        self._step_results: List[Dict[str, Any]] = []

    @property
    def globals(self) -> Dict[str, Any]:
        return self._globals

    @property
    def history(self) -> List[ExecutionRecord]:
        return self._history

    @property
    def code_cells(self) -> List[str]:
        return self._code_cells

    @property
    def plan_history(self) -> List[List[str]]:
        return self._plan_history

    @property
    def step_results(self) -> List[Dict[str, Any]]:
        return self._step_results

    def add_record(
        self,
        prompt: str,
        code: str,
        output: str,
        error: str | None = None,
        images: List[str] | None = None,
    ) -> None:
        self._code_cells.append(code)
        self._history.append(
            ExecutionRecord(
                prompt=prompt,
                code=code,
                output=output,
                error=error,
                images=images or [],
            )
        )

    def get_recent_history(self, max_items: int = 5) -> List[ExecutionRecord]:
        return self._history[-max_items:]

    def store_plan(self, plan: List[str]) -> None:
        self._plan_history.append(plan)

    def store_step_result(self, step_index: int, output: str) -> None:
        self._step_results.append({"step_index": step_index, "output": output})

    def reset(self) -> None:
        self._globals = {"__name__": "__main__"}
        self._history = []
        self._code_cells = []
        self._plan_history = []
        self._step_results = []


session_memory: Dict[str, NotebookMemory] = {}


def get_or_create_memory(session_id: str) -> NotebookMemory:
    memory = session_memory.get(session_id)
    if memory is None:
        memory = NotebookMemory()
        session_memory[session_id] = memory
    return memory


def reset_memory(session_id: str) -> None:
    memory = session_memory.get(session_id)
    if memory:
        memory.reset()
