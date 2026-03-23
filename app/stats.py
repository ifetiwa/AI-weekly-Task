"""Statistics blueprint — analytics and trends."""

from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.models import TaskRun
from checklist.tasks import DAY_ORDER, WEEKLY_CHECKLIST

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/")
@login_required
def index():
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    all_runs = (
        TaskRun.query
        .filter_by(user_id=current_user.id)
        .order_by(TaskRun.run_at.desc())
        .all()
    )

    week_runs = [r for r in all_runs if r.run_at and r.run_at >= week_ago]
    month_runs = [r for r in all_runs if r.run_at and r.run_at >= month_ago]

    # ── Per-day stats ───────────────────────────────────────────
    day_stats = {}
    for day in DAY_ORDER:
        day_runs = [r for r in week_runs if r.day == day]
        total = len(day_runs)
        ok = sum(1 for r in day_runs if r.status == "success")
        fail = sum(1 for r in day_runs if r.status == "failure")
        day_stats[day] = {
            "total": total,
            "success": ok,
            "failure": fail,
            "rate": round(ok / total * 100) if total else 0,
            "label": WEEKLY_CHECKLIST[day]["label"],
        }

    # ── Integration type stats ──────────────────────────────────
    int_stats = defaultdict(lambda: {"total": 0, "success": 0, "failure": 0})
    for r in month_runs:
        key = r.integration_type or "unknown"
        int_stats[key]["total"] += 1
        if r.status == "success":
            int_stats[key]["success"] += 1
        elif r.status == "failure":
            int_stats[key]["failure"] += 1

    # ── Daily run counts for last 7 days ────────────────────────
    daily_counts = defaultdict(lambda: {"success": 0, "failure": 0, "other": 0})
    for r in week_runs:
        if r.run_at:
            dkey = r.run_at.strftime("%a %d")
            if r.status == "success":
                daily_counts[dkey]["success"] += 1
            elif r.status == "failure":
                daily_counts[dkey]["failure"] += 1
            else:
                daily_counts[dkey]["other"] += 1
    # Ensure all 7 days present
    chart_data = []
    for i in range(6, -1, -1):
        d = now - timedelta(days=i)
        label = d.strftime("%a %d")
        chart_data.append({"label": label, **daily_counts[label]})

    # ── Average response time ───────────────────────────────────
    durations = [r.duration_ms for r in month_runs if r.duration_ms and r.duration_ms > 0]
    avg_duration = round(sum(durations) / len(durations)) if durations else 0

    # ── Totals ──────────────────────────────────────────────────
    total_all = len(all_runs)
    total_ok = sum(1 for r in all_runs if r.status == "success")
    total_fail = sum(1 for r in all_runs if r.status == "failure")

    return render_template(
        "stats.html",
        day_order=DAY_ORDER,
        day_stats=day_stats,
        int_stats=dict(int_stats),
        chart_data=chart_data,
        avg_duration=avg_duration,
        total_all=total_all,
        total_ok=total_ok,
        total_fail=total_fail,
        total_week=len(week_runs),
        total_month=len(month_runs),
    )
