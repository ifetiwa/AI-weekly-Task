"""Tests for the Admin blueprint."""

import pytest

from app import create_app, db
from app.models import CustomTask, IntegrationConfig, Site, User


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SECRET_KEY"] = "test-secret"
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_user(app):
    with app.app_context():
        u = User(name="Admin", email="admin@test.com", is_admin=True)
        u.set_password("admin12345")
        db.session.add(u)
        db.session.commit()
        return u.id


@pytest.fixture
def regular_user(app):
    with app.app_context():
        u = User(name="Regular", email="regular@test.com")
        u.set_password("password123")
        db.session.add(u)
        db.session.commit()
        return u.id


def login(client, email, password):
    return client.post("/login", data={
        "email": email, "password": password,
    }, follow_redirects=True)


# ── Access control ──

def test_admin_dashboard_requires_login(client):
    resp = client.get("/admin/", follow_redirects=True)
    assert b"login" in resp.data.lower() or resp.status_code == 302


def test_admin_dashboard_forbidden_for_regular_user(client, regular_user):
    login(client, "regular@test.com", "password123")
    resp = client.get("/admin/")
    assert resp.status_code == 403


def test_admin_dashboard_accessible_for_admin(client, admin_user):
    login(client, "admin@test.com", "admin12345")
    resp = client.get("/admin/")
    assert resp.status_code == 200
    assert b"Admin Dashboard" in resp.data


# ── Users page ──

def test_admin_users_page(client, admin_user, regular_user):
    login(client, "admin@test.com", "admin12345")
    resp = client.get("/admin/users")
    assert resp.status_code == 200
    assert b"Regular" in resp.data
    assert b"Admin" in resp.data


def test_toggle_user_status(client, admin_user, regular_user):
    login(client, "admin@test.com", "admin12345")
    resp = client.post(f"/admin/users/{regular_user}/toggle", follow_redirects=True)
    assert resp.status_code == 200
    assert b"deactivated" in resp.data


def test_toggle_admin_role(client, admin_user, regular_user):
    login(client, "admin@test.com", "admin12345")
    resp = client.post(f"/admin/users/{regular_user}/toggle-admin", follow_redirects=True)
    assert resp.status_code == 200
    assert b"admin" in resp.data.lower()


def test_cannot_deactivate_self(client, admin_user):
    login(client, "admin@test.com", "admin12345")
    resp = client.post(f"/admin/users/{admin_user}/toggle", follow_redirects=True)
    assert b"cannot deactivate yourself" in resp.data.lower()


def test_cannot_change_own_admin(client, admin_user):
    login(client, "admin@test.com", "admin12345")
    resp = client.post(f"/admin/users/{admin_user}/toggle-admin", follow_redirects=True)
    assert b"cannot change your own" in resp.data.lower()


def test_delete_user(client, admin_user, regular_user):
    login(client, "admin@test.com", "admin12345")
    resp = client.post(f"/admin/users/{regular_user}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert b"deleted" in resp.data.lower()


def test_cannot_delete_self(client, admin_user):
    login(client, "admin@test.com", "admin12345")
    resp = client.post(f"/admin/users/{admin_user}/delete", follow_redirects=True)
    assert b"cannot delete yourself" in resp.data.lower()


# ── Tasks page ──

def test_admin_tasks_page(client, admin_user):
    login(client, "admin@test.com", "admin12345")
    resp = client.get("/admin/tasks")
    assert resp.status_code == 200
    assert b"Manage Tasks" in resp.data


def test_admin_add_task(client, admin_user, regular_user):
    login(client, "admin@test.com", "admin12345")
    resp = client.post("/admin/tasks/add", data={
        "user_id": regular_user,
        "day": "Monday",
        "task_name": "Admin-added task",
        "integration_type": "manual",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Admin-added task" in resp.data


def test_admin_add_task_invalid_day(client, admin_user, regular_user):
    login(client, "admin@test.com", "admin12345")
    resp = client.post("/admin/tasks/add", data={
        "user_id": regular_user,
        "day": "Sunday",
        "task_name": "Invalid day task",
        "integration_type": "manual",
    }, follow_redirects=True)
    assert b"Invalid day" in resp.data


def test_admin_delete_task(app, client, admin_user, regular_user):
    login(client, "admin@test.com", "admin12345")
    with app.app_context():
        task = CustomTask(
            user_id=regular_user, day="Tuesday",
            task_name="To delete", integration_type="manual",
        )
        db.session.add(task)
        db.session.commit()
        task_id = task.id

    resp = client.post(f"/admin/tasks/{task_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert b"removed" in resp.data.lower()


# ── Integrations page ──

def test_admin_integrations_page(client, admin_user):
    login(client, "admin@test.com", "admin12345")
    resp = client.get("/admin/integrations")
    assert resp.status_code == 200
    assert b"Manage Integrations" in resp.data


def test_admin_delete_integration(app, client, admin_user, regular_user):
    login(client, "admin@test.com", "admin12345")
    with app.app_context():
        cfg = IntegrationConfig(
            user_id=regular_user, service_type="sendgrid",
            label="Test SendGrid",
        )
        db.session.add(cfg)
        db.session.commit()
        cfg_id = cfg.id

    resp = client.post(f"/admin/integrations/{cfg_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert b"deleted" in resp.data.lower()


def test_admin_toggle_integration(app, client, admin_user, regular_user):
    login(client, "admin@test.com", "admin12345")
    with app.app_context():
        cfg = IntegrationConfig(
            user_id=regular_user, service_type="mailgun",
            label="Test Mailgun", is_active=True,
        )
        db.session.add(cfg)
        db.session.commit()
        cfg_id = cfg.id

    resp = client.post(f"/admin/integrations/{cfg_id}/toggle", follow_redirects=True)
    assert resp.status_code == 200
    assert b"deactivated" in resp.data.lower()


# ── Logs page ──

def test_admin_logs_page(client, admin_user):
    login(client, "admin@test.com", "admin12345")
    resp = client.get("/admin/logs")
    assert resp.status_code == 200
    assert b"Activity Logs" in resp.data


# ── is_admin flag ──

def test_is_admin_defaults_false(app):
    with app.app_context():
        u = User(name="New User", email="new@test.com")
        u.set_password("password123")
        db.session.add(u)
        db.session.commit()
        assert u.is_admin is False


def test_admin_nav_visible_for_admin(client, admin_user):
    login(client, "admin@test.com", "admin12345")
    resp = client.get("/")
    assert b"Admin" in resp.data


def test_admin_nav_hidden_for_regular(client, regular_user):
    login(client, "regular@test.com", "password123")
    resp = client.get("/")
    # The word "Admin" should not appear as a nav link
    assert b"/admin/" not in resp.data
