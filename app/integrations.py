"""Integrations blueprint — CRUD for sites & API configs, task execution."""

import csv
import io
import json
import secrets
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

from flask import (
    Blueprint, Response, flash, redirect, render_template,
    request, session, url_for,
)
from flask_login import current_user, login_required

from app import db
from app.models import (
    INTEGRATION_TYPES,
    ActivityLog,
    IntegrationConfig,
    Site,
    TaskRun,
)
from app.dashboard import TASK_INTEGRATIONS, INTEGRATION_LABELS, get_merged_checklist, get_merged_task_integrations
from checklist.tasks import DAY_ORDER, WEEKLY_CHECKLIST

integrations_bp = Blueprint("integrations", __name__)


# ── List ────────────────────────────────────────────────────────────

@integrations_bp.route("/")
@login_required
def index():
    sites = Site.query.filter_by(user_id=current_user.id).order_by(Site.created_at.desc()).all()
    configs = (
        IntegrationConfig.query
        .filter_by(user_id=current_user.id)
        .order_by(IntegrationConfig.created_at.desc())
        .all()
    )
    return render_template(
        "integrations.html",
        sites=sites,
        configs=configs,
        integration_types=INTEGRATION_TYPES,
    )


# ── Sites CRUD ──────────────────────────────────────────────────────

@integrations_bp.route("/sites/add", methods=["GET", "POST"])
@login_required
def add_site():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        url = request.form.get("url", "").strip()
        site_type = request.form.get("site_type", "wordpress")

        if not name or not url:
            flash("Name and URL are required.", "error")
            return redirect(url_for("integrations.add_site"))

        site = Site(user_id=current_user.id, name=name, url=url, site_type=site_type)

        creds = {}
        if site_type == "wordpress":
            wp_user = request.form.get("wp_username", "").strip()
            wp_pass = request.form.get("wp_app_password", "").strip()
            if wp_user and wp_pass:
                creds = {"username": wp_user, "app_password": wp_pass}
        pages = request.form.get("pages", "").strip()
        if pages:
            creds["pages"] = [p.strip() for p in pages.split(",") if p.strip()]
        if creds:
            site.set_credentials(creds)

        db.session.add(site)
        _log("site_added", "integrations", f"Added site: {name}")
        db.session.commit()
        flash(f"Site '{name}' added.", "success")
        return redirect(url_for("integrations.index"))

    return render_template("configure.html", mode="add_site")


@integrations_bp.route("/sites/<int:site_id>/edit", methods=["GET", "POST"])
@login_required
def edit_site(site_id):
    site = Site.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        site.name = request.form.get("name", site.name).strip()
        site.url = request.form.get("url", site.url).strip()
        site.site_type = request.form.get("site_type", site.site_type)

        creds = site.get_credentials()
        if site.site_type == "wordpress":
            wp_user = request.form.get("wp_username", "").strip()
            wp_pass = request.form.get("wp_app_password", "").strip()
            if wp_user:
                creds["username"] = wp_user
            if wp_pass:
                creds["app_password"] = wp_pass
        pages = request.form.get("pages", "").strip()
        if pages:
            creds["pages"] = [p.strip() for p in pages.split(",") if p.strip()]
        site.set_credentials(creds)

        _log("site_updated", "integrations", f"Updated site: {site.name}")
        db.session.commit()
        flash(f"Site '{site.name}' updated.", "success")
        return redirect(url_for("integrations.index"))

    return render_template("configure.html", mode="edit_site", site=site)


@integrations_bp.route("/sites/<int:site_id>/delete", methods=["POST"])
@login_required
def delete_site(site_id):
    site = Site.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    name = site.name
    db.session.delete(site)
    _log("site_deleted", "integrations", f"Deleted site: {name}")
    db.session.commit()
    flash(f"Site '{name}' deleted.", "success")
    return redirect(url_for("integrations.index"))


# ── API Integration Config CRUD ──────────────────────────────────

@integrations_bp.route("/apis/add", methods=["GET", "POST"])
@login_required
def add_api():
    if request.method == "POST":
        service = request.form.get("service_type", "")
        label = request.form.get("label", "").strip()

        if service not in INTEGRATION_TYPES:
            flash("Invalid service type.", "error")
            return redirect(url_for("integrations.add_api"))

        config_data = {}
        for field in INTEGRATION_TYPES[service]["fields"]:
            val = request.form.get(field["name"], "").strip()
            if val:
                config_data[field["name"]] = val

        cfg = IntegrationConfig(
            user_id=current_user.id,
            service_type=service,
            label=label or INTEGRATION_TYPES[service]["label"],
        )
        cfg.set_config(config_data)

        db.session.add(cfg)
        _log("api_added", "integrations",
             f"Added {INTEGRATION_TYPES[service]['label']} integration")
        db.session.commit()
        flash(f"{INTEGRATION_TYPES[service]['label']} integration added.", "success")
        return redirect(url_for("integrations.index"))

    return render_template(
        "configure.html", mode="add_api", integration_types=INTEGRATION_TYPES
    )


@integrations_bp.route("/apis/<int:cfg_id>/edit", methods=["GET", "POST"])
@login_required
def edit_api(cfg_id):
    cfg = IntegrationConfig.query.filter_by(
        id=cfg_id, user_id=current_user.id
    ).first_or_404()

    if request.method == "POST":
        cfg.label = request.form.get("label", cfg.label).strip()
        config_data = cfg.get_config()
        stype = cfg.service_type
        for field in INTEGRATION_TYPES.get(stype, {}).get("fields", []):
            val = request.form.get(field["name"], "").strip()
            if val:
                config_data[field["name"]] = val
        cfg.set_config(config_data)

        _log("api_updated", "integrations", f"Updated integration: {cfg.label}")
        db.session.commit()
        flash(f"Integration '{cfg.label}' updated.", "success")
        return redirect(url_for("integrations.index"))

    return render_template(
        "configure.html", mode="edit_api", cfg=cfg,
        integration_types=INTEGRATION_TYPES,
    )


@integrations_bp.route("/apis/<int:cfg_id>/delete", methods=["POST"])
@login_required
def delete_api(cfg_id):
    cfg = IntegrationConfig.query.filter_by(
        id=cfg_id, user_id=current_user.id
    ).first_or_404()
    label = cfg.label
    db.session.delete(cfg)
    _log("api_deleted", "integrations", f"Deleted integration: {label}")
    db.session.commit()
    flash(f"Integration '{label}' deleted.", "success")
    return redirect(url_for("integrations.index"))


# ── Task Execution ──────────────────────────────────────────────────

@integrations_bp.route("/run/<day>/<int:task_index>", methods=["POST"])
@login_required
def run_task(day, task_index):
    checklist = get_merged_checklist(current_user.id)
    if day not in checklist:
        flash("Invalid day.", "error")
        return redirect(url_for("dashboard.index"))

    tasks = checklist[day]["tasks"]
    if task_index < 0 or task_index >= len(tasks):
        flash("Invalid task.", "error")
        return redirect(url_for("dashboard.index"))

    task_name = tasks[task_index]
    task_ints = get_merged_task_integrations(current_user.id)
    integration_type = task_ints.get(day, {}).get(task_name, "manual")

    # Collect site IDs — supports both single and multi-site
    site_ids = request.form.getlist("site_ids", type=int)
    if not site_ids:
        single = request.form.get("site_id", type=int)
        if single:
            site_ids = [single]

    sites = []
    if site_ids:
        sites = Site.query.filter(
            Site.id.in_(site_ids), Site.user_id == current_user.id
        ).all()

    batch_id = uuid.uuid4().hex

    if not sites:
        # Run once without a site
        result = _execute_task(integration_type, task_name, None)
        _save_run(day, task_name, integration_type, None, result, batch_id)
    else:
        for site in sites:
            result = _execute_task(integration_type, task_name, site)
            _save_run(day, task_name, integration_type, site, result, batch_id)

    db.session.commit()
    return redirect(url_for("integrations.run_results", batch_id=batch_id))


@integrations_bp.route("/run-day/<day>", methods=["POST"])
@login_required
def run_day(day):
    checklist = get_merged_checklist(current_user.id)
    if day not in checklist:
        flash("Invalid day.", "error")
        return redirect(url_for("dashboard.index"))

    # Collect site IDs — supports both single and multi-site
    site_ids = request.form.getlist("site_ids", type=int)
    if not site_ids:
        single = request.form.get("site_id", type=int)
        if single:
            site_ids = [single]

    sites = []
    if site_ids:
        sites = Site.query.filter(
            Site.id.in_(site_ids), Site.user_id == current_user.id
        ).all()

    tasks = checklist[day]["tasks"]
    task_ints = get_merged_task_integrations(current_user.id)
    targets = sites if sites else [None]
    batch_id = uuid.uuid4().hex

    ok = fail = skip = 0
    for site in targets:
        for task_name in tasks:
            integration_type = task_ints.get(day, {}).get(task_name, "manual")
            result = _execute_task(integration_type, task_name, site)
            _save_run(day, task_name, integration_type, site, result, batch_id)
            if result["status"] == "success":
                ok += 1
            elif result["status"] in ("failure", "error"):
                fail += 1
            else:
                skip += 1

    site_label = ", ".join(s.name for s in sites) if sites else "no site"
    _log("day_run", "execution",
         f"Ran all {day} tasks on [{site_label}] — {ok} ok, {fail} fail, {skip} skipped")
    db.session.commit()
    return redirect(url_for("integrations.run_results", batch_id=batch_id))


# ── Run Results Page ────────────────────────────────────────────────

@integrations_bp.route("/results/<batch_id>")
@login_required
def run_results(batch_id):
    runs = (
        TaskRun.query
        .filter_by(user_id=current_user.id, batch_id=batch_id)
        .order_by(TaskRun.run_at.asc())
        .all()
    )
    if not runs:
        flash("No results found for this run.", "error")
        return redirect(url_for("dashboard.index"))

    # Aggregate stats
    ok = sum(1 for r in runs if r.status == "success")
    fail = sum(1 for r in runs if r.status in ("failure", "error"))
    warn = sum(1 for r in runs if r.status == "warning")
    skip = sum(1 for r in runs if r.status == "skipped")
    total_ms = sum(r.duration_ms or 0 for r in runs)
    day = runs[0].day

    # Parse result_data JSON for each run
    for r in runs:
        try:
            r._parsed_data = json.loads(r.result_data) if r.result_data else {}
        except (json.JSONDecodeError, TypeError):
            r._parsed_data = {}

    # Group by site
    site_groups = {}
    for r in runs:
        site_key = r.site.name if r.site else "No Site"
        site_groups.setdefault(site_key, []).append(r)

    # Build detailed report data for the template
    report = _build_report_data(runs, day, batch_id, ok, fail, warn, skip,
                                total_ms, site_groups)

    # ── Daily Recommendations ───────────────────────────────────────
    recommendations = _generate_recommendations(runs, report)

    # ── Analytics ───────────────────────────────────────────────────
    analytics = _build_analytics(runs, day)

    return render_template(
        "run_results.html",
        runs=runs,
        batch_id=batch_id,
        day=day,
        ok=ok,
        fail=fail,
        warn=warn,
        skip=skip,
        total=len(runs),
        total_ms=total_ms,
        site_groups=site_groups,
        integration_labels=INTEGRATION_LABELS,
        report=report,
        recommendations=recommendations,
        analytics=analytics,
    )


# ── OAuth / Connect Flows ──────────────────────────────────────────

@integrations_bp.route("/connect/wordpress/<int:site_id>")
@login_required
def connect_wordpress(site_id):
    """Redirect the user to the WordPress Application Passwords auth screen.

    WordPress 5.6+ supports the ``authorize-application.php`` endpoint which
    lets users approve an application and have the app-password returned via
    a callback URL automatically.
    """
    site = Site.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    base = site.url.rstrip("/")
    # Generate a nonce to protect the callback
    nonce = secrets.token_urlsafe(24)
    session["wp_connect_nonce"] = nonce
    session["wp_connect_site_id"] = site.id

    callback = url_for("integrations.callback_wordpress", _external=True)
    params = urlencode({
        "app_name": "TechCheck Dashboard",
        "app_id": str(uuid.uuid4()),
        "success_url": callback,
    })
    wp_auth_url = f"{base}/wp-admin/authorize-application.php?{params}"
    return redirect(wp_auth_url)


@integrations_bp.route("/callback/wordpress")
@login_required
def callback_wordpress():
    """Receive WordPress application-password credentials from the WP redirect."""
    user_login = request.args.get("user_login", "").strip()
    password = request.args.get("password", "").strip()
    site_url = request.args.get("site_url", "").strip()

    site_id = session.pop("wp_connect_site_id", None)
    session.pop("wp_connect_nonce", None)

    if not user_login or not password or not site_id:
        flash("WordPress authorisation failed — missing credentials.", "error")
        return redirect(url_for("integrations.index"))

    site = Site.query.filter_by(id=site_id, user_id=current_user.id).first()
    if not site:
        flash("Site not found.", "error")
        return redirect(url_for("integrations.index"))

    creds = site.get_credentials()
    creds["username"] = user_login
    creds["app_password"] = password
    site.set_credentials(creds)

    _log("wp_connected", "integrations",
         f"WordPress connected for {site.name} via Application Password")
    db.session.commit()
    flash(f"WordPress connected for '{site.name}' — credentials saved automatically!", "success")
    return redirect(url_for("integrations.index"))


@integrations_bp.route("/connect/google/<service>")
@login_required
def connect_google(service):
    """Start Google OAuth 2.0 flow for Analytics / Search Console / PageSpeed."""
    from flask import current_app
    client_id = current_app.config.get("GOOGLE_CLIENT_ID", "")
    if not client_id:
        flash("Google OAuth not configured — add GOOGLE_CLIENT_ID and "
              "GOOGLE_CLIENT_SECRET to your environment variables. "
              "Create credentials at console.cloud.google.com/apis/credentials",
              "error")
        return redirect(url_for("integrations.index"))

    scopes = {
        "google_analytics": "https://www.googleapis.com/auth/analytics.readonly",
        "google_search_console": "https://www.googleapis.com/auth/webmasters.readonly",
        "pagespeed": "https://www.googleapis.com/auth/cloud-platform",
    }
    scope = scopes.get(service, "openid email")
    nonce = secrets.token_urlsafe(24)
    session["google_oauth_state"] = nonce
    session["google_oauth_service"] = service

    callback = url_for("integrations.callback_google", _external=True)
    params = urlencode({
        "client_id": client_id,
        "redirect_uri": callback,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
        "state": nonce,
    })
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@integrations_bp.route("/callback/google")
@login_required
def callback_google():
    """Handle Google OAuth callback — exchange code for tokens."""
    import requests as http_requests
    from flask import current_app

    code = request.args.get("code", "")
    state = request.args.get("state", "")
    saved_state = session.pop("google_oauth_state", "")
    service = session.pop("google_oauth_service", "")

    if not code or state != saved_state or not service:
        flash("Google authorisation failed or expired.", "error")
        return redirect(url_for("integrations.index"))

    client_id = current_app.config.get("GOOGLE_CLIENT_ID", "")
    client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET", "")
    callback = url_for("integrations.callback_google", _external=True)

    # Exchange code for tokens
    try:
        resp = http_requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": callback,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        tokens = resp.json()
    except Exception as exc:
        flash(f"Failed to exchange Google auth code: {exc}", "error")
        return redirect(url_for("integrations.index"))

    if "access_token" not in tokens:
        err = tokens.get("error_description", tokens.get("error", "unknown error"))
        flash(f"Google OAuth error: {err}", "error")
        return redirect(url_for("integrations.index"))

    # Save as IntegrationConfig
    info = INTEGRATION_TYPES.get(service, {})
    cfg = IntegrationConfig(
        user_id=current_user.id,
        service_type=service,
        label=f"{info.get('label', service)} (OAuth)",
    )
    cfg.set_config({
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "token_type": tokens.get("token_type", "Bearer"),
        "expires_in": tokens.get("expires_in", 3600),
        "connected_via": "oauth",
    })
    db.session.add(cfg)
    _log("google_connected", "integrations",
         f"Connected {info.get('label', service)} via Google OAuth")
    db.session.commit()
    flash(f"{info.get('label', service)} connected via Google OAuth!", "success")
    return redirect(url_for("integrations.index"))


@integrations_bp.route("/connect/<service_type>")
@login_required
def connect_api(service_type):
    """Show a guided connect wizard for API-key services.

    Opens the provider dashboard in a new tab and provides a callback
    URL that can receive the API key via form-post or query parameter.
    """
    if service_type in ("google_analytics", "google_search_console", "pagespeed"):
        return redirect(url_for("integrations.connect_google", service=service_type))

    info = INTEGRATION_TYPES.get(service_type)
    if not info:
        flash("Unknown service type.", "error")
        return redirect(url_for("integrations.index"))

    # Generate a one-time connect token
    token = secrets.token_urlsafe(32)
    session["connect_token"] = token
    session["connect_service"] = service_type

    return render_template(
        "connect_wizard.html",
        service_type=service_type,
        info=info,
        connect_token=token,
        callback_url=url_for("integrations.callback_api",
                             service_type=service_type, _external=True),
    )


@integrations_bp.route("/callback/<service_type>", methods=["GET", "POST"])
@login_required
def callback_api(service_type):
    """Receive API key from the connect wizard form."""
    info = INTEGRATION_TYPES.get(service_type)
    if not info:
        flash("Unknown service type.", "error")
        return redirect(url_for("integrations.index"))

    # Collect fields from either GET params or POST form
    config_data = {}
    for field in info.get("fields", []):
        val = (request.form.get(field["name"], "")
               or request.args.get(field["name"], "")).strip()
        if val:
            config_data[field["name"]] = val

    if not config_data:
        flash(f"No credentials provided for {info['label']}.", "error")
        return redirect(url_for("integrations.connect_api",
                                service_type=service_type))

    cfg = IntegrationConfig(
        user_id=current_user.id,
        service_type=service_type,
        label=f"{info['label']} (auto-connected)",
    )
    cfg.set_config(config_data)
    db.session.add(cfg)
    _log("api_auto_connected", "integrations",
         f"Connected {info['label']} via connect wizard")
    db.session.commit()

    session.pop("connect_token", None)
    session.pop("connect_service", None)
    flash(f"{info['label']} connected successfully!", "success")
    return redirect(url_for("integrations.index"))


# ── Connection Tests ────────────────────────────────────────────────

@integrations_bp.route("/test-site/<int:site_id>")
@login_required
def test_site(site_id):
    """Quick connectivity test for a site — checks HTTP reachability."""
    import requests as http_requests

    site = Site.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    url = site.url.rstrip("/")

    try:
        resp = http_requests.get(url, timeout=10, allow_redirects=True)
        if resp.status_code < 400:
            # Check WP REST API if wordpress
            wp_ok = False
            if site.site_type == "wordpress":
                creds = site.get_credentials()
                if creds.get("username") and creds.get("app_password"):
                    try:
                        wp_resp = http_requests.get(
                            f"{url}/wp-json/wp/v2/plugins",
                            auth=(creds["username"], creds["app_password"]),
                            timeout=10,
                        )
                        wp_ok = wp_resp.status_code < 400
                    except Exception:
                        pass
                    if wp_ok:
                        flash(f"✓ '{site.name}' is reachable and WordPress API credentials are valid!", "success")
                    else:
                        flash(f"⚠ '{site.name}' is reachable but WordPress API credentials failed. "
                              "Re-connect or update your Application Password.", "warning")
                else:
                    flash(f"✓ '{site.name}' is reachable (HTTP {resp.status_code}). "
                          "Connect WordPress credentials to enable plugin/theme checks.", "warning")
            else:
                flash(f"✓ '{site.name}' is reachable — HTTP {resp.status_code}, "
                      f"response in {resp.elapsed.total_seconds():.2f}s", "success")
        else:
            flash(f"✗ '{site.name}' returned HTTP {resp.status_code}.", "error")
    except http_requests.ConnectionError:
        flash(f"✗ Cannot reach '{site.name}' — connection failed.", "error")
    except http_requests.Timeout:
        flash(f"✗ '{site.name}' did not respond within 10 seconds.", "error")
    except Exception as exc:
        flash(f"✗ Error testing '{site.name}': {str(exc)[:150]}", "error")

    return redirect(url_for("integrations.index"))


@integrations_bp.route("/test-api/<int:cfg_id>")
@login_required
def test_api(cfg_id):
    """Quick connectivity test for an API integration — validates credentials."""
    import requests as http_requests

    cfg = IntegrationConfig.query.filter_by(
        id=cfg_id, user_id=current_user.id
    ).first_or_404()
    config_data = cfg.get_config()
    stype = cfg.service_type

    try:
        if stype == "sendgrid":
            api_key = config_data.get("api_key", "")
            resp = http_requests.get(
                "https://api.sendgrid.com/v3/user/profile",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            if resp.status_code == 200:
                flash(f"✓ SendGrid connection verified — API key is valid!", "success")
            else:
                flash(f"✗ SendGrid returned HTTP {resp.status_code}. Check your API key.", "error")

        elif stype == "mailgun":
            api_key = config_data.get("api_key", "")
            domain = config_data.get("domain", "")
            resp = http_requests.get(
                f"https://api.mailgun.net/v3/{domain}",
                auth=("api", api_key),
                timeout=10,
            )
            if resp.status_code == 200:
                flash(f"✓ Mailgun connection verified for domain '{domain}'!", "success")
            else:
                flash(f"✗ Mailgun returned HTTP {resp.status_code}. Check API key & domain.", "error")

        elif stype == "uptimerobot":
            api_key = config_data.get("api_key", "")
            resp = http_requests.post(
                "https://api.uptimerobot.com/v2/getAccountDetails",
                data={"api_key": api_key, "format": "json"},
                timeout=10,
            )
            data = resp.json()
            if data.get("stat") == "ok":
                flash(f"✓ UptimeRobot connection verified!", "success")
            else:
                flash(f"✗ UptimeRobot: {data.get('error', {}).get('message', 'Invalid API key')}.", "error")

        elif stype in ("google_analytics", "google_search_console", "pagespeed"):
            token = config_data.get("access_token", "")
            resp = http_requests.get(
                "https://www.googleapis.com/oauth2/v1/tokeninfo",
                params={"access_token": token},
                timeout=10,
            )
            if resp.status_code == 200:
                flash(f"✓ Google OAuth token is valid!", "success")
            else:
                flash(f"✗ Google token may have expired. Try re-connecting.", "warning")
        else:
            flash(f"Test not available for {cfg.label}.", "warning")

    except http_requests.ConnectionError:
        flash(f"✗ Cannot reach {cfg.label} API — connection failed.", "error")
    except http_requests.Timeout:
        flash(f"✗ {cfg.label} API did not respond within 10 seconds.", "error")
    except Exception as exc:
        flash(f"✗ Error testing {cfg.label}: {str(exc)[:150]}", "error")

    return redirect(url_for("integrations.index"))


# ── Reports ─────────────────────────────────────────────────────────

@integrations_bp.route("/results/<batch_id>/report/csv")
@login_required
def download_report_csv(batch_id):
    """Download batch results as a CSV report."""
    runs = (
        TaskRun.query
        .filter_by(user_id=current_user.id, batch_id=batch_id)
        .order_by(TaskRun.run_at.asc())
        .all()
    )
    if not runs:
        flash("No results found.", "error")
        return redirect(url_for("dashboard.index"))

    ok = sum(1 for r in runs if r.status == "success")
    fail = sum(1 for r in runs if r.status in ("failure", "error"))
    warn = sum(1 for r in runs if r.status == "warning")
    skip = sum(1 for r in runs if r.status == "skipped")
    total_ms = sum(r.duration_ms or 0 for r in runs)
    day = runs[0].day

    site_groups = {}
    for r in runs:
        key = r.site.name if r.site else "No Site"
        site_groups.setdefault(key, []).append(r)

    report = _build_report_data(runs, day, batch_id, ok, fail, warn, skip,
                                total_ms, site_groups)

    output = io.StringIO()
    writer = csv.writer(output)

    # Summary section
    writer.writerow(["WEEKLY TECH CHECKLIST REPORT"])
    writer.writerow(["Day", day])
    writer.writerow(["Batch ID", batch_id])
    writer.writerow(["Generated", report["generated_at"]])
    writer.writerow(["Total Checks", report["summary"]["total"]])
    writer.writerow(["Passed", report["summary"]["passed"]])
    writer.writerow(["Failed", report["summary"]["failed"]])
    writer.writerow(["Warnings", report["summary"]["warnings"]])
    writer.writerow(["Skipped", report["summary"]["skipped"]])
    writer.writerow(["Pass Rate", f"{report['summary']['pass_rate']}%"])
    writer.writerow(["Total Duration (ms)", report["summary"]["duration_ms"]])
    writer.writerow([])

    # All checks
    writer.writerow(["ALL CHECKS"])
    writer.writerow(["Task", "Site", "Type", "Status", "Summary", "Duration (ms)", "Time"])
    for c in report["all_checks"]:
        writer.writerow([c["task"], c["site"], c["type"], c["status"],
                         c["summary"], c["duration_ms"], c["time"]])
    writer.writerow([])

    # Plugins
    if report["plugins"]:
        writer.writerow(["WORDPRESS PLUGINS"])
        writer.writerow(["Site", "Plugin Name", "Version", "Status", "Update Available"])
        for p in report["plugins"]:
            writer.writerow([p["site"], p["name"], p["version"],
                             p["status"], p["update_available"]])
        writer.writerow([])

    # Themes
    if report["themes"]:
        writer.writerow(["WORDPRESS THEMES"])
        writer.writerow(["Site", "Theme Name", "Status"])
        for t in report["themes"]:
            writer.writerow([t["site"], t["name"], t["status"]])
        writer.writerow([])

    # Broken links
    if report["broken_links"]:
        writer.writerow(["BROKEN LINKS"])
        writer.writerow(["Site", "URL", "HTTP Status"])
        for b in report["broken_links"]:
            writer.writerow([b["site"], b["url"], b["http_status"]])
        writer.writerow([])

    # DNS
    if report["dns_records"]:
        writer.writerow(["DNS / EMAIL AUTHENTICATION"])
        writer.writerow(["Site", "SPF", "DKIM", "DMARC"])
        for d in report["dns_records"]:
            if "spf" in d:
                writer.writerow([d["site"], d.get("spf", ""),
                                 d.get("dkim", ""), d.get("dmarc", "")])
        writer.writerow([])

    # PageSpeed
    if report["pagespeed"]:
        writer.writerow(["PAGESPEED SCORES"])
        writer.writerow(["Site", "Score", "Strategy", "FCP", "LCP", "CLS"])
        for p in report["pagespeed"]:
            writer.writerow([p["site"], p["score"], p["strategy"],
                             p["fcp"], p["lcp"], p["cls"]])
        writer.writerow([])

    # SSL
    if report["ssl_certificates"]:
        writer.writerow(["SSL CERTIFICATES"])
        writer.writerow(["Site", "Days Remaining", "Expires", "Issuer"])
        for s in report["ssl_certificates"]:
            writer.writerow([s["site"], s["days_remaining"],
                             s["expires"], s["issuer"]])
        writer.writerow([])

    # Uptime
    if report["uptime_monitors"]:
        writer.writerow(["UPTIME MONITORS"])
        writer.writerow(["Name", "URL", "Status"])
        for u in report["uptime_monitors"]:
            writer.writerow([u["name"], u["url"], u["status"]])
        writer.writerow([])

    # Site Health
    if report["site_health"]:
        writer.writerow(["SITE HEALTH"])
        writer.writerow(["Site", "HTTP Status", "Response Time (ms)", "Final URL"])
        for h in report["site_health"]:
            writer.writerow([h["site"], h["status_code"],
                             h["response_time_ms"], h["final_url"]])

    # Email
    if report["email_stats"]:
        writer.writerow(["EMAIL DELIVERY"])
        writer.writerow(["Site", "Task", "Delivered", "Opens", "Bounces"])
        for e in report["email_stats"]:
            writer.writerow([e.get("site", ""), e.get("task", ""),
                             e.get("delivered", ""), e.get("opens", ""),
                             e.get("bounces", "")])

    csv_content = output.getvalue()
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                f"attachment; filename=checklist_report_{day}_{batch_id[:8]}.csv"
        },
    )


@integrations_bp.route("/results/<batch_id>/report/json")
@login_required
def download_report_json(batch_id):
    """Download batch results as a JSON report."""
    runs = (
        TaskRun.query
        .filter_by(user_id=current_user.id, batch_id=batch_id)
        .order_by(TaskRun.run_at.asc())
        .all()
    )
    if not runs:
        flash("No results found.", "error")
        return redirect(url_for("dashboard.index"))

    ok = sum(1 for r in runs if r.status == "success")
    fail = sum(1 for r in runs if r.status in ("failure", "error"))
    warn = sum(1 for r in runs if r.status == "warning")
    skip = sum(1 for r in runs if r.status == "skipped")
    total_ms = sum(r.duration_ms or 0 for r in runs)
    day = runs[0].day

    site_groups = {}
    for r in runs:
        key = r.site.name if r.site else "No Site"
        site_groups.setdefault(key, []).append(r)

    report = _build_report_data(runs, day, batch_id, ok, fail, warn, skip,
                                total_ms, site_groups)

    return Response(
        json.dumps(report, indent=2),
        mimetype="application/json",
        headers={
            "Content-Disposition":
                f"attachment; filename=checklist_report_{day}_{batch_id[:8]}.json"
        },
    )


# ── Helpers ─────────────────────────────────────────────────────────

def _log(action, category, details):
    db.session.add(
        ActivityLog(
            user_id=current_user.id,
            action=action,
            category=category,
            details=details,
            ip_address=request.remote_addr,
        )
    )


def _save_run(day, task_name, integration_type, site, result, batch_id=None):
    """Create a TaskRun record and activity log entry."""
    run = TaskRun(
        user_id=current_user.id,
        batch_id=batch_id,
        day=day,
        task_name=task_name,
        integration_type=integration_type,
        site_id=site.id if site else None,
        status=result["status"],
        result_summary=result.get("summary", ""),
        result_data=json.dumps(result.get("data", {})),
        duration_ms=result.get("duration_ms", 0),
    )
    db.session.add(run)
    site_label = site.name if site else "no site"
    _log("task_run", "execution",
         f"[{day}] {task_name} on {site_label} → {result['status']}: {result.get('summary','')}")


def _flash_css(status):
    if status == "success":
        return "success"
    if status == "warning":
        return "warning"
    return "error"


def _execute_task(integration_type, task_name, site=None):
    """Dispatch to the appropriate API client and return result dict."""
    from app.clients import dispatch

    start = time.time()
    try:
        # Gather relevant API configs for current user
        configs = (
            IntegrationConfig.query
            .filter_by(user_id=current_user.id, is_active=True)
            .all()
        )
        result = dispatch(integration_type, task_name, site=site, configs=configs)
    except Exception as exc:
        result = {
            "status": "failure",
            "summary": f"Error: {str(exc)[:200]}",
            "data": {"error": str(exc)},
        }
    result["duration_ms"] = int((time.time() - start) * 1000)
    return result


def _build_report_data(runs, day, batch_id, ok, fail, warn, skip, total_ms,
                       site_groups):
    """Build a structured report dict from batch run data."""
    # Collect detailed breakdowns
    plugins_list = []
    themes_list = []
    broken_links = []
    dns_results = []
    email_stats = []
    pagespeed_scores = []
    ssl_certs = []
    uptime_monitors = []
    site_health = []

    for r in runs:
        try:
            d = json.loads(r.result_data) if r.result_data else {}
        except (json.JSONDecodeError, TypeError):
            d = {}

        site_name = r.site.name if r.site else "N/A"
        itype = r.integration_type or "manual"

        # WordPress plugins
        if d.get("plugins"):
            for p in d["plugins"]:
                plugins_list.append({
                    "site": site_name,
                    "name": p.get("name", "?"),
                    "version": p.get("version", "?"),
                    "status": p.get("status", "?"),
                    "update_available": p.get("update") or "No",
                })
        # WordPress themes
        if d.get("themes"):
            for t in d["themes"]:
                themes_list.append({
                    "site": site_name,
                    "name": t.get("name", "?"),
                    "status": t.get("status", "?"),
                })
        # Broken links
        if d.get("broken"):
            for link in d["broken"]:
                broken_links.append({
                    "site": site_name,
                    "url": link.get("url", "?"),
                    "http_status": link.get("status", "?"),
                })
        # DNS
        if d.get("spf") or d.get("dkim") or d.get("dmarc"):
            dns_results.append({
                "site": site_name,
                "spf": d.get("spf", {}).get("status", "?"),
                "dkim": d.get("dkim", {}).get("status", "?"),
                "dmarc": d.get("dmarc", {}).get("status", "?"),
                "spf_summary": d.get("spf", {}).get("summary", ""),
                "dkim_summary": d.get("dkim", {}).get("summary", ""),
                "dmarc_summary": d.get("dmarc", {}).get("summary", ""),
            })
        if d.get("records") and itype == "dns_check":
            dns_results.append({
                "site": site_name,
                "records": d.get("records", []),
                "task": r.task_name,
            })
        # Email
        if itype == "email_service" and d:
            entry = {"site": site_name, "task": r.task_name}
            for k in ("delivered", "opens", "bounces", "clicks",
                      "count", "to"):
                if d.get(k) is not None:
                    entry[k] = d[k]
            if d.get("recent"):
                entry["recent_count"] = len(d["recent"])
            if len(entry) > 2:
                email_stats.append(entry)
        # PageSpeed
        if d.get("score") is not None:
            pagespeed_scores.append({
                "site": site_name,
                "score": d["score"],
                "strategy": d.get("strategy", "mobile"),
                "fcp": d.get("fcp", "N/A"),
                "lcp": d.get("lcp", "N/A"),
                "cls": d.get("cls", "N/A"),
            })
        # SSL
        if d.get("days_remaining") is not None:
            ssl_certs.append({
                "site": site_name,
                "days_remaining": d["days_remaining"],
                "expires": d.get("expires", "?"),
                "issuer": str(d.get("issuer", "?")),
            })
        # Uptime monitors
        if d.get("monitors"):
            for m in d["monitors"]:
                uptime_monitors.append({
                    "name": m.get("name", "?"),
                    "url": m.get("url", ""),
                    "status": "Up" if m.get("status") == 2 else "Down",
                })
        # Site health
        if itype == "website_health" and d.get("status_code"):
            site_health.append({
                "site": site_name,
                "status_code": d["status_code"],
                "response_time_ms": d.get("response_time_ms", 0),
                "final_url": d.get("final_url", ""),
            })

    return {
        "batch_id": batch_id,
        "day": day,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "total": len(runs),
            "passed": ok,
            "failed": fail,
            "warnings": warn,
            "skipped": skip,
            "duration_ms": total_ms,
            "pass_rate": round(ok / len(runs) * 100, 1) if runs else 0,
        },
        "sites": {
            name: {
                "total": len(sr),
                "passed": sum(1 for r in sr if r.status == "success"),
                "failed": sum(1 for r in sr if r.status in ("failure", "error")),
                "warnings": sum(1 for r in sr if r.status == "warning"),
                "skipped": sum(1 for r in sr if r.status == "skipped"),
            }
            for name, sr in site_groups.items()
        },
        "all_checks": [
            {
                "task": r.task_name,
                "site": r.site.name if r.site else "N/A",
                "type": r.integration_type or "manual",
                "status": r.status,
                "summary": r.result_summary or "",
                "duration_ms": r.duration_ms or 0,
                "time": r.run_at.strftime("%H:%M:%S") if r.run_at else "",
            }
            for r in runs
        ],
        "plugins": plugins_list,
        "themes": themes_list,
        "broken_links": broken_links,
        "dns_records": dns_results,
        "email_stats": email_stats,
        "pagespeed": pagespeed_scores,
        "ssl_certificates": ssl_certs,
        "uptime_monitors": uptime_monitors,
        "site_health": site_health,
    }


def _generate_recommendations(runs, report):
    """Generate daily recommendations based on run results."""
    recs = []

    # Failed checks
    failed = [r for r in runs if r.status in ("failure", "error")]
    if failed:
        recs.append({
            "priority": "high",
            "icon": "&#128308;",
            "title": f"{len(failed)} check{'s' if len(failed) != 1 else ''} failed",
            "description": "Investigate and resolve failed checks immediately. "
                           "Review error details in the failed checks section below.",
            "tasks": [r.task_name for r in failed[:5]],
        })

    # Skipped checks
    skipped = [r for r in runs if r.status == "skipped"]
    if skipped:
        recs.append({
            "priority": "medium",
            "icon": "&#9898;",
            "title": f"{len(skipped)} check{'s' if len(skipped) != 1 else ''} skipped",
            "description": "These checks were skipped because integrations are not configured. "
                           "Set up the required integrations to enable automated monitoring.",
            "tasks": list({r.task_name for r in skipped})[:5],
        })

    # SSL certificates expiring soon
    if report.get("ssl_certificates"):
        expiring = [s for s in report["ssl_certificates"] if s.get("days_remaining", 999) < 30]
        if expiring:
            recs.append({
                "priority": "high",
                "icon": "&#128274;",
                "title": f"{len(expiring)} SSL certificate{'s' if len(expiring) != 1 else ''} expiring soon",
                "description": "Renew SSL certificates before expiry to avoid site downtime and security warnings.",
                "tasks": [f"{s['site']} — {s['days_remaining']} days left" for s in expiring],
            })

    # Broken links
    if report.get("broken_links"):
        bl = report["broken_links"]
        recs.append({
            "priority": "medium",
            "icon": "&#128279;",
            "title": f"{len(bl)} broken link{'s' if len(bl) != 1 else ''} found",
            "description": "Fix or remove broken links to improve SEO rankings and user experience.",
            "tasks": [f"{b['url'][:60]} (HTTP {b['http_status']})" for b in bl[:5]],
        })

    # Plugin updates
    if report.get("plugins"):
        needs_update = [p for p in report["plugins"]
                        if p.get("update_available") and p["update_available"] != "No"]
        if needs_update:
            recs.append({
                "priority": "medium",
                "icon": "&#128268;",
                "title": f"{len(needs_update)} plugin{'s' if len(needs_update) != 1 else ''} need updating",
                "description": "Update plugins to patch security vulnerabilities and get new features.",
                "tasks": [f"{p['name']} on {p['site']}" for p in needs_update[:5]],
            })

    # Slow sites
    if report.get("site_health"):
        slow = [s for s in report["site_health"] if s.get("response_time_ms", 0) > 3000]
        if slow:
            recs.append({
                "priority": "medium",
                "icon": "&#9888;",
                "title": f"{len(slow)} site{'s' if len(slow) != 1 else ''} responding slowly",
                "description": "Sites with response times over 3 seconds may lose visitors. "
                               "Consider optimizing server performance or enabling caching.",
                "tasks": [f"{s['site']} — {s['response_time_ms']}ms" for s in slow],
            })

    # Low PageSpeed scores
    if report.get("pagespeed"):
        low_scores = [p for p in report["pagespeed"] if p.get("score", 100) < 50]
        if low_scores:
            recs.append({
                "priority": "medium",
                "icon": "&#9889;",
                "title": f"{len(low_scores)} site{'s' if len(low_scores) != 1 else ''} with low PageSpeed",
                "description": "Scores below 50 significantly impact user experience and SEO. "
                               "Optimize images, reduce JavaScript, and enable compression.",
                "tasks": [f"{p['site']} — score {p['score']}/100" for p in low_scores],
            })

    # Uptime monitors down
    if report.get("uptime_monitors"):
        down = [m for m in report["uptime_monitors"] if m.get("status") == "Down"]
        if down:
            recs.append({
                "priority": "high",
                "icon": "&#128308;",
                "title": f"{len(down)} monitor{'s' if len(down) != 1 else ''} reporting DOWN",
                "description": "These sites are currently unreachable. Investigate immediately.",
                "tasks": [m["name"] for m in down],
            })

    # DNS issues
    if report.get("dns_records"):
        dns_issues = []
        for d in report["dns_records"]:
            for field in ("spf", "dkim", "dmarc"):
                if d.get(field) and d[field] not in ("success", "?"):
                    dns_issues.append(f"{d.get('site', '?')}: {field.upper()} — {d[field]}")
        if dns_issues:
            recs.append({
                "priority": "medium",
                "icon": "&#128225;",
                "title": "DNS email authentication issues detected",
                "description": "Missing or misconfigured SPF, DKIM, or DMARC records can cause "
                               "emails to land in spam folders.",
                "tasks": dns_issues[:5],
            })

    # Email bounce rate
    if report.get("email_stats"):
        for e in report["email_stats"]:
            if e.get("bounces", 0) > 0 and e.get("delivered", 1) > 0:
                bounce_rate = e["bounces"] / (e["delivered"] + e["bounces"]) * 100
                if bounce_rate > 5:
                    recs.append({
                        "priority": "high",
                        "icon": "&#128231;",
                        "title": f"High email bounce rate ({bounce_rate:.1f}%)",
                        "description": "A bounce rate above 5% can damage sender reputation. "
                                       "Clean your email list and verify email addresses.",
                        "tasks": [f"{e.get('task', 'Email check')} — {e['bounces']} bounces"],
                    })

    # All clear!
    if not recs:
        recs.append({
            "priority": "low",
            "icon": "&#9989;",
            "title": "All checks passed — no issues detected",
            "description": "Everything looks great! Continue monitoring regularly to "
                           "catch issues early.",
            "tasks": [],
        })

    return recs


def _build_analytics(runs, day):
    """Build analytics data for the run results page."""
    total = len(runs)
    ok = sum(1 for r in runs if r.status == "success")
    fail = sum(1 for r in runs if r.status in ("failure", "error"))
    warn = sum(1 for r in runs if r.status == "warning")
    skip = sum(1 for r in runs if r.status == "skipped")

    # Status distribution
    status_dist = [
        {"label": "Passed", "count": ok, "color": "#4ade80"},
        {"label": "Failed", "count": fail, "color": "#f87171"},
        {"label": "Warnings", "count": warn, "color": "#facc15"},
        {"label": "Skipped", "count": skip, "color": "#94a3b8"},
    ]

    # Integration type distribution
    type_counts = {}
    for r in runs:
        itype = r.integration_type or "manual"
        type_counts[itype] = type_counts.get(itype, 0) + 1
    type_dist = [
        {"type": k, "label": INTEGRATION_LABELS.get(k, {}).get("label", k),
         "count": v, "icon": INTEGRATION_LABELS.get(k, {}).get("icon", "")}
        for k, v in sorted(type_counts.items(), key=lambda x: -x[1])
    ]

    # Duration stats
    durations = [r.duration_ms or 0 for r in runs]
    avg_duration = int(sum(durations) / len(durations)) if durations else 0
    max_duration = max(durations) if durations else 0
    min_duration = min(durations) if durations else 0
    slowest_task = ""
    fastest_task = ""
    for r in runs:
        if (r.duration_ms or 0) == max_duration:
            slowest_task = r.task_name
        if (r.duration_ms or 0) == min_duration:
            fastest_task = r.task_name

    # Per-site pass rate
    site_pass_rates = []
    site_map = {}
    for r in runs:
        site_key = r.site.name if r.site else "No Site"
        site_map.setdefault(site_key, {"ok": 0, "total": 0})
        site_map[site_key]["total"] += 1
        if r.status == "success":
            site_map[site_key]["ok"] += 1
    for name, data in site_map.items():
        pct = round(data["ok"] / data["total"] * 100, 1) if data["total"] else 0
        site_pass_rates.append({"site": name, "rate": pct, "ok": data["ok"], "total": data["total"]})
    site_pass_rates.sort(key=lambda x: -x["rate"])

    # Historical comparison (last 10 same-day batches)
    history = (
        TaskRun.query
        .filter_by(user_id=current_user.id, day=day)
        .filter(TaskRun.batch_id.isnot(None))
        .order_by(TaskRun.run_at.desc())
        .limit(500)
        .all()
    )
    batch_history = {}
    for r in history:
        if r.batch_id not in batch_history:
            batch_history[r.batch_id] = {"ok": 0, "total": 0, "date": r.run_at}
        batch_history[r.batch_id]["total"] += 1
        if r.status == "success":
            batch_history[r.batch_id]["ok"] += 1

    trend = []
    for bid, data in sorted(batch_history.items(),
                            key=lambda x: x[1]["date"] or datetime(2000, 1, 1)):
        pct = round(data["ok"] / data["total"] * 100, 1) if data["total"] else 0
        trend.append({
            "batch_id": bid[:8],
            "date": data["date"].strftime("%b %d %H:%M") if data["date"] else "?",
            "pass_rate": pct,
            "total": data["total"],
        })
    trend = trend[-10:]  # Keep last 10

    return {
        "status_distribution": status_dist,
        "type_distribution": type_dist,
        "duration": {
            "avg": avg_duration,
            "max": max_duration,
            "min": min_duration,
            "slowest_task": slowest_task,
            "fastest_task": fastest_task,
        },
        "site_pass_rates": site_pass_rates,
        "trend": trend,
        "pass_rate": round(ok / total * 100, 1) if total else 0,
    }
