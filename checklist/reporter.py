"""Report generator for the weekly tech checklist."""

from datetime import date
from typing import Optional

from .tasks import DAY_ORDER, WEEKLY_CHECKLIST
from .tracker import ChecklistTracker


class ChecklistReporter:
    """Generates human-readable reports from a ChecklistTracker."""

    def __init__(self, tracker: ChecklistTracker):
        self.tracker = tracker

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def daily_report(self, day: str) -> str:
        """Return a formatted report for a single day."""
        progress = self.tracker.day_progress(day)
        lines = [
            f"=== {day} — {progress['label']} ===",
            f"Progress: {progress['done']}/{progress['total']} tasks "
            f"({progress['percent']}% complete)",
            "",
        ]
        for task, done in progress["tasks"].items():
            status = "✅" if done else "⬜"
            lines.append(f"  {status}  {task}")
        lines.append("")
        return "\n".join(lines)

    def weekly_report(self, week_label: Optional[str] = None) -> str:
        """Return a formatted report for the full week."""
        week_label = week_label or f"Week of {date.today().strftime('%B %d, %Y')}"
        progress = self.tracker.weekly_progress()

        header = [
            "=" * 60,
            f"  WEEKLY TECH CHECKLIST — {week_label}",
            "=" * 60,
            f"  Overall: {progress['done']}/{progress['total']} tasks "
            f"({progress['percent']}% complete)",
            "=" * 60,
            "",
        ]

        body = []
        for day in DAY_ORDER:
            body.append(self.daily_report(day))

        footer = [
            "-" * 60,
            self._summary_bar(progress["percent"]),
            "",
        ]

        return "\n".join(header + body + footer)

    def pending_report(self) -> str:
        """Return a report listing only incomplete tasks across all days."""
        lines = ["=== PENDING TASKS ===", ""]
        any_pending = False
        for day in DAY_ORDER:
            progress = self.tracker.day_progress(day)
            pending = [t for t, done in progress["tasks"].items() if not done]
            if pending:
                any_pending = True
                lines.append(f"[{day} — {progress['label']}]")
                for task in pending:
                    lines.append(f"  ⬜  {task}")
                lines.append("")
        if not any_pending:
            lines.append("🎉 All tasks are complete!")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _summary_bar(percent: int, width: int = 40) -> str:
        filled = int(width * percent / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"  [{bar}] {percent}%"
