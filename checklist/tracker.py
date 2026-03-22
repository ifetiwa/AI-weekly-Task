"""Checklist tracker: load and save task completion state."""

import json
import os
from datetime import date
from typing import Dict, Optional

from .tasks import WEEKLY_CHECKLIST, DAY_ORDER


class ChecklistTracker:
    """Tracks completion state for the weekly tech checklist.

    State is persisted to a JSON file so progress survives between
    program invocations.
    """

    def __init__(self, state_file: str = "checklist_state.json"):
        self.state_file = state_file
        self._state: Dict = self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> Dict:
        """Load state from disk, or return a fresh state dict."""
        if os.path.exists(self.state_file):
            with open(self.state_file, "r", encoding="utf-8") as fh:
                return json.load(fh)
        return self._fresh_state()

    def save(self) -> None:
        """Persist the current state to disk."""
        with open(self.state_file, "w", encoding="utf-8") as fh:
            json.dump(self._state, fh, indent=2)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fresh_state() -> Dict:
        """Return an empty completion state for all tasks."""
        state: Dict = {"week": str(date.today().isocalendar()[1]), "days": {}}
        for day, day_data in WEEKLY_CHECKLIST.items():
            state["days"][day] = {task: False for task in day_data["tasks"]}
        return state

    def reset(self) -> None:
        """Reset all tasks to incomplete and persist."""
        self._state = self._fresh_state()
        self.save()

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------

    def mark_complete(self, day: str, task: str) -> None:
        """Mark a specific task as complete."""
        self._validate(day, task)
        self._state["days"][day][task] = True

    def mark_incomplete(self, day: str, task: str) -> None:
        """Mark a specific task as incomplete."""
        self._validate(day, task)
        self._state["days"][day][task] = False

    def is_complete(self, day: str, task: str) -> bool:
        """Return True if the given task is marked complete."""
        self._validate(day, task)
        return bool(self._state["days"][day][task])

    def complete_all_for_day(self, day: str) -> None:
        """Mark every task for *day* as complete."""
        if day not in WEEKLY_CHECKLIST:
            raise ValueError(f"Unknown day: {day!r}")
        for task in self._state["days"][day]:
            self._state["days"][day][task] = True

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------

    def day_progress(self, day: str) -> Dict:
        """Return completion stats for a single day."""
        if day not in WEEKLY_CHECKLIST:
            raise ValueError(f"Unknown day: {day!r}")
        tasks = self._state["days"][day]
        total = len(tasks)
        done = sum(1 for v in tasks.values() if v)
        return {
            "day": day,
            "label": WEEKLY_CHECKLIST[day]["label"],
            "total": total,
            "done": done,
            "pending": total - done,
            "percent": round(done / total * 100) if total else 0,
            "tasks": tasks,
        }

    def weekly_progress(self) -> Dict:
        """Return completion stats for the entire week."""
        days = {}
        total_tasks = 0
        total_done = 0
        for day in DAY_ORDER:
            progress = self.day_progress(day)
            days[day] = progress
            total_tasks += progress["total"]
            total_done += progress["done"]
        return {
            "total": total_tasks,
            "done": total_done,
            "pending": total_tasks - total_done,
            "percent": round(total_done / total_tasks * 100) if total_tasks else 0,
            "days": days,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _validate(self, day: str, task: str) -> None:
        if day not in WEEKLY_CHECKLIST:
            raise ValueError(f"Unknown day: {day!r}")
        if task not in self._state["days"].get(day, {}):
            raise ValueError(f"Unknown task for {day}: {task!r}")
