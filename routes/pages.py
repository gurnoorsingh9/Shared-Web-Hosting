from flask import Blueprint, redirect, render_template, session

from routes.utils import current_user, log_action, log_manual

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def home():
    if "email" in session:
        return redirect("/dashboard")
    return render_template("login.html")


@pages_bp.route("/agreement")
@log_action("Agreement")
def legal():
    return render_template("agreement.html")


@pages_bp.route("/logout")
def logout():
    u = current_user()
    site = u.get("site_name") if u else None
    if site:
        log_manual(site, "Logout")  # log only if site exists
    session.clear()
    return render_template("login.html")


@pages_bp.route("/signup")
def signup_page():
    return render_template("signup.html")


@pages_bp.route("/dashboard")
def dash():
    if "email" not in session:
        return redirect("/")
    return render_template("dashboard.html")
