#!/usr/bin/env python3
"""CLI entry point for the Weekly Tech Checklist System."""

import argparse
import sys

from checklist import ChecklistTracker, ChecklistReporter
from checklist.tasks import DAY_ORDER, WEEKLY_CHECKLIST


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="checklist",
        description="Weekly Tech Checklist — manage and report on daily tech tasks.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # show ---------------------------------------------------------------
    show_p = sub.add_parser("show", help="Display the checklist (all or one day).")
    show_p.add_argument(
        "day",
        nargs="?",
        choices=DAY_ORDER,
        help="Day to display (omit for full week).",
    )

    # done ---------------------------------------------------------------
    done_p = sub.add_parser("done", help="Mark a task as complete.")
    done_p.add_argument("day", choices=DAY_ORDER, help="Day of the task.")
    done_p.add_argument("task_index", type=int, help="1-based task index.")

    # undo ---------------------------------------------------------------
    undo_p = sub.add_parser("undo", help="Mark a task as incomplete.")
    undo_p.add_argument("day", choices=DAY_ORDER, help="Day of the task.")
    undo_p.add_argument("task_index", type=int, help="1-based task index.")

    # complete-day -------------------------------------------------------
    cd_p = sub.add_parser("complete-day", help="Mark all tasks for a day as complete.")
    cd_p.add_argument("day", choices=DAY_ORDER, help="Day to complete.")

    # pending ------------------------------------------------------------
    sub.add_parser("pending", help="List all pending (incomplete) tasks.")

    # reset --------------------------------------------------------------
    sub.add_parser("reset", help="Reset all tasks to incomplete.")

    # State file option (global) -----------------------------------------
    parser.add_argument(
        "--state-file",
        default="checklist_state.json",
        help="Path to the JSON state file (default: checklist_state.json).",
    )

    return parser


def resolve_task(day: str, task_index: int) -> str:
    """Return the task string for a 1-based index, or exit with error."""
    tasks = WEEKLY_CHECKLIST[day]["tasks"]
    if task_index < 1 or task_index > len(tasks):
        print(
            f"Error: task index {task_index} out of range "
            f"(1–{len(tasks)} for {day}).",
            file=sys.stderr,
        )
        sys.exit(1)
    return tasks[task_index - 1]


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    tracker = ChecklistTracker(state_file=args.state_file)
    reporter = ChecklistReporter(tracker)

    if args.command == "show":
        if args.day:
            print(reporter.daily_report(args.day))
        else:
            print(reporter.weekly_report())

    elif args.command == "done":
        task = resolve_task(args.day, args.task_index)
        tracker.mark_complete(args.day, task)
        tracker.save()
        print(f"✅  Marked complete: [{args.day}] {task}")

    elif args.command == "undo":
        task = resolve_task(args.day, args.task_index)
        tracker.mark_incomplete(args.day, task)
        tracker.save()
        print(f"⬜  Marked incomplete: [{args.day}] {task}")

    elif args.command == "complete-day":
        tracker.complete_all_for_day(args.day)
        tracker.save()
        print(f"✅  All tasks marked complete for {args.day}.")

    elif args.command == "pending":
        print(reporter.pending_report())

    elif args.command == "reset":
        tracker.reset()
        print("🔄  All tasks reset to incomplete.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
