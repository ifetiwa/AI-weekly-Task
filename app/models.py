"""Database models."""

import json
from datetime import datetime

from cryptography.fernet import Fernet
from flask import current_app
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login_manager


# ── User ────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sites = db.relationship("Site", backref="owner", lazy="dynamic",
                            cascade="all, delete-orphan")
    integrations = db.relationship("IntegrationConfig", backref="owner",
                                   lazy="dynamic", cascade="all, delete-orphan")
    task_runs = db.relationship("TaskRun", backref="owner", lazy="dynamic",
                                cascade="all, delete-orphan")
    activity_logs = db.relationship("ActivityLog", backref="owner", lazy="dynamic",
                                    cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def _load_user(user_id):
    return db.session.get(User, int(user_id))


# ── Site (WordPress / generic website) ──────────────────────────────

class Site(db.Model):
    __tablename__ = "sites"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    site_type = db.Column(db.String(50), default="wordpress")
    credentials_encrypted = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_checked = db.Column(db.DateTime)
    last_status = db.Column(db.String(20))

    task_runs = db.relationship("TaskRun", backref="site", lazy="dynamic")

    def set_credentials(self, creds: dict):
        f = Fernet(current_app.config["ENCRYPTION_KEY"])
        self.credentials_encrypted = f.encrypt(
            json.dumps(creds).encode()
        ).decode()

    def get_credentials(self) -> dict:
        if not self.credentials_encrypted:
            return {}
        f = Fernet(current_app.config["ENCRYPTION_KEY"])
        return json.loads(f.decrypt(self.credentials_encrypted.encode()).decode())


# ── Integration Config (third-party API keys) ──────────────────────

INTEGRATION_TYPES = {
    "sendgrid": {
        "label": "SendGrid",
        "icon": "📧",
        "fields": [
            {"name": "api_key", "label": "API Key", "type": "password"},
            {"name": "from_email", "label": "Default From Email", "type": "email"},
        ],
        "setup_url": "https://app.sendgrid.com/settings/api_keys",
        "docs_url": "https://docs.sendgrid.com/ui/account-and-settings/api-keys",
    },
    "mailgun": {
        "label": "Mailgun",
        "icon": "📬",
        "fields": [
            {"name": "api_key", "label": "API Key", "type": "password"},
            {"name": "domain", "label": "Domain", "type": "text"},
        ],
        "setup_url": "https://app.mailgun.com/settings/api_security",
        "docs_url": "https://documentation.mailgun.com/docs/mailgun/api-reference/openapi-final/tag/Domains/",
    },
    "google_search_console": {
        "label": "Google Search Console",
        "icon": "🔍",
        "fields": [
            {"name": "api_key", "label": "API / Service-Account Key (JSON)", "type": "textarea"},
            {"name": "site_url", "label": "Site URL", "type": "url"},
        ],
        "setup_url": "https://search.google.com/search-console",
        "docs_url": "https://console.cloud.google.com/apis/library/searchconsole.googleapis.com",
    },
    "google_analytics": {
        "label": "Google Analytics (GA4)",
        "icon": "📊",
        "fields": [
            {"name": "api_key", "label": "API / Service-Account Key (JSON)", "type": "textarea"},
            {"name": "property_id", "label": "Property ID", "type": "text"},
        ],
        "setup_url": "https://analytics.google.com/",
        "docs_url": "https://console.cloud.google.com/apis/library/analyticsdata.googleapis.com",
    },
    "pagespeed": {
        "label": "PageSpeed Insights",
        "icon": "⚡",
        "fields": [
            {"name": "api_key", "label": "API Key", "type": "password"},
        ],
        "setup_url": "https://console.cloud.google.com/apis/library/pagespeedonline.googleapis.com",
        "docs_url": "https://developers.google.com/speed/docs/insights/v5/get-started",
    },
    "uptimerobot": {
        "label": "UptimeRobot",
        "icon": "🔔",
        "fields": [
            {"name": "api_key", "label": "API Key", "type": "password"},
        ],
        "setup_url": "https://dashboard.uptimerobot.com/integrations",
        "docs_url": "https://uptimerobot.com/api/",
    },
}


class IntegrationConfig(db.Model):
    __tablename__ = "integration_configs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    service_type = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(200))
    config_encrypted = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_config(self, config_dict: dict):
        f = Fernet(current_app.config["ENCRYPTION_KEY"])
        self.config_encrypted = f.encrypt(
            json.dumps(config_dict).encode()
        ).decode()

    def get_config(self) -> dict:
        if not self.config_encrypted:
            return {}
        f = Fernet(current_app.config["ENCRYPTION_KEY"])
        return json.loads(f.decrypt(self.config_encrypted.encode()).decode())


# ── Task Run (execution log per task) ──────────────────────────────

class TaskRun(db.Model):
    __tablename__ = "task_runs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    batch_id = db.Column(db.String(36), index=True)  # groups runs from a single execution
    day = db.Column(db.String(20), nullable=False)
    task_name = db.Column(db.String(300), nullable=False)
    integration_type = db.Column(db.String(50))
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id"))
    status = db.Column(db.String(20), nullable=False)  # success / failure / warning / skipped
    result_summary = db.Column(db.String(500))
    result_data = db.Column(db.Text)  # JSON
    duration_ms = db.Column(db.Integer)
    run_at = db.Column(db.DateTime, default=datetime.utcnow)


# ── Activity Log ───────────────────────────────────────────────────

class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ── Custom Tasks (user-defined per day) ────────────────────────────

class CustomTask(db.Model):
    __tablename__ = "custom_tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    task_name = db.Column(db.String(300), nullable=False)
    integration_type = db.Column(db.String(50), default="manual")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owner_rel = db.relationship("User", backref=db.backref("custom_tasks", lazy="dynamic"))
