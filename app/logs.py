"""Logs blueprint — view activity logs and task run history."""

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from app.models import ActivityLog, TaskRun
from checklist.tasks import DAY_ORDER

logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/")
@login_required
def index():
    page = request.args.get("page", 1, type=int)
    per_page = 30
    day_filter = request.args.get("day", "")
    status_filter = request.args.get("status", "")
    category_filter = request.args.get("category", "")

    # Task runs
    runs_q = TaskRun.query.filter_by(user_id=current_user.id)
    if day_filter:
        runs_q = runs_q.filter_by(day=day_filter)
    if status_filter:
        runs_q = runs_q.filter_by(status=status_filter)
    runs_q = runs_q.order_by(TaskRun.run_at.desc())
    runs_page = runs_q.paginate(page=page, per_page=per_page, error_out=False)

    # Activity log (latest 50)
    activity_q = ActivityLog.query.filter_by(user_id=current_user.id)
    if category_filter:
        activity_q = activity_q.filter_by(category=category_filter)
    activity_q = activity_q.order_by(ActivityLog.created_at.desc())
    activities = activity_q.limit(50).all()

    return render_template(
        "logs.html",
        runs=runs_page,
        activities=activities,
        day_order=DAY_ORDER,
        day_filter=day_filter,
        status_filter=status_filter,
        category_filter=category_filter,
    )
