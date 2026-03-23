# AI-weekly-Task

A Python CLI tool that manages and tracks the company's weekly tech checklist, covering five daily focus areas from Monday through Friday.

## Checklist Coverage

| Day | Focus Area |
|-----------|------------------------|
| Monday | Websites & CMS |
| Tuesday | SEO & Analytics |
| Wednesday | Email & Deliverability |
| Thursday | LIMS & Core Systems |
| Friday | Systems & Performance |

## Requirements

- Python 3.8+
- `pytest` (for running tests)

```bash
pip install -r requirements.txt
```

## Usage

All commands accept an optional `--state-file <path>` flag to specify where progress is persisted (default: `checklist_state.json` in the current directory).

### Show the full weekly checklist

```bash
python main.py show
```

### Show a single day

```bash
python main.py show Monday
```

### Mark a task as complete (by 1-based index)

```bash
python main.py done Monday 1
```

### Mark a task as incomplete

```bash
python main.py undo Monday 1
```

### Complete every task for a day at once

```bash
python main.py complete-day Friday
```

### List all pending (incomplete) tasks

```bash
python main.py pending
```

### Reset all tasks to incomplete

```bash
python main.py reset
```

## Running Tests

```bash
python -m pytest tests/ -v
```

## Project Structure

```
.
├── main.py                  # CLI entry point
├── requirements.txt
├── checklist/
│   ├── __init__.py
│   ├── tasks.py             # Task definitions for all five days
│   ├── tracker.py           # Load/save completion state (JSON)
│   └── reporter.py          # Generate daily/weekly/pending reports
└── tests/
    ├── test_tasks.py
    ├── test_tracker.py
    ├── test_reporter.py
    └── test_main.py
```

Progress is saved automatically to `checklist_state.json` after every `done`, `undo`, `complete-day`, and `reset` command.
