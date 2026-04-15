from __future__ import annotations

from threading import Lock
from typing import Dict, Optional

from .models import ReplayRecord, TaskRecord


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._tasks: Dict[str, TaskRecord] = {}
        self._replays: Dict[str, ReplayRecord] = {}

    def save_task(self, task: TaskRecord) -> None:
        with self._lock:
            self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            return self._tasks.get(task_id)

    def save_replay(self, replay: ReplayRecord) -> None:
        with self._lock:
            self._replays[replay.task_id] = replay

    def get_replay(self, task_id: str) -> Optional[ReplayRecord]:
        with self._lock:
            return self._replays.get(task_id)
