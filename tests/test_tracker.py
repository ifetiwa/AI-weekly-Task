"""Tests for ChecklistTracker."""

import json
import os
import tempfile

import pytest

from checklist.tasks import WEEKLY_CHECKLIST, DAY_ORDER
from checklist.tracker import ChecklistTracker


@pytest.fixture
def tmp_state(tmp_path):
    """Return a ChecklistTracker backed by a temp file."""
    return ChecklistTracker(state_file=str(tmp_path / "state.json"))


def test_initial_state_all_incomplete(tmp_state):
    for day in DAY_ORDER:
        for task in WEEKLY_CHECKLIST[day]["tasks"]:
            assert not tmp_state.is_complete(day, task)


def test_mark_complete(tmp_state):
    task = WEEKLY_CHECKLIST["Monday"]["tasks"][0]
    tmp_state.mark_complete("Monday", task)
    assert tmp_state.is_complete("Monday", task)


def test_mark_incomplete(tmp_state):
    task = WEEKLY_CHECKLIST["Tuesday"]["tasks"][0]
    tmp_state.mark_complete("Tuesday", task)
    tmp_state.mark_incomplete("Tuesday", task)
    assert not tmp_state.is_complete("Tuesday", task)


def test_complete_all_for_day(tmp_state):
    tmp_state.complete_all_for_day("Wednesday")
    for task in WEEKLY_CHECKLIST["Wednesday"]["tasks"]:
        assert tmp_state.is_complete("Wednesday", task)


def test_reset_clears_all(tmp_state):
    tmp_state.complete_all_for_day("Monday")
    tmp_state.reset()
    for task in WEEKLY_CHECKLIST["Monday"]["tasks"]:
        assert not tmp_state.is_complete("Monday", task)


def test_save_and_reload(tmp_path):
    state_file = str(tmp_path / "state.json")
    tracker = ChecklistTracker(state_file=state_file)
    task = WEEKLY_CHECKLIST["Thursday"]["tasks"][0]
    tracker.mark_complete("Thursday", task)
    tracker.save()

    reloaded = ChecklistTracker(state_file=state_file)
    assert reloaded.is_complete("Thursday", task)


def test_day_progress_values(tmp_state):
    day = "Friday"
    tasks = WEEKLY_CHECKLIST[day]["tasks"]
    tmp_state.mark_complete(day, tasks[0])
    tmp_state.mark_complete(day, tasks[1])

    progress = tmp_state.day_progress(day)
    assert progress["total"] == len(tasks)
    assert progress["done"] == 2
    assert progress["pending"] == len(tasks) - 2
    assert progress["percent"] == round(2 / len(tasks) * 100)


def test_weekly_progress_totals(tmp_state):
    total_tasks = sum(len(d["tasks"]) for d in WEEKLY_CHECKLIST.values())
    tmp_state.complete_all_for_day("Monday")
    monday_count = len(WEEKLY_CHECKLIST["Monday"]["tasks"])

    wp = tmp_state.weekly_progress()
    assert wp["total"] == total_tasks
    assert wp["done"] == monday_count
    assert wp["pending"] == total_tasks - monday_count


def test_invalid_day_raises(tmp_state):
    with pytest.raises(ValueError):
        tmp_state.mark_complete("Sunday", "anything")


def test_invalid_task_raises(tmp_state):
    with pytest.raises(ValueError):
        tmp_state.mark_complete("Monday", "nonexistent task")


def test_state_file_created_on_save(tmp_path):
    state_file = str(tmp_path / "new_state.json")
    assert not os.path.exists(state_file)
    tracker = ChecklistTracker(state_file=state_file)
    tracker.save()
    assert os.path.exists(state_file)
    with open(state_file, "r") as fh:
        data = json.load(fh)
    assert "days" in data
