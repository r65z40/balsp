"""Factory Flask de l'application balsp."""
from __future__ import annotations

import os

import click
from flask import Flask

from config import Config
from extensions import csrf, db, login_manager
from models import EmailTemplate, User
from utils.defaults import DEFAULT_EMAIL_BODY, DEFAULT_EMAIL_SUBJECT


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_class)

    # S'assurer que les dossiers nécessaires existent
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.dirname(app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")), exist_ok=True)

    # Extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # Blueprints
    from routes.auth import bp as auth_bp
    from routes.dashboard import bp as dashboard_bp
    from routes.scan import bp as scan_bp
    from routes.settings import bp as settings_bp
    from routes.sponsors import bp as sponsors_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(sponsors_bp)
    app.register_blueprint(scan_bp)
    app.register_blueprint(settings_bp)

    # CLI
    @app.cli.command("init-db")
    def init_db():
        """Crée les tables, le compte admin et le modèle d'email par défaut."""
        db.create_all()

        username = app.config["ADMIN_USERNAME"]
        password = app.config["ADMIN_PASSWORD"]
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            click.echo(f"Compte administrateur créé : {username}")
        else:
            click.echo(f"Compte administrateur déjà présent : {username}")

        if not EmailTemplate.query.first():
            tpl = EmailTemplate(
                subject=DEFAULT_EMAIL_SUBJECT, body_html=DEFAULT_EMAIL_BODY
            )
            db.session.add(tpl)
            click.echo("Modèle d'email par défaut initialisé.")

        db.session.commit()
        click.echo("Base de données initialisée.")

    @app.cli.command("migrate-db")
    def migrate_db():
        """Ajoute les colonnes/tables manquantes sur une base existante."""
        from sqlalchemy import inspect, text

        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        # Table guests (nouvelle)
        if "guests" not in existing_tables:
            from models import Guest

            Guest.__table__.create(db.engine)
            click.echo("Table 'guests' créée.")
        else:
            click.echo("Table 'guests' déjà présente.")

        # Colonne bonus_invitations sur sponsors
        if "sponsors" in existing_tables:
            cols = {c["name"] for c in inspector.get_columns("sponsors")}
            if "bonus_invitations" not in cols:
                db.session.execute(
                    text(
                        "ALTER TABLE sponsors "
                        "ADD COLUMN bonus_invitations INTEGER NOT NULL DEFAULT 0"
                    )
                )
                db.session.commit()
                click.echo("Colonne 'bonus_invitations' ajoutée à sponsors.")
            else:
                click.echo("Colonne 'bonus_invitations' déjà présente.")

        click.echo("Migration terminée.")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=bool(int(os.environ.get("FLASK_DEBUG", "0"))))
