"""Tests for the Settings blueprint and CustomTask model."""

import pytest

from app import create_app, db
from app.models import CustomTask, User


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
def user(app):
    with app.app_context():
        u = User(name="Test User", email="test@example.com")
        u.set_password("password123")
        db.session.add(u)
        db.session.commit()
        return u.id


def login(client, email="test@example.com", password="password123"):
    return client.post("/login", data={
        "email": email, "password": password,
    }, follow_redirects=True)


# ── CustomTask model tests ──

def test_custom_task_creation(app, user):
    with app.app_context():
        task = CustomTask(
            user_id=user,
            day="Monday",
            task_name="Test custom task",
            integration_type="manual",
        )
        db.session.add(task)
        db.session.commit()
        assert task.id is not None
        assert task.is_active is True


def test_custom_task_belongs_to_user(app, user):
    with app.app_context():
        task = CustomTask(
            user_id=user,
            day="Tuesday",
            task_name="Another task",
        )
        db.session.add(task)
        db.session.commit()

        found = CustomTask.query.filter_by(user_id=user, day="Tuesday").first()
        assert found is not None
        assert found.task_name == "Another task"


# ── Settings routes tests ──

def test_settings_page_requires_login(client):
    resp = client.get("/settings/", follow_redirects=False)
    assert resp.status_code in (302, 308)


def test_settings_page_loads(client, user):
    login(client)
    resp = client.get("/settings/")
    assert resp.status_code == 200
    assert b"Settings" in resp.data


def test_add_custom_task(client, user):
    login(client)
    resp = client.post("/settings/add-task", data={
        "day": "Monday",
        "task_name": "My custom Monday task",
        "integration_type": "manual",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"My custom Monday task" in resp.data


def test_add_task_invalid_day(client, user):
    login(client)
    resp = client.post("/settings/add-task", data={
        "day": "Sunday",
        "task_name": "Invalid day task",
        "integration_type": "manual",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Invalid day" in resp.data


def test_add_task_too_short(client, user):
    login(client)
    resp = client.post("/settings/add-task", data={
        "day": "Monday",
        "task_name": "ab",
        "integration_type": "manual",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"at least 3 characters" in resp.data


def test_add_duplicate_task(client, user):
    login(client)
    client.post("/settings/add-task", data={
        "day": "Friday",
        "task_name": "Duplicate check",
        "integration_type": "manual",
    }, follow_redirects=True)
    resp = client.post("/settings/add-task", data={
        "day": "Friday",
        "task_name": "Duplicate check",
        "integration_type": "manual",
    }, follow_redirects=True)
    assert b"already exists" in resp.data


def test_delete_custom_task(app, client, user):
    login(client)
    client.post("/settings/add-task", data={
        "day": "Wednesday",
        "task_name": "To be deleted",
        "integration_type": "manual",
    }, follow_redirects=True)

    with app.app_context():
        task = CustomTask.query.filter_by(
            user_id=user, task_name="To be deleted"
        ).first()
        task_id = task.id

    resp = client.post(f"/settings/delete-task/{task_id}", follow_redirects=True)
    assert resp.status_code == 200
    assert b"removed" in resp.data


# ── Merged checklist tests ──

def test_merged_checklist_includes_custom_tasks(app, user):
    with app.app_context():
        from app.dashboard import get_merged_checklist
        task = CustomTask(
            user_id=user,
            day="Monday",
            task_name="Custom Monday Task",
            integration_type="website_health",
        )
        db.session.add(task)
        db.session.commit()

        merged = get_merged_checklist(user)
        assert "Custom Monday Task" in merged["Monday"]["tasks"]


def test_merged_task_integrations_includes_custom(app, user):
    with app.app_context():
        from app.dashboard import get_merged_task_integrations
        task = CustomTask(
            user_id=user,
            day="Friday",
            task_name="Custom Friday Check",
            integration_type="ssl_check",
        )
        db.session.add(task)
        db.session.commit()

        merged = get_merged_task_integrations(user)
        assert merged["Friday"]["Custom Friday Check"] == "ssl_check"


# ── Recommendations/analytics helper tests ──

def test_recommendations_all_clear(app, user):
    """When no runs have issues, recommendations return an 'all clear' message."""
    with app.app_context():
        from app.integrations import _generate_recommendations
        recs = _generate_recommendations([], {})
        assert len(recs) == 1
        assert recs[0]["priority"] == "low"


def test_analytics_empty_runs(app, client, user):
    """Analytics handles empty runs gracefully."""
    login(client)
    # Test via a request context so current_user is available
    with app.test_request_context():
        from flask_login import login_user
        from app.models import User as U
        u = U.query.get(user)
        login_user(u)
        from app.integrations import _build_analytics
        analytics = _build_analytics([], "Monday")
        assert analytics["pass_rate"] == 0
        assert analytics["duration"]["avg"] == 0
