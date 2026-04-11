"""Configuration SMTP + personnalisation du modèle d'email + branding."""
from __future__ import annotations

import os

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required

from extensions import admin_required, db, log_action
from forms import BrandingForm, EmailTemplateForm, SmtpConfigForm
from models import EmailTemplate, Invitation, SmtpConfig, Sponsor, Tier
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
@admin_required
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
        log_action("edit_smtp", "Configuration SMTP modifiée.")
        db.session.commit()
        flash("Configuration SMTP enregistrée.", "success")
        return redirect(url_for("settings.smtp"))

    return render_template("settings/smtp.html", form=form, cfg=cfg)


def _sample_sponsor() -> Sponsor:
    """Sponsor factice (avec invitations) pour l'aperçu."""
    s = Sponsor(
        company_name="Entreprise Exemple",
        contact_name="Jean Dupont",
        contact_email="jean.dupont@exemple.fr",
        contact_phone="01 23 45 67 89",
        tier=Tier.BETWEEN_501_999,
        amount=750,
        total_invitations=3,
    )
    s.invitations = [
        Invitation(number=1, token="sample-token-1", guest_name="Jean Dupont"),
        Invitation(number=2, token="sample-token-2", guest_name=None),
        Invitation(number=3, token="sample-token-3", guest_name=None),
    ]
    return s


@bp.route("/email", methods=["GET", "POST"])
@login_required
@admin_required
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
            log_action("restore_email_template", "Modèle d'email restauré par défaut.")
            db.session.commit()
            flash("Modèle par défaut restauré.", "success")
            return redirect(url_for("settings.email_template"))

        if form.preview.data:
            from utils.qr import generate_qr_data_url

            sample = _sample_sponsor()
            logo_path = str(current_app.config.get("BAL_LOGO_PATH", ""))
            if not os.path.exists(logo_path):
                logo_path = None
            total = len(sample.invitations)
            qr_imgs = []
            for inv in sample.invitations:
                data_url = generate_qr_data_url(
                    inv.token, number=inv.number, total=total, logo_path=logo_path
                )
                name_block = (
                    f'<div style="color:#555;font-size:14px;">Au nom de <strong>{inv.guest_name}</strong></div>'
                    if inv.guest_name else ""
                )
                qr_imgs.append(
                    f'<div style="display:inline-block;margin:12px;text-align:center;vertical-align:top;">'
                    f'<img src="{data_url}" style="max-width:240px;" alt="QR {inv.number}">'
                    f'{name_block}</div>'
                )
            qr_html = '<div style="text-align:center;margin:25px 0;">' + "".join(qr_imgs) + "</div>"
            context = build_context(sample, qr_codes_html=qr_html)
            preview_html = render_email_template(form.body_html.data, context)
            flash("Aperçu généré avec un sponsor fictif.", "info")
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
                    invitations=sample.invitations,
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
        log_action("edit_email_template", "Modèle d'email modifié.")
        db.session.commit()
        flash("Modèle d'email enregistré.", "success")
        return redirect(url_for("settings.email_template"))

    return render_template(
        "settings/email_template.html", form=form, preview_html=preview_html
    )


@bp.route("/branding", methods=["GET", "POST"])
@login_required
@admin_required
def branding():
    """Upload du logo du bal (placé au centre de chaque QR code)."""
    logo_path = str(current_app.config["BAL_LOGO_PATH"])
    logo_exists = os.path.exists(logo_path)
    form = BrandingForm()

    if form.validate_on_submit():
        if form.remove.data:
            if logo_exists:
                try:
                    os.remove(logo_path)
                    log_action("remove_bal_logo", "Logo du bal supprimé.")
                    db.session.commit()
                    flash("Logo supprimé.", "success")
                except OSError as exc:
                    flash(f"Impossible de supprimer le logo : {exc}", "danger")
            else:
                flash("Aucun logo à supprimer.", "info")
            return redirect(url_for("settings.branding"))

        if not form.logo.data:
            flash("Veuillez sélectionner un fichier.", "warning")
            return redirect(url_for("settings.branding"))

        # Conversion en PNG et enregistrement
        try:
            from PIL import Image

            os.makedirs(os.path.dirname(logo_path), exist_ok=True)
            img = Image.open(form.logo.data).convert("RGBA")
            # Redimensionner si trop grand (max 600x600)
            img.thumbnail((600, 600), Image.LANCZOS)
            img.save(logo_path, format="PNG")
            log_action("set_bal_logo", "Logo du bal mis à jour.")
            db.session.commit()
            flash("Logo du bal enregistré.", "success")
        except Exception as exc:  # noqa: BLE001
            current_app.logger.exception("Upload du logo du bal échoué")
            flash(f"Impossible d'enregistrer le logo : {exc}", "danger")
        return redirect(url_for("settings.branding"))

    # Aperçu : un QR de démonstration avec le logo actuel
    preview_data_url = None
    try:
        from utils.qr import generate_qr_data_url

        preview_data_url = generate_qr_data_url(
            "demo-preview-token",
            number=1,
            total=3,
            logo_path=logo_path if logo_exists else None,
        )
    except Exception:
        current_app.logger.exception("Aperçu logo échoué")

    return render_template(
        "settings/branding.html",
        form=form,
        logo_exists=logo_exists,
        preview_data_url=preview_data_url,
    )
