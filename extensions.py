"""Instances Flask partagées (évite les imports circulaires)."""
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = "auth.login"
login_manager.login_message = "Connectez-vous pour accéder à la billetterie du Bal des Pompiers."
login_manager.login_message_category = "warning"
