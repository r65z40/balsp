"""Factory Flask de l'application balsp."""
from __future__ import annotations

import os

import click
from flask import Flask

from config import Config
from extensions import csrf, db, login_manager
from models import EmailTemplate, Role, User
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
    from routes.admin import bp as admin_bp
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
    app.register_blueprint(admin_bp)

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template as rt

        return rt("403.html"), 403

    # CLI
    @app.cli.command("init-db")
    def init_db():
        """Crée les tables, le compte admin et le modèle d'email par défaut."""
        db.create_all()

        username = app.config["ADMIN_USERNAME"]
        password = app.config["ADMIN_PASSWORD"]
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, role=Role.ADMIN)
            user.set_password(password)
            db.session.add(user)
            click.echo(f"Compte administrateur créé : {username}")
        else:
            if user.role != Role.ADMIN:
                user.role = Role.ADMIN
                click.echo(f"Rôle admin attribué à : {username}")
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
        """Ajoute les colonnes/tables manquantes sur une base existante.

        Gère également la transition de l'ancien schéma (1 QR par sponsor,
        table ``guests``, table ``scan_logs``) vers le nouveau schéma basé
        sur la table ``invitations`` (1 QR par personne).
        """
        import uuid as _uuid
        from datetime import datetime

        from sqlalchemy import inspect, text

        from models import AuditLog, Invitation

        # Crée toutes les tables manquantes d'un coup
        db.create_all()

        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        # Table audit_logs
        if "audit_logs" not in existing_tables:
            AuditLog.__table__.create(db.engine)
            click.echo("Table 'audit_logs' créée.")
        else:
            click.echo("Table 'audit_logs' déjà présente.")

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

        # Colonne role sur users
        if "users" in existing_tables:
            cols = {c["name"] for c in inspector.get_columns("users")}
            if "role" not in cols:
                db.session.execute(
                    text("ALTER TABLE users ADD COLUMN role VARCHAR(10) DEFAULT 'USER'")
                )
                admin_username = app.config["ADMIN_USERNAME"]
                db.session.execute(
                    text("UPDATE users SET role = 'ADMIN' WHERE username = :u"),
                    {"u": admin_username},
                )
                db.session.commit()
                click.echo("Colonne 'role' ajoutée à users. Admin promu.")
            else:
                click.echo("Colonne 'role' déjà présente sur users.")

        # Neutraliser les anciennes colonnes NOT NULL de sponsors
        # (invitation_token, entries_count) sur un schéma pré-refactor.
        # SQLAlchemy ne les connaît plus : tout INSERT échouerait sur la
        # contrainte NOT NULL. On renomme l'ancienne table, on laisse
        # db.create_all() recréer la nouvelle structure et on recopie
        # les données (sauf les colonnes obsolètes) et les anciens
        # tokens/entries pour la migration des invitations ci-dessous.
        legacy_sponsor_rows: list[dict] = []
        if "sponsors" in existing_tables:
            sponsor_col_names = {
                c["name"] for c in inspector.get_columns("sponsors")
            }
            legacy_cols = {"invitation_token", "entries_count"}
            if legacy_cols & sponsor_col_names:
                click.echo(
                    "Nettoyage des colonnes obsolètes sur sponsors "
                    "(invitation_token, entries_count)..."
                )
                keep_cols = [
                    c for c in sponsor_col_names if c not in legacy_cols
                ]
                keep_list = ", ".join(keep_cols)

                # Sauvegarde l'ensemble des colonnes (y compris les legacy)
                # pour pouvoir migrer vers les Invitations après
                legacy_sponsor_rows = [
                    dict(r)
                    for r in db.session.execute(
                        text("SELECT * FROM sponsors")
                    ).mappings().all()
                ]

                db.session.execute(
                    text("ALTER TABLE sponsors RENAME TO sponsors_old")
                )
                db.session.commit()

                # Recrée la table sponsors propre (sans les colonnes legacy)
                db.create_all()

                # Recopie les données utiles
                if legacy_sponsor_rows:
                    db.session.execute(
                        text(
                            f"INSERT INTO sponsors ({keep_list}) "
                            f"SELECT {keep_list} FROM sponsors_old"
                        )
                    )
                db.session.execute(text("DROP TABLE sponsors_old"))
                db.session.commit()
                click.echo("Colonnes obsolètes supprimées.")
                # Met à jour l'inspector après DDL
                inspector = inspect(db.engine)

        # Table invitations (1 QR code par personne)
        existing_tables_after = inspect(db.engine).get_table_names()
        if "invitations" not in existing_tables_after:
            Invitation.__table__.create(db.engine)
            click.echo("Table 'invitations' créée.")

            # Migration des données de l'ancien schéma (1 sponsor = 1 QR)
            # vers le nouveau (N QR par sponsor).
            # On utilise legacy_sponsor_rows si la table sponsors a été
            # nettoyée (colonnes obsolètes déjà retirées), sinon on lit
            # directement depuis la table courante.
            if legacy_sponsor_rows:
                rows = legacy_sponsor_rows
                has_old_token = True
                has_old_entries = True
            elif "sponsors" in existing_tables:
                sponsor_cols = {c["name"] for c in inspector.get_columns("sponsors")}
                has_old_token = "invitation_token" in sponsor_cols
                has_old_entries = "entries_count" in sponsor_cols

                select_fields = ["id", "total_invitations"]
                if has_old_token:
                    select_fields.append("invitation_token")
                if has_old_entries:
                    select_fields.append("entries_count")

                rows = [
                    dict(r)
                    for r in db.session.execute(
                        text(f"SELECT {', '.join(select_fields)} FROM sponsors")
                    ).mappings().all()
                ]
            else:
                rows = []
                has_old_token = False
                has_old_entries = False

            if rows:
                # Récupérer les guests nommés de l'ancien schéma, si présents
                old_guests: dict[int, list[dict]] = {}
                if "guests" in existing_tables:
                    guest_rows = db.session.execute(
                        text(
                            "SELECT sponsor_id, name, checked_in, checked_in_at "
                            "FROM guests ORDER BY id"
                        )
                    ).mappings().all()
                    for g in guest_rows:
                        old_guests.setdefault(g["sponsor_id"], []).append(dict(g))

                created = 0
                for row in rows:
                    sponsor_id = row["id"]
                    total = int(row.get("total_invitations") or 0)
                    old_token = row.get("invitation_token") if has_old_token else None
                    old_entries = int(row.get("entries_count") or 0) if has_old_entries else 0
                    guests = old_guests.get(sponsor_id, [])

                    now = datetime.utcnow()
                    for n in range(1, total + 1):
                        token = (
                            old_token
                            if n == 1 and old_token
                            else str(_uuid.uuid4())
                        )
                        scanned_at = now if n <= old_entries else None
                        guest_name = None
                        if guests:
                            # On attribue les noms d'invités dans l'ordre
                            g = guests.pop(0)
                            guest_name = g.get("name")
                            # Si le guest était déjà coché mais que cette
                            # invitation n'est pas marquée comme scannée,
                            # on marque malgré tout pour préserver l'état.
                            if g.get("checked_in") and scanned_at is None:
                                scanned_at = now

                        db.session.add(
                            Invitation(
                                sponsor_id=sponsor_id,
                                number=n,
                                token=token,
                                guest_name=guest_name,
                                scanned_at=scanned_at,
                            )
                        )
                        created += 1

                db.session.commit()
                if created:
                    click.echo(
                        f"Migration : {created} invitations créées à partir "
                        f"de {len(rows)} sponsor(s)."
                    )
        else:
            click.echo("Table 'invitations' déjà présente.")

        # Migration with_conso → invitation_type sur invitations
        if "invitations" in inspector.get_table_names():
            inv_cols = {c["name"] for c in inspector.get_columns("invitations")}
            if "invitation_type" not in inv_cols:
                db.session.execute(
                    text(
                        "ALTER TABLE invitations "
                        "ADD COLUMN invitation_type VARCHAR(20) NOT NULL DEFAULT 'SANS_CONSO'"
                    )
                )
                if "with_conso" in inv_cols:
                    db.session.execute(
                        text(
                            "UPDATE invitations SET invitation_type = 'AVEC_CONSO' "
                            "WHERE with_conso = 1"
                        )
                    )
                db.session.commit()
                click.echo("Colonne 'invitation_type' ajoutée à invitations.")
            else:
                click.echo("Colonne 'invitation_type' déjà présente sur invitations.")

        # Colonne admin_cc_email sur smtp_config
        if "smtp_config" in inspector.get_table_names():
            smtp_cols = {c["name"] for c in inspector.get_columns("smtp_config")}
            if "admin_cc_email" not in smtp_cols:
                db.session.execute(
                    text(
                        "ALTER TABLE smtp_config "
                        "ADD COLUMN admin_cc_email VARCHAR(200)"
                    )
                )
                db.session.commit()
                click.echo("Colonne 'admin_cc_email' ajoutée à smtp_config.")
            else:
                click.echo("Colonne 'admin_cc_email' déjà présente sur smtp_config.")

        # Colonne custom_email_body sur sponsors
        if "sponsors" in inspector.get_table_names():
            sp_cols = {c["name"] for c in inspector.get_columns("sponsors")}
            if "custom_email_body" not in sp_cols:
                db.session.execute(
                    text(
                        "ALTER TABLE sponsors "
                        "ADD COLUMN custom_email_body TEXT"
                    )
                )
                db.session.commit()
                click.echo("Colonne 'custom_email_body' ajoutée à sponsors.")
            else:
                click.echo("Colonne 'custom_email_body' déjà présente sur sponsors.")

        # Colonne guest_email sur invitations
        if "invitations" in inspector.get_table_names():
            inv_cols = {c["name"] for c in inspector.get_columns("invitations")}
            if "guest_email" not in inv_cols:
                db.session.execute(
                    text(
                        "ALTER TABLE invitations "
                        "ADD COLUMN guest_email VARCHAR(200)"
                    )
                )
                db.session.commit()
                click.echo("Colonne 'guest_email' ajoutée à invitations.")
            else:
                click.echo("Colonne 'guest_email' déjà présente sur invitations.")

        # Mise à jour du template d'email : remplacer l'ancien pattern
        # <img src="cid:${qr_cid}"> par ${qr_codes} (bloc multi-QR).
        tpl = EmailTemplate.query.first()
        if tpl and "${qr_cid}" in (tpl.body_html or ""):
            from utils.mailer import upgrade_legacy_template

            tpl.body_html = upgrade_legacy_template(tpl.body_html)
            db.session.commit()
            click.echo("Template d'email mis à jour (${qr_cid} → ${qr_codes}).")

        click.echo("Migration terminée.")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=bool(int(os.environ.get("FLASK_DEBUG", "0"))))
