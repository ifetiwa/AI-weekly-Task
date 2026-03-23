#!/usr/bin/env python3
"""Flask web dashboard for the Weekly Tech Checklist System."""

import os
import sys
from datetime import date

from flask import Flask, redirect, render_template, request, url_for

from checklist import ChecklistTracker, ChecklistReporter
from checklist.tasks import DAY_ORDER, WEEKLY_CHECKLIST

app = Flask(__name__)

STATE_FILE = os.path.join(os.path.dirname(__file__), "checklist_state.json")

DAY_COLORS = {
    "Monday":    {"accent": "#3b82f6", "light": "#eff6ff", "badge": "#dbeafe"},
    "Tuesday":   {"accent": "#8b5cf6", "light": "#f5f3ff", "badge": "#ede9fe"},
    "Wednesday": {"accent": "#14b8a6", "light": "#f0fdfa", "badge": "#ccfbf1"},
    "Thursday":  {"accent": "#f59e0b", "light": "#fffbeb", "badge": "#fef3c7"},
    "Friday":    {"accent": "#10b981", "light": "#ecfdf5", "badge": "#d1fae5"},
}


def get_tracker() -> ChecklistTracker:
    return ChecklistTracker(state_file=STATE_FILE)


@app.route("/")
def index():
    tracker = get_tracker()
    weekly = tracker.weekly_progress()
    week_label = f"Week of {date.today().strftime('%B %d, %Y')}"
    return render_template(
        "dashboard.html",
        weekly=weekly,
        day_order=DAY_ORDER,
        day_colors=DAY_COLORS,
        week_label=week_label,
    )


@app.route("/toggle/<day>/<int:task_index>", methods=["POST"])
def toggle(day: str, task_index: int):
    if day not in WEEKLY_CHECKLIST:
        return redirect(url_for("index"))
    tasks = WEEKLY_CHECKLIST[day]["tasks"]
    if 0 <= task_index < len(tasks):
        tracker = get_tracker()
        task = tasks[task_index]
        if tracker.is_complete(day, task):
            tracker.mark_incomplete(day, task)
        else:
            tracker.mark_complete(day, task)
        tracker.save()
    return redirect(url_for("index") + f"#{day}")


@app.route("/complete-day/<day>", methods=["POST"])
def complete_day(day: str):
    if day not in WEEKLY_CHECKLIST:
        return redirect(url_for("index"))
    tracker = get_tracker()
    tracker.complete_all_for_day(day)
    tracker.save()
    return redirect(url_for("index") + f"#{day}")


@app.route("/reset", methods=["POST"])
def reset():
    tracker = get_tracker()
    tracker.reset()
    return redirect(url_for("index"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Dashboard running at  http://127.0.0.1:{port}\n")
    app.run(debug=True, port=port)
