"""Instances Flask partagées (évite les imports circulaires)."""
from functools import wraps

from flask import abort
from flask_login import LoginManager, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = "auth.login"
login_manager.login_message = "Connectez-vous pour accéder à la billetterie du Bal des Pompiers."
login_manager.login_message_category = "warning"


def admin_required(f):
    """Décorateur : exige un utilisateur admin connecté."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)

    return decorated


def log_action(action: str, description: str, target_type: str | None = None, target_id: int | None = None):
    """Enregistre une action dans le journal d'audit."""
    from models import AuditLog

    entry = AuditLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        username=current_user.username if current_user.is_authenticated else "système",
        action=action,
        description=description,
        target_type=target_type,
        target_id=target_id,
    )
    db.session.add(entry)
