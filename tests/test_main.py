"""Tests for the CLI entry point (main.py)."""

import json
import sys

import pytest

from main import main
from checklist.tasks import WEEKLY_CHECKLIST


@pytest.fixture
def state_file(tmp_path):
    return str(tmp_path / "state.json")


def run(*args, state_file):
    return main(["--state-file", state_file] + list(args))


def test_show_week(state_file, capsys):
    run("show", state_file=state_file)
    captured = capsys.readouterr()
    assert "Monday" in captured.out
    assert "Friday" in captured.out


def test_show_day(state_file, capsys):
    run("show", "Tuesday", state_file=state_file)
    captured = capsys.readouterr()
    assert "Tuesday" in captured.out
    assert "SEO & Analytics" in captured.out


def test_done_command(state_file, capsys):
    run("done", "Monday", "1", state_file=state_file)
    captured = capsys.readouterr()
    assert "Marked complete" in captured.out

    # Verify persisted
    with open(state_file) as fh:
        state = json.load(fh)
    task = WEEKLY_CHECKLIST["Monday"]["tasks"][0]
    assert state["days"]["Monday"][task] is True


def test_undo_command(state_file, capsys):
    run("done", "Monday", "1", state_file=state_file)
    run("undo", "Monday", "1", state_file=state_file)
    captured = capsys.readouterr()
    assert "Marked incomplete" in captured.out


def test_complete_day_command(state_file, capsys):
    run("complete-day", "Friday", state_file=state_file)
    captured = capsys.readouterr()
    assert "complete for Friday" in captured.out

    with open(state_file) as fh:
        state = json.load(fh)
    for task in WEEKLY_CHECKLIST["Friday"]["tasks"]:
        assert state["days"]["Friday"][task] is True


def test_pending_command(state_file, capsys):
    run("pending", state_file=state_file)
    captured = capsys.readouterr()
    assert "PENDING TASKS" in captured.out


def test_reset_command(state_file, capsys):
    run("complete-day", "Monday", state_file=state_file)
    run("reset", state_file=state_file)
    captured = capsys.readouterr()
    assert "reset" in captured.out.lower()


def test_done_invalid_index_exits(state_file):
    with pytest.raises(SystemExit):
        run("done", "Monday", "999", state_file=state_file)
