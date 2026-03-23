"""Authentication blueprint."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.models import ActivityLog, User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=bool(request.form.get("remember")))
            db.session.add(
                ActivityLog(
                    user_id=user.id, action="login", category="auth",
                    details="User logged in", ip_address=request.remote_addr,
                )
            )
            db.session.commit()
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard.index"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("All fields are required.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
        else:
            user = User(email=email, name=name)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            db.session.add(
                ActivityLog(
                    user_id=user.id, action="signup", category="auth",
                    details="Account created", ip_address=request.remote_addr,
                )
            )
            db.session.commit()
            login_user(user)
            flash("Account created successfully!", "success")
            return redirect(url_for("dashboard.index"))

    return render_template("signup.html")


@auth_bp.route("/logout")
@login_required
def logout():
    db.session.add(
        ActivityLog(
            user_id=current_user.id, action="logout", category="auth",
            details="User logged out", ip_address=request.remote_addr,
        )
    )
    db.session.commit()
    logout_user()
    return redirect(url_for("auth.login"))
