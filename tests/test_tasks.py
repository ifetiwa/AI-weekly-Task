"""Tests for task definitions."""

import pytest
from checklist.tasks import WEEKLY_CHECKLIST, DAY_ORDER


def test_all_days_present():
    expected = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}
    assert set(WEEKLY_CHECKLIST.keys()) == expected


def test_day_order_matches_checklist():
    assert set(DAY_ORDER) == set(WEEKLY_CHECKLIST.keys())
    assert len(DAY_ORDER) == 5


def test_each_day_has_label_and_tasks():
    for day, data in WEEKLY_CHECKLIST.items():
        assert "label" in data, f"{day} missing 'label'"
        assert "tasks" in data, f"{day} missing 'tasks'"
        assert isinstance(data["label"], str) and data["label"], f"{day} label is empty"
        assert isinstance(data["tasks"], list) and data["tasks"], f"{day} tasks list is empty"


def test_task_strings_are_non_empty():
    for day, data in WEEKLY_CHECKLIST.items():
        for task in data["tasks"]:
            assert isinstance(task, str) and task.strip(), (
                f"Empty/non-string task in {day}: {task!r}"
            )


def test_task_counts():
    """Verify the exact number of tasks per day matches the specification."""
    expected_counts = {
        "Monday": 9,
        "Tuesday": 8,
        "Wednesday": 9,
        "Thursday": 8,
        "Friday": 7,
    }
    for day, count in expected_counts.items():
        actual = len(WEEKLY_CHECKLIST[day]["tasks"])
        assert actual == count, f"{day}: expected {count} tasks, got {actual}"


def test_monday_label():
    assert WEEKLY_CHECKLIST["Monday"]["label"] == "Websites & CMS"


def test_tuesday_label():
    assert WEEKLY_CHECKLIST["Tuesday"]["label"] == "SEO & Analytics"


def test_wednesday_label():
    assert WEEKLY_CHECKLIST["Wednesday"]["label"] == "Email & Deliverability"


def test_thursday_label():
    assert WEEKLY_CHECKLIST["Thursday"]["label"] == "LIMS & Core Systems"


def test_friday_label():
    assert WEEKLY_CHECKLIST["Friday"]["label"] == "Systems & Performance"
