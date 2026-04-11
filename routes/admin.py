"""Routes d'administration : gestion des utilisateurs + journal d'audit."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from extensions import admin_required, db, log_action
from forms import UserForm
from models import AuditLog, Role, User

bp = Blueprint("admin", __name__, url_prefix="/admin")


# --- Gestion des utilisateurs ---


@bp.route("/users")
@login_required
@admin_required
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users)


@bp.route("/users/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_user():
    form = UserForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data.strip()).first():
            flash("Ce nom d'utilisateur existe déjà.", "danger")
            return render_template("admin/user_form.html", form=form, user=None)

        user = User(
            username=form.username.data.strip(),
            role=Role[form.role.data],
        )
        if not form.password.data:
            flash("Le mot de passe est obligatoire pour un nouvel utilisateur.", "warning")
            return render_template("admin/user_form.html", form=form, user=None)
        user.set_password(form.password.data)
        db.session.add(user)
        log_action("create_user", f"Utilisateur « {user.username} » créé (rôle : {user.role.label}).", "user")
        db.session.commit()
        flash(f"Utilisateur « {user.username} » créé.", "success")
        return redirect(url_for("admin.list_users"))

    return render_template("admin/user_form.html", form=form, user=None)


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id: int):
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    if request.method == "GET":
        form.role.data = user.role.name

    if form.validate_on_submit():
        existing = User.query.filter_by(username=form.username.data.strip()).first()
        if existing and existing.id != user.id:
            flash("Ce nom d'utilisateur est déjà pris.", "danger")
            return render_template("admin/user_form.html", form=form, user=user)

        user.username = form.username.data.strip()
        user.role = Role[form.role.data]
        if form.password.data:
            user.set_password(form.password.data)
        log_action("edit_user", f"Utilisateur « {user.username} » modifié.", "user", user.id)
        db.session.commit()
        flash(f"Utilisateur « {user.username} » mis à jour.", "success")
        return redirect(url_for("admin.list_users"))

    return render_template("admin/user_form.html", form=form, user=user)


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id: int):
    from flask_login import current_user

    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "danger")
        return redirect(url_for("admin.list_users"))

    username = user.username
    log_action("delete_user", f"Utilisateur « {username} » supprimé.", "user", user.id)
    db.session.delete(user)
    db.session.commit()
    flash(f"Utilisateur « {username} » supprimé.", "success")
    return redirect(url_for("admin.list_users"))


# --- Journal d'audit ---


@bp.route("/audit")
@login_required
@admin_required
def audit_log():
    page = request.args.get("page", 1, type=int)
    user_filter = request.args.get("user", "", type=str).strip()
    action_filter = request.args.get("action", "", type=str).strip()

    query = AuditLog.query.order_by(AuditLog.created_at.desc())
    if user_filter:
        query = query.filter(AuditLog.username.ilike(f"%{user_filter}%"))
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)

    pagination = query.paginate(page=page, per_page=50, error_out=False)

    # Distinct action types for the filter dropdown
    actions = [
        r[0] for r in db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()
    ]

    return render_template(
        "admin/audit.html",
        logs=pagination.items,
        pagination=pagination,
        user_filter=user_filter,
        action_filter=action_filter,
        actions=actions,
    )
