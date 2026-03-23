"""Dashboard blueprint — main checklist view with integration status."""

import json
from datetime import datetime, timedelta

from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required

from app.models import CustomTask, IntegrationConfig, Site, TaskRun
from checklist.tasks import DAY_ORDER, WEEKLY_CHECKLIST

dashboard_bp = Blueprint("dashboard", __name__)


def get_merged_checklist(user_id):
    """Return WEEKLY_CHECKLIST merged with the user's custom tasks."""
    custom_tasks = (
        CustomTask.query
        .filter_by(user_id=user_id, is_active=True)
        .all()
    )
    merged = {}
    for day, data in WEEKLY_CHECKLIST.items():
        merged[day] = {
            "label": data["label"],
            "tasks": list(data["tasks"]),
        }
    for ct in custom_tasks:
        if ct.day in merged:
            merged[ct.day]["tasks"].append(ct.task_name)
    return merged


def get_merged_task_integrations(user_id):
    """Return TASK_INTEGRATIONS merged with the user's custom task types."""
    custom_tasks = (
        CustomTask.query
        .filter_by(user_id=user_id, is_active=True)
        .all()
    )
    merged = {day: dict(tasks) for day, tasks in TASK_INTEGRATIONS.items()}
    for ct in custom_tasks:
        if ct.day not in merged:
            merged[ct.day] = {}
        merged[ct.day][ct.task_name] = ct.integration_type
    return merged

# Map every checklist task to the integration type that can automate it.
TASK_INTEGRATIONS = {
    "Monday": {
        "Check all websites are live": "website_health",
        "Open homepage, login, dashboard, and key pages": "website_health",
        "Check SSL certificates (no warnings)": "ssl_check",
        "Test forms (contact, signup, payments)": "manual",
        "Run speed test (mobile + desktop)": "pagespeed",
        "Fix broken links (if any)": "link_check",
        "Update CMS": "wordpress",
        "Update plugins/extensions": "wordpress",
        "Remove unused plugins/themes": "wordpress",
    },
    "Tuesday": {
        "Check Google Search Console for errors": "search_console",
        "Fix indexing/crawl issues": "search_console",
        "Confirm sitemap is valid": "sitemap_check",
        "Review traffic in GA4": "analytics",
        "Check top-performing pages": "analytics",
        "Review keyword rankings": "search_console",
        "Verify tracking pixels (Meta, Google Ads)": "meta_check",
        "Review meta titles/descriptions": "meta_check",
    },
    "Wednesday": {
        "Check email dashboard (SendGrid/Mailgun/etc.)": "email_service",
        "Review bounce rate": "email_service",
        "Review spam complaints": "email_service",
        "Send test email (confirm inbox delivery)": "email_service",
        "Check spam placement": "manual",
        "Verify SPF record": "dns_check",
        "Verify DKIM record": "dns_check",
        "Verify DMARC record": "dns_check",
        "Test OTP, password reset, and alerts": "manual",
    },
    "Thursday": {
        "Log into LIMS and confirm access": "api_health",
        "Check recent data entries": "api_health",
        "Test report generation": "manual",
        "Test exports/downloads": "manual",
        "Confirm integrations are syncing": "api_health",
        "Review user permissions": "manual",
        "Check audit logs": "api_health",
        "Confirm no system errors": "api_health",
    },
    "Friday": {
        "Check internal dashboards/admin panels": "website_health",
        "Confirm data is updating correctly": "api_health",
        "Test core workflows end-to-end": "manual",
        "Review API logs (errors/slow responses)": "api_health",
        "Check uptime monitoring alerts": "uptime",
        "Review server usage (CPU, RAM, bandwidth)": "server_monitor",
        "Investigate any incidents from the week": "manual",
    },
}

INTEGRATION_LABELS = {
    "website_health": {"label": "Website Health", "icon": "🌐", "auto": True},
    "ssl_check":      {"label": "SSL Check",      "icon": "🔒", "auto": True},
    "pagespeed":      {"label": "PageSpeed",       "icon": "⚡", "auto": True},
    "link_check":     {"label": "Link Check",      "icon": "🔗", "auto": True},
    "wordpress":      {"label": "WordPress API",   "icon": "📝", "auto": True},
    "search_console": {"label": "Search Console",  "icon": "🔍", "auto": True},
    "sitemap_check":  {"label": "Sitemap Check",   "icon": "🗺️", "auto": True},
    "analytics":      {"label": "Analytics",        "icon": "📊", "auto": True},
    "meta_check":     {"label": "Meta Tags",        "icon": "🏷️", "auto": True},
    "email_service":  {"label": "Email Service",    "icon": "📧", "auto": True},
    "dns_check":      {"label": "DNS Check",        "icon": "📡", "auto": True},
    "api_health":     {"label": "API Health",        "icon": "🔌", "auto": True},
    "uptime":         {"label": "Uptime Monitor",   "icon": "📈", "auto": True},
    "server_monitor": {"label": "Server Monitor",   "icon": "🖥️", "auto": True},
    "manual":         {"label": "Manual",            "icon": "👤", "auto": False},
}

DAY_COLORS = {
    "Monday":    "#3b82f6",
    "Tuesday":   "#8b5cf6",
    "Wednesday": "#14b8a6",
    "Thursday":  "#f59e0b",
    "Friday":    "#10b981",
}


@dashboard_bp.route("/")
@login_required
def index():
    sites = Site.query.filter_by(user_id=current_user.id, is_active=True).all()
    integrations = IntegrationConfig.query.filter_by(
        user_id=current_user.id, is_active=True
    ).all()

    checklist = get_merged_checklist(current_user.id)
    task_ints = get_merged_task_integrations(current_user.id)

    # Latest run per (day, task)
    all_runs = (
        TaskRun.query
        .filter_by(user_id=current_user.id)
        .order_by(TaskRun.run_at.desc())
        .all()
    )
    task_status: dict = {}
    for run in all_runs:
        key = f"{run.day}:{run.task_name}"
        if key not in task_status:
            task_status[key] = run

    # Today's stats
    today_start = datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today_runs = [r for r in all_runs if r.run_at and r.run_at >= today_start]
    total_today = len(today_runs)
    success_today = sum(1 for r in today_runs if r.status == "success")

    # Recent activity (latest 15)
    recent_runs = all_runs[:15]

    # Setup status for banner
    from app.setup import get_setup_status
    setup_status = get_setup_status(current_user.id)

    return render_template(
        "dashboard.html",
        day_order=DAY_ORDER,
        checklist=checklist,
        task_integrations=task_ints,
        integration_labels=INTEGRATION_LABELS,
        day_colors=DAY_COLORS,
        sites=sites,
        integrations=integrations,
        task_status=task_status,
        recent_runs=recent_runs,
        total_today=total_today,
        success_today=success_today,
        total_sites=len(sites),
        total_integrations=len(integrations),
        setup_status=setup_status,
    )


@dashboard_bp.route("/day/<day>")
@login_required
def day_detail(day):
    if day not in WEEKLY_CHECKLIST:
        abort(404)

    sites = Site.query.filter_by(user_id=current_user.id, is_active=True).all()
    integrations = IntegrationConfig.query.filter_by(
        user_id=current_user.id, is_active=True
    ).all()

    checklist = get_merged_checklist(current_user.id)
    task_ints = get_merged_task_integrations(current_user.id)

    day_data = checklist[day]
    tasks = day_data["tasks"]
    color = DAY_COLORS[day]

    # All runs for this day, grouped by (task, site)
    day_runs = (
        TaskRun.query
        .filter_by(user_id=current_user.id, day=day)
        .order_by(TaskRun.run_at.desc())
        .all()
    )

    # Latest run per (task, site_id) — to show current status per site
    latest_by_task_site = {}
    for run in day_runs:
        key = (run.task_name, run.site_id)
        if key not in latest_by_task_site:
            latest_by_task_site[key] = run

    # Build per-task detail with per-site results
    task_details = []
    for task in tasks:
        int_type = task_ints.get(day, {}).get(task, "manual")
        int_info = INTEGRATION_LABELS.get(int_type, {})

        site_results = []
        for site in sites:
            run = latest_by_task_site.get((task, site.id))
            result_data = {}
            if run and run.result_data:
                try:
                    result_data = json.loads(run.result_data)
                except (json.JSONDecodeError, TypeError):
                    pass
            site_results.append({
                "site": site,
                "run": run,
                "result_data": result_data,
            })

        # Also include runs with no site
        no_site_run = latest_by_task_site.get((task, None))

        task_details.append({
            "name": task,
            "integration_type": int_type,
            "integration_info": int_info,
            "site_results": site_results,
            "no_site_run": no_site_run,
        })

    # Aggregate stats for this day
    total_runs = len(day_runs)
    success_runs = sum(1 for r in day_runs if r.status == "success")
    failure_runs = sum(1 for r in day_runs if r.status == "failure")
    warning_runs = sum(1 for r in day_runs if r.status == "warning")
    skipped_runs = sum(1 for r in day_runs if r.status == "skipped")
    avg_duration = (
        int(sum(r.duration_ms or 0 for r in day_runs) / total_runs)
        if total_runs else 0
    )

    # Broken links collected from result_data
    broken_links = []
    for run in day_runs:
        if run.integration_type == "link_check" and run.result_data:
            try:
                data = json.loads(run.result_data)
                for link in data.get("broken", []):
                    broken_links.append({
                        "url": link.get("url", ""),
                        "status": link.get("status", ""),
                        "site": run.site.name if run.site else "Unknown",
                        "checked_at": run.run_at,
                    })
            except (json.JSONDecodeError, TypeError):
                pass

    # Run history (latest 30 for this day)
    recent_day_runs = day_runs[:30]

    # Per-site summary for this day
    site_summaries = []
    for site in sites:
        site_runs = [r for r in day_runs if r.site_id == site.id]
        latest_runs = {}
        for r in site_runs:
            if r.task_name not in latest_runs:
                latest_runs[r.task_name] = r
        s_ok = sum(1 for r in latest_runs.values() if r.status == "success")
        s_fail = sum(1 for r in latest_runs.values() if r.status == "failure")
        s_warn = sum(1 for r in latest_runs.values() if r.status == "warning")
        s_skip = sum(1 for r in latest_runs.values() if r.status == "skipped")
        site_summaries.append({
            "site": site,
            "total": len(latest_runs),
            "success": s_ok,
            "failure": s_fail,
            "warning": s_warn,
            "skipped": s_skip,
            "pct": int(s_ok / len(tasks) * 100) if tasks else 0,
        })

    return render_template(
        "day_detail.html",
        day=day,
        day_data=day_data,
        color=color,
        day_order=DAY_ORDER,
        tasks=tasks,
        task_details=task_details,
        task_integrations=task_ints,
        integration_labels=INTEGRATION_LABELS,
        sites=sites,
        broken_links=broken_links,
        recent_day_runs=recent_day_runs,
        site_summaries=site_summaries,
        total_runs=total_runs,
        success_runs=success_runs,
        failure_runs=failure_runs,
        warning_runs=warning_runs,
        skipped_runs=skipped_runs,
        avg_duration=avg_duration,
    )
