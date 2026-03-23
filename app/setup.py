"""Setup wizard blueprint — auto-detects required integrations per checklist task."""

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.models import IntegrationConfig, Site
from app.dashboard import TASK_INTEGRATIONS, INTEGRATION_LABELS
from checklist.tasks import DAY_ORDER, WEEKLY_CHECKLIST

setup_bp = Blueprint("setup", __name__)

# Map each integration_type to the service_type(s) that satisfy it,
# and whether a Site is also needed.
INTEGRATION_REQUIREMENTS = {
    "website_health": {
        "label": "Website Health Check",
        "needs_site": True,
        "needs_api": None,
        "description": "Requires a site URL to perform HTTP health checks.",
        "setup_hint": "Add your website under Integrations → Add Site.",
    },
    "ssl_check": {
        "label": "SSL Certificate Check",
        "needs_site": True,
        "needs_api": None,
        "description": "Checks SSL cert validity and expiry for your site.",
        "setup_hint": "Add your website under Integrations → Add Site.",
    },
    "pagespeed": {
        "label": "PageSpeed Insights",
        "needs_site": True,
        "needs_api": "pagespeed",
        "description": "Google PageSpeed Insights for mobile + desktop performance.",
        "setup_hint": "Add a site and configure a PageSpeed API key (free from Google Cloud Console).",
        "setup_url": "https://console.cloud.google.com/apis/library/pagespeedonline.googleapis.com",
    },
    "link_check": {
        "label": "Broken Link Checker",
        "needs_site": True,
        "needs_api": None,
        "description": "Crawls your site pages to find broken links.",
        "setup_hint": "Add your website under Integrations → Add Site.",
    },
    "wordpress": {
        "label": "WordPress API",
        "needs_site": True,
        "needs_api": None,
        "description": "Manages plugins, themes, and core updates via WP REST API.",
        "setup_hint": "Add a WordPress site with Application Password credentials (Users → Edit → Application Passwords in WP admin).",
        "needs_wp_creds": True,
    },
    "search_console": {
        "label": "Google Search Console",
        "needs_site": False,
        "needs_api": "google_search_console",
        "description": "Monitors indexing errors, crawl issues, and keyword rankings.",
        "setup_hint": "Add a Google Search Console API integration with a service account JSON key.",
        "setup_url": "https://search.google.com/search-console",
    },
    "sitemap_check": {
        "label": "Sitemap Validator",
        "needs_site": True,
        "needs_api": None,
        "description": "Validates your XML sitemap is accessible and well-formed.",
        "setup_hint": "Add your website under Integrations → Add Site.",
    },
    "analytics": {
        "label": "Google Analytics (GA4)",
        "needs_site": False,
        "needs_api": "google_analytics",
        "description": "Reviews traffic, top pages, and performance metrics from GA4.",
        "setup_hint": "Add a Google Analytics API integration with a service account JSON key and property ID.",
        "setup_url": "https://analytics.google.com/",
    },
    "meta_check": {
        "label": "Meta Tags Checker",
        "needs_site": True,
        "needs_api": None,
        "description": "Checks meta titles, descriptions, and tracking pixels on your pages.",
        "setup_hint": "Add your website under Integrations → Add Site.",
    },
    "email_service": {
        "label": "Email Service (SendGrid / Mailgun)",
        "needs_site": False,
        "needs_api": "sendgrid|mailgun",
        "description": "Monitors bounce rates, spam complaints, and email delivery.",
        "setup_hint": "Add a SendGrid or Mailgun API integration with your API key.",
        "setup_url": "https://app.sendgrid.com/settings/api_keys",
    },
    "dns_check": {
        "label": "DNS Record Check",
        "needs_site": True,
        "needs_api": None,
        "description": "Verifies SPF, DKIM, and DMARC records for email authentication.",
        "setup_hint": "Add your website under Integrations → Add Site (domain is extracted from the URL).",
    },
    "api_health": {
        "label": "API Health Check",
        "needs_site": True,
        "needs_api": None,
        "description": "Pings your API endpoints to confirm they are responding.",
        "setup_hint": "Add your site/API URL under Integrations → Add Site.",
    },
    "uptime": {
        "label": "Uptime Monitor",
        "needs_site": False,
        "needs_api": "uptimerobot",
        "description": "Retrieves uptime status from UptimeRobot.",
        "setup_hint": "Add an UptimeRobot API integration with your read-only API key.",
        "setup_url": "https://dashboard.uptimerobot.com/integrations",
    },
    "server_monitor": {
        "label": "Server Monitor",
        "needs_site": True,
        "needs_api": None,
        "description": "Checks server health and resource usage.",
        "setup_hint": "Add your server/site URL under Integrations → Add Site.",
    },
    "manual": {
        "label": "Manual Task",
        "needs_site": False,
        "needs_api": None,
        "description": "Requires human action — cannot be automated.",
        "setup_hint": None,
    },
}


def _check_api_configured(configs, needs_api):
    """Check if any of the required API service types are configured."""
    if not needs_api:
        return True
    required_types = [t.strip() for t in needs_api.split("|")]
    for cfg in configs:
        if cfg.service_type in required_types and cfg.is_active:
            return True
    return False


def get_setup_status(user_id):
    """Analyze all checklist tasks and return setup status per integration type."""
    sites = Site.query.filter_by(user_id=user_id, is_active=True).all()
    configs = IntegrationConfig.query.filter_by(user_id=user_id, is_active=True).all()

    has_sites = len(sites) > 0
    has_wp_site = any(
        s.site_type == "wordpress" and s.get_credentials().get("username")
        for s in sites
    )

    # Collect unique integration types needed across all days
    needed_types = set()
    for day in DAY_ORDER:
        for task in WEEKLY_CHECKLIST[day]["tasks"]:
            itype = TASK_INTEGRATIONS.get(day, {}).get(task, "manual")
            if itype != "manual":
                needed_types.add(itype)

    # Build status for each required integration type
    results = {}
    for itype in sorted(needed_types):
        req = INTEGRATION_REQUIREMENTS.get(itype, {})
        needs_site = req.get("needs_site", False)
        needs_api = req.get("needs_api")
        needs_wp = req.get("needs_wp_creds", False)

        site_ok = (not needs_site) or has_sites
        wp_ok = (not needs_wp) or has_wp_site
        api_ok = _check_api_configured(configs, needs_api)

        ready = site_ok and wp_ok and api_ok

        missing = []
        if needs_site and not has_sites:
            missing.append("site")
        if needs_wp and not has_wp_site:
            missing.append("wordpress_credentials")
        if needs_api and not api_ok:
            missing.append(needs_api)

        # Find which tasks use this integration type
        tasks_using = []
        for day in DAY_ORDER:
            for task in WEEKLY_CHECKLIST[day]["tasks"]:
                if TASK_INTEGRATIONS.get(day, {}).get(task) == itype:
                    tasks_using.append({"day": day, "task": task})

        results[itype] = {
            "label": req.get("label", itype),
            "description": req.get("description", ""),
            "setup_hint": req.get("setup_hint", ""),
            "setup_url": req.get("setup_url", ""),
            "ready": ready,
            "missing": missing,
            "tasks": tasks_using,
            "task_count": len(tasks_using),
        }

    # Summary counts
    total = len(results)
    ready_count = sum(1 for v in results.values() if v["ready"])
    manual_count = sum(
        1 for day in DAY_ORDER
        for task in WEEKLY_CHECKLIST[day]["tasks"]
        if TASK_INTEGRATIONS.get(day, {}).get(task) == "manual"
    )

    return {
        "integrations": results,
        "total": total,
        "ready": ready_count,
        "missing": total - ready_count,
        "manual_tasks": manual_count,
        "has_sites": has_sites,
        "has_wp": has_wp_site,
        "site_count": len(sites),
        "api_count": len(configs),
    }


@setup_bp.route("/")
@login_required
def index():
    status = get_setup_status(current_user.id)
    return render_template(
        "setup.html",
        status=status,
        integration_labels=INTEGRATION_LABELS,
        day_order=DAY_ORDER,
        checklist=WEEKLY_CHECKLIST,
        task_integrations=TASK_INTEGRATIONS,
    )
