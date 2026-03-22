"""Tests for ChecklistReporter."""

import pytest

from checklist.tasks import WEEKLY_CHECKLIST, DAY_ORDER
from checklist.tracker import ChecklistTracker
from checklist.reporter import ChecklistReporter


@pytest.fixture
def tracker(tmp_path):
    return ChecklistTracker(state_file=str(tmp_path / "state.json"))


@pytest.fixture
def reporter(tracker):
    return ChecklistReporter(tracker)


def test_daily_report_contains_day_name(reporter):
    report = reporter.daily_report("Monday")
    assert "Monday" in report


def test_daily_report_contains_label(reporter):
    report = reporter.daily_report("Monday")
    assert "Websites & CMS" in report


def test_daily_report_shows_all_tasks(reporter):
    report = reporter.daily_report("Tuesday")
    for task in WEEKLY_CHECKLIST["Tuesday"]["tasks"]:
        assert task in report


def test_daily_report_incomplete_marker(reporter):
    report = reporter.daily_report("Wednesday")
    assert "⬜" in report


def test_daily_report_complete_marker(tracker, reporter):
    task = WEEKLY_CHECKLIST["Thursday"]["tasks"][0]
    tracker.mark_complete("Thursday", task)
    report = reporter.daily_report("Thursday")
    assert "✅" in report


def test_weekly_report_contains_all_days(reporter):
    report = reporter.weekly_report()
    for day in DAY_ORDER:
        assert day in report


def test_weekly_report_contains_overall_progress(reporter):
    report = reporter.weekly_report()
    assert "Overall" in report


def test_weekly_report_shows_100_percent_when_all_done(tracker, reporter):
    for day in DAY_ORDER:
        tracker.complete_all_for_day(day)
    report = reporter.weekly_report()
    assert "100%" in report


def test_pending_report_lists_incomplete_tasks(tracker, reporter):
    tracker.complete_all_for_day("Monday")
    report = reporter.pending_report()
    # Monday tasks should NOT appear
    for task in WEEKLY_CHECKLIST["Monday"]["tasks"]:
        assert task not in report
    # Tasks from other days should appear
    for task in WEEKLY_CHECKLIST["Tuesday"]["tasks"]:
        assert task in report


def test_pending_report_all_done_message(tracker, reporter):
    for day in DAY_ORDER:
        tracker.complete_all_for_day(day)
    report = reporter.pending_report()
    assert "All tasks are complete" in report


def test_summary_bar_0_percent():
    bar = ChecklistReporter._summary_bar(0)
    assert "0%" in bar


def test_summary_bar_100_percent():
    bar = ChecklistReporter._summary_bar(100)
    assert "100%" in bar
    assert "░" not in bar
