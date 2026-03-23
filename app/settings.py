"""Settings blueprint — manage custom tasks per day."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.dashboard import INTEGRATION_LABELS, TASK_INTEGRATIONS
from app.models import CustomTask
from checklist.tasks import DAY_ORDER, WEEKLY_CHECKLIST

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/")
@login_required
def index():
    custom_tasks = (
        CustomTask.query
        .filter_by(user_id=current_user.id, is_active=True)
        .order_by(CustomTask.created_at.asc())
        .all()
    )

    # Group custom tasks by day
    custom_by_day = {}
    for day in DAY_ORDER:
        custom_by_day[day] = [t for t in custom_tasks if t.day == day]

    # Build combined view: default tasks + custom tasks per day
    days_data = []
    for day in DAY_ORDER:
        default_tasks = WEEKLY_CHECKLIST[day]["tasks"]
        label = WEEKLY_CHECKLIST[day]["label"]
        days_data.append({
            "name": day,
            "label": label,
            "default_tasks": default_tasks,
            "custom_tasks": custom_by_day.get(day, []),
        })

    # Available integration types for the dropdown
    int_types = [
        {"value": k, "label": v["label"], "icon": v["icon"]}
        for k, v in INTEGRATION_LABELS.items()
    ]

    return render_template(
        "settings.html",
        days_data=days_data,
        integration_types=int_types,
    )


@settings_bp.route("/add-task", methods=["POST"])
@login_required
def add_task():
    day = request.form.get("day", "").strip()
    task_name = request.form.get("task_name", "").strip()
    integration_type = request.form.get("integration_type", "manual").strip()

    if day not in DAY_ORDER:
        flash("Invalid day selected.", "error")
        return redirect(url_for("settings.index"))

    if not task_name or len(task_name) < 3:
        flash("Task name must be at least 3 characters.", "error")
        return redirect(url_for("settings.index"))

    if len(task_name) > 300:
        flash("Task name is too long (max 300 characters).", "error")
        return redirect(url_for("settings.index"))

    # Check for duplicates (both default and custom)
    default_tasks = WEEKLY_CHECKLIST[day]["tasks"]
    if task_name in default_tasks:
        flash("This task already exists as a default task.", "error")
        return redirect(url_for("settings.index"))

    existing = CustomTask.query.filter_by(
        user_id=current_user.id, day=day, task_name=task_name, is_active=True
    ).first()
    if existing:
        flash("This custom task already exists.", "error")
        return redirect(url_for("settings.index"))

    task = CustomTask(
        user_id=current_user.id,
        day=day,
        task_name=task_name,
        integration_type=integration_type,
    )
    db.session.add(task)
    db.session.commit()
    flash(f"Task \"{task_name}\" added to {day}.", "success")
    return redirect(url_for("settings.index"))


@settings_bp.route("/edit-task/<int:task_id>", methods=["POST"])
@login_required
def edit_task(task_id):
    task = CustomTask.query.filter_by(
        id=task_id, user_id=current_user.id
    ).first_or_404()

    task_name = request.form.get("task_name", "").strip()
    integration_type = request.form.get("integration_type", "manual").strip()

    if task_name and len(task_name) >= 3:
        task.task_name = task_name
    if integration_type:
        task.integration_type = integration_type

    db.session.commit()
    flash("Task updated.", "success")
    return redirect(url_for("settings.index"))


@settings_bp.route("/delete-task/<int:task_id>", methods=["POST"])
@login_required
def delete_task(task_id):
    task = CustomTask.query.filter_by(
        id=task_id, user_id=current_user.id
    ).first_or_404()
    task.is_active = False
    db.session.commit()
    flash(f"Task \"{task.task_name}\" removed.", "success")
    return redirect(url_for("settings.index"))
