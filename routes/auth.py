"""Authentification."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from extensions import log_action, db
from forms import LoginForm
from models import User

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            log_action("login", f"Connexion de « {user.username} ».")
            db.session.commit()
            next_url = request.args.get("next") or url_for("dashboard.index")
            return redirect(next_url)
        flash("Identifiants invalides.", "danger")
    return render_template("login.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    log_action("logout", "Déconnexion.")
    db.session.commit()
    logout_user()
    flash("Déconnexion réussie.", "success")
    return redirect(url_for("auth.login"))
