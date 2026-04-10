"""Configuration SMTP + personnalisation du modèle d'email."""
from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_login import login_required

from extensions import db
from forms import EmailTemplateForm, SmtpConfigForm
from models import EmailTemplate, SmtpConfig, Sponsor, Tier
from utils.crypto import encrypt
from utils.defaults import DEFAULT_EMAIL_BODY, DEFAULT_EMAIL_SUBJECT
from utils.mailer import (
    SmtpSettings,
    build_context,
    render_template as render_email_template,
    send_invitation_email,
    send_simple_email,
)

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.route("/", methods=["GET", "POST"])
@login_required
def smtp():
    cfg = SmtpConfig.query.first()
    form = SmtpConfigForm(obj=cfg) if cfg else SmtpConfigForm()

    if form.validate_on_submit():
        if form.test.data:
            # Envoi d'un email de test sans forcément enregistrer
            if not cfg:
                flash("Enregistrez d'abord la configuration avant de tester.", "warning")
                return redirect(url_for("settings.smtp"))
            if not form.test_recipient.data:
                flash("Indiquez une adresse de destination pour le test.", "warning")
                return redirect(url_for("settings.smtp"))
            try:
                smtp_settings = SmtpSettings.from_db(cfg)
                send_simple_email(
                    smtp_settings,
                    form.test_recipient.data,
                    "Test de configuration SMTP",
                    "<p>Si vous recevez cet email, votre configuration SMTP "
                    "fonctionne correctement. 🎉</p>",
                )
                flash(f"Email de test envoyé à {form.test_recipient.data}.", "success")
            except Exception as exc:  # noqa: BLE001
                current_app.logger.exception("Test SMTP échoué")
                flash(f"Échec du test : {exc}", "danger")
            return redirect(url_for("settings.smtp"))

        # Sauvegarde
        if not cfg:
            cfg = SmtpConfig()
            db.session.add(cfg)
        cfg.host = form.host.data.strip()
        cfg.port = form.port.data
        cfg.username = (form.username.data or "").strip() or None
        if form.password.data:
            cfg.password_encrypted = encrypt(form.password.data)
        cfg.use_tls = form.use_tls.data
        cfg.use_ssl = form.use_ssl.data
        cfg.from_name = form.from_name.data.strip()
        cfg.from_email = form.from_email.data.strip()
        db.session.commit()
        flash("Configuration SMTP enregistrée.", "success")
        return redirect(url_for("settings.smtp"))

    return render_template("settings/smtp.html", form=form, cfg=cfg)


def _sample_sponsor() -> Sponsor:
    """Sponsor factice pour l'aperçu."""
    s = Sponsor(
        company_name="Entreprise Exemple",
        contact_name="Jean Dupont",
        contact_email="jean.dupont@exemple.fr",
        contact_phone="01 23 45 67 89",
        tier=Tier.BETWEEN_501_999,
        amount=750,
        total_invitations=3,
    )
    return s


@bp.route("/email", methods=["GET", "POST"])
@login_required
def email_template():
    tpl = EmailTemplate.query.first()
    if not tpl:
        tpl = EmailTemplate(subject=DEFAULT_EMAIL_SUBJECT, body_html=DEFAULT_EMAIL_BODY)
        db.session.add(tpl)
        db.session.commit()

    form = EmailTemplateForm(obj=tpl)
    preview_html = None

    if form.validate_on_submit():
        if form.restore.data:
            tpl.subject = DEFAULT_EMAIL_SUBJECT
            tpl.body_html = DEFAULT_EMAIL_BODY
            db.session.commit()
            flash("Modèle par défaut restauré.", "success")
            return redirect(url_for("settings.email_template"))

        if form.preview.data:
            sample = _sample_sponsor()
            context = build_context(sample, qr_cid="preview")
            # Pour l'aperçu on remplace le cid par une image placeholder
            context["qr_cid"] = (
                "https://upload.wikimedia.org/wikipedia/commons/d/d0/QR_code_for_mobile_English_Wikipedia.svg"
            )
            preview_html = render_email_template(form.body_html.data, context)
            flash("Aperçu généré avec un sponsor fictif.", "info")
            # On ne sauvegarde pas, on réaffiche juste
            return render_template(
                "settings/email_template.html",
                form=form,
                preview_html=preview_html,
                preview_subject=render_email_template(form.subject.data, context),
            )

        if form.send_test.data:
            if not form.test_recipient.data:
                flash("Indiquez une adresse pour le test.", "warning")
                return redirect(url_for("settings.email_template"))
            cfg = SmtpConfig.query.first()
            if not cfg:
                flash("Configurez le SMTP avant d'envoyer un test.", "warning")
                return redirect(url_for("settings.smtp"))
            try:
                smtp_settings = SmtpSettings.from_db(cfg)
                temp_tpl = EmailTemplate(
                    subject=form.subject.data, body_html=form.body_html.data
                )
                sample = _sample_sponsor()
                send_invitation_email(
                    smtp_settings,
                    temp_tpl,
                    sample,
                    qr_payload="SPONSOR-TEST-TOKEN",
                    recipient_override=form.test_recipient.data,
                )
                flash(
                    f"Email de test envoyé à {form.test_recipient.data} "
                    "avec le modèle courant (non enregistré).",
                    "success",
                )
            except Exception as exc:  # noqa: BLE001
                current_app.logger.exception("Envoi test modèle échoué")
                flash(f"Échec de l'envoi de test : {exc}", "danger")
            return redirect(url_for("settings.email_template"))

        # Sauvegarde
        tpl.subject = form.subject.data
        tpl.body_html = form.body_html.data
        db.session.commit()
        flash("Modèle d'email enregistré.", "success")
        return redirect(url_for("settings.email_template"))

    return render_template(
        "settings/email_template.html", form=form, preview_html=preview_html
    )
