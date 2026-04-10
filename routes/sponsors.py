"""Routes CRUD sponsors + envoi email."""
from __future__ import annotations

import os
import uuid
from datetime import datetime

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required
from werkzeug.utils import secure_filename

from extensions import db
from forms import SponsorForm
from models import EmailTemplate, SmtpConfig, Sponsor, Tier
from utils.mailer import SmtpSettings, send_invitation_email
from utils.qr import generate_qr_data_url, generate_qr_png
from utils.tiers import compute_invitations, tier_from_amount

bp = Blueprint("sponsors", __name__, url_prefix="/sponsors")


def _save_logo(file_storage) -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = current_app.config["ALLOWED_LOGO_EXTENSIONS"]
    if ext not in allowed:
        raise ValueError("Format de logo non supporté.")
    unique = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    file_storage.save(os.path.join(upload_dir, unique))
    return unique


def _delete_logo(filename: str | None) -> None:
    if not filename:
        return
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _apply_form_to_sponsor(form: SponsorForm, sponsor: Sponsor) -> None:
    sponsor.company_name = form.company_name.data.strip()
    sponsor.contact_name = form.contact_name.data.strip()
    sponsor.contact_email = form.contact_email.data.strip()
    sponsor.contact_phone = (form.contact_phone.data or "").strip() or None

    if form.is_donor.data:
        sponsor.tier = Tier.DONOR
        sponsor.amount = form.amount.data  # peut être None
        sponsor.custom_invitations = int(form.custom_invitations.data)
        sponsor.total_invitations = compute_invitations(
            Tier.DONOR, sponsor.custom_invitations
        )
    else:
        sponsor.amount = form.amount.data
        sponsor.tier = tier_from_amount(form.amount.data)
        sponsor.custom_invitations = None
        sponsor.total_invitations = compute_invitations(sponsor.tier)


@bp.route("/")
@login_required
def list_sponsors():
    sponsors = Sponsor.query.order_by(Sponsor.created_at.desc()).all()
    return render_template("sponsors/list.html", sponsors=sponsors)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_sponsor():
    form = SponsorForm()
    if form.validate_on_submit():
        try:
            sponsor = Sponsor()
            _apply_form_to_sponsor(form, sponsor)
            sponsor.logo_filename = _save_logo(form.logo.data)
            db.session.add(sponsor)
            db.session.commit()
            flash("Sponsor créé avec succès.", "success")
            return redirect(url_for("sponsors.detail", sponsor_id=sponsor.id))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    return render_template("sponsors/form.html", form=form, sponsor=None)


@bp.route("/<int:sponsor_id>")
@login_required
def detail(sponsor_id: int):
    sponsor = Sponsor.query.get_or_404(sponsor_id)
    qr_data_url = generate_qr_data_url(sponsor.invitation_token)
    return render_template(
        "sponsors/detail.html", sponsor=sponsor, qr_data_url=qr_data_url
    )


@bp.route("/<int:sponsor_id>/edit", methods=["GET", "POST"])
@login_required
def edit(sponsor_id: int):
    sponsor = Sponsor.query.get_or_404(sponsor_id)
    form = SponsorForm(obj=sponsor)
    if request.method == "GET":
        form.is_donor.data = sponsor.tier == Tier.DONOR
        form.custom_invitations.data = sponsor.custom_invitations
        form.amount.data = sponsor.amount

    if form.validate_on_submit():
        try:
            _apply_form_to_sponsor(form, sponsor)
            new_logo = _save_logo(form.logo.data)
            if new_logo:
                _delete_logo(sponsor.logo_filename)
                sponsor.logo_filename = new_logo
            db.session.commit()
            flash("Sponsor mis à jour.", "success")
            return redirect(url_for("sponsors.detail", sponsor_id=sponsor.id))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    return render_template("sponsors/form.html", form=form, sponsor=sponsor)


@bp.route("/<int:sponsor_id>/delete", methods=["POST"])
@login_required
def delete(sponsor_id: int):
    sponsor = Sponsor.query.get_or_404(sponsor_id)
    _delete_logo(sponsor.logo_filename)
    db.session.delete(sponsor)
    db.session.commit()
    flash("Sponsor supprimé.", "success")
    return redirect(url_for("sponsors.list_sponsors"))


@bp.route("/<int:sponsor_id>/qr.png")
@login_required
def qr_png(sponsor_id: int):
    sponsor = Sponsor.query.get_or_404(sponsor_id)
    return Response(generate_qr_png(sponsor.invitation_token), mimetype="image/png")


@bp.route("/<int:sponsor_id>/send-email", methods=["POST"])
@login_required
def send_email(sponsor_id: int):
    sponsor = Sponsor.query.get_or_404(sponsor_id)
    smtp_cfg = SmtpConfig.query.first()
    if not smtp_cfg:
        flash(
            "Configuration SMTP manquante. Renseignez-la dans les paramètres.",
            "danger",
        )
        return redirect(url_for("sponsors.detail", sponsor_id=sponsor.id))

    template = EmailTemplate.query.first()
    if not template:
        flash("Modèle d'email manquant.", "danger")
        return redirect(url_for("sponsors.detail", sponsor_id=sponsor.id))

    try:
        smtp = SmtpSettings.from_db(smtp_cfg)
        send_invitation_email(smtp, template, sponsor, sponsor.invitation_token)
        sponsor.email_sent_at = datetime.utcnow()
        db.session.commit()
        flash(f"Email envoyé à {sponsor.contact_email}.", "success")
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Erreur d'envoi d'email")
        flash(f"Erreur lors de l'envoi : {exc}", "danger")
    return redirect(url_for("sponsors.detail", sponsor_id=sponsor.id))
