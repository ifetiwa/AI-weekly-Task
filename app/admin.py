"""Admin blueprint — system-wide management for admin users."""

import os
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.dashboard import INTEGRATION_LABELS, TASK_INTEGRATIONS
from app.models import (
    INTEGRATION_TYPES,
    ActivityLog,
    CustomTask,
    IntegrationConfig,
    Site,
    TaskRun,
    User,
)
from checklist.tasks import DAY_ORDER, WEEKLY_CHECKLIST

admin_bp = Blueprint("admin", __name__)


# ── Admin-required decorator ───────────────────────────────────────

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ──────────────────────────────────────────────────────

@admin_bp.route("/")
@admin_required
def index():
    users = User.query.order_by(User.created_at.desc()).all()
    total_tasks = TaskRun.query.count()
    total_integrations = IntegrationConfig.query.filter_by(is_active=True).count()
    total_sites = Site.query.filter_by(is_active=True).count()
    total_custom_tasks = CustomTask.query.filter_by(is_active=True).count()
    recent_logs = (
        ActivityLog.query
        .order_by(ActivityLog.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "admin/dashboard.html",
        users=users,
        total_users=len(users),
        total_tasks=total_tasks,
        total_integrations=total_integrations,
        total_sites=total_sites,
        total_custom_tasks=total_custom_tasks,
        recent_logs=recent_logs,
    )


# ── User Management ───────────────────────────────────────────────

@admin_bp.route("/users")
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=all_users)


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    if user.id == current_user.id:
        flash("You cannot deactivate yourself.", "error")
        return redirect(url_for("admin.users"))
    user.is_active = not user.is_active
    db.session.commit()
    status = "activated" if user.is_active else "deactivated"
    flash(f"User {user.name} has been {status}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/toggle-admin", methods=["POST"])
@admin_required
def toggle_admin(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    if user.id == current_user.id:
        flash("You cannot change your own admin status.", "error")
        return redirect(url_for("admin.users"))
    user.is_admin = not user.is_admin
    db.session.commit()
    role = "admin" if user.is_admin else "regular user"
    flash(f"{user.name} is now a {role}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    if user.id == current_user.id:
        flash("You cannot delete yourself.", "error")
        return redirect(url_for("admin.users"))
    name = user.name
    db.session.delete(user)
    db.session.commit()
    flash(f"User {name} has been deleted.", "success")
    return redirect(url_for("admin.users"))


# ── Task Management ───────────────────────────────────────────────

@admin_bp.route("/tasks")
@admin_required
def tasks():
    # Build default tasks per day
    days_data = []
    for day in DAY_ORDER:
        days_data.append({
            "name": day,
            "label": WEEKLY_CHECKLIST[day]["label"],
            "tasks": WEEKLY_CHECKLIST[day]["tasks"],
        })

    # All custom tasks across all users
    custom_tasks = (
        CustomTask.query
        .filter_by(is_active=True)
        .order_by(CustomTask.day, CustomTask.created_at)
        .all()
    )

    int_types = [
        {"value": k, "label": v["label"], "icon": v["icon"]}
        for k, v in INTEGRATION_LABELS.items()
    ]

    all_users = User.query.order_by(User.name).all()

    return render_template(
        "admin/tasks.html",
        days_data=days_data,
        custom_tasks=custom_tasks,
        integration_types=int_types,
        day_order=DAY_ORDER,
        users=all_users,
    )


@admin_bp.route("/tasks/add", methods=["POST"])
@admin_required
def add_task():
    user_id = request.form.get("user_id", type=int)
    day = request.form.get("day", "").strip()
    task_name = request.form.get("task_name", "").strip()
    integration_type = request.form.get("integration_type", "manual").strip()

    if not task_name or len(task_name) < 3:
        flash("Task name must be at least 3 characters.", "error")
        return redirect(url_for("admin.tasks"))
    if day not in DAY_ORDER:
        flash("Invalid day.", "error")
        return redirect(url_for("admin.tasks"))
    if not user_id:
        flash("Please select a user.", "error")
        return redirect(url_for("admin.tasks"))

    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin.tasks"))

    task = CustomTask(
        user_id=user_id,
        day=day,
        task_name=task_name,
        integration_type=integration_type,
    )
    db.session.add(task)
    db.session.commit()
    flash(f'Task "{task_name}" added for {user.name} on {day}.', "success")
    return redirect(url_for("admin.tasks"))


@admin_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@admin_required
def delete_task(task_id):
    task = CustomTask.query.get_or_404(task_id)
    task.is_active = False
    db.session.commit()
    flash(f'Task "{task.task_name}" has been removed.', "success")
    return redirect(url_for("admin.tasks"))


# ── Integration Management ─────────────────────────────────────────

@admin_bp.route("/integrations")
@admin_required
def integrations():
    configs = (
        IntegrationConfig.query
        .order_by(IntegrationConfig.created_at.desc())
        .all()
    )
    sites = (
        Site.query
        .order_by(Site.created_at.desc())
        .all()
    )
    all_users = User.query.order_by(User.name).all()
    return render_template(
        "admin/integrations.html",
        configs=configs,
        sites=sites,
        users=all_users,
        integration_types=INTEGRATION_TYPES,
    )


@admin_bp.route("/integrations/<int:cfg_id>/toggle", methods=["POST"])
@admin_required
def toggle_integration(cfg_id):
    cfg = db.session.get(IntegrationConfig, cfg_id)
    if not cfg:
        abort(404)
    cfg.is_active = not cfg.is_active
    db.session.commit()
    status = "activated" if cfg.is_active else "deactivated"
    flash(f"{cfg.label or cfg.service_type} has been {status}.", "success")
    return redirect(url_for("admin.integrations"))


@admin_bp.route("/integrations/<int:cfg_id>/delete", methods=["POST"])
@admin_required
def delete_integration(cfg_id):
    cfg = db.session.get(IntegrationConfig, cfg_id)
    if not cfg:
        abort(404)
    label = cfg.label or cfg.service_type
    db.session.delete(cfg)
    db.session.commit()
    flash(f"Integration {label} has been deleted.", "success")
    return redirect(url_for("admin.integrations"))


@admin_bp.route("/sites/<int:site_id>/delete", methods=["POST"])
@admin_required
def delete_site(site_id):
    site = db.session.get(Site, site_id)
    if not site:
        abort(404)
    name = site.name
    db.session.delete(site)
    db.session.commit()
    flash(f"Site {name} has been deleted.", "success")
    return redirect(url_for("admin.integrations"))


# ── Activity Logs ──────────────────────────────────────────────────

@admin_bp.route("/logs")
@admin_required
def logs():
    page = request.args.get("page", 1, type=int)
    all_logs = (
        ActivityLog.query
        .order_by(ActivityLog.created_at.desc())
        .paginate(page=page, per_page=50, error_out=False)
    )
    return render_template("admin/logs.html", logs=all_logs)


# ── Seed Admin (CLI command) ──────────────────────────────────────

def init_admin_cli(app):
    """Register CLI command to create or promote an admin user."""

    @app.cli.command("create-admin")
    def create_admin():
        """Create or promote the admin user from environment variables."""
        import click

        email = os.environ.get("ADMIN_EMAIL", "admin@techcheck.io")
        password = os.environ.get("ADMIN_PASSWORD", "Admin@1234")
        name = os.environ.get("ADMIN_NAME", "Admin")

        user = User.query.filter_by(email=email).first()
        if user:
            user.is_admin = True
            db.session.commit()
            click.echo(f"User {email} promoted to admin.")
        else:
            user = User(email=email, name=name, is_admin=True)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            click.echo(f"Admin user created: {email}")
