"""Routes CRUD sponsors + envoi email + gestion des invitations."""
from __future__ import annotations

import io
import os
import uuid
import zipfile
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
    send_file,
    url_for,
)
from flask_login import login_required
from werkzeug.utils import secure_filename

from extensions import db, log_action
from forms import SponsorForm
from models import EmailTemplate, Invitation, SmtpConfig, Sponsor, Tier
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


def _bal_logo_path() -> str | None:
    path = str(current_app.config.get("BAL_LOGO_PATH", ""))
    return path if path and os.path.exists(path) else None


def _sync_invitations(sponsor: Sponsor) -> None:
    """Ajuste le nombre d'invitations pour coller à sponsor.total_invitations.

    Crée des Invitation supplémentaires si N a augmenté, supprime les dernières
    invitations NON SCANNÉES si N a diminué. Si des invitations déjà scannées
    devaient être supprimées, on lève une ValueError.
    """
    current = sorted(list(sponsor.invitations), key=lambda i: i.number)
    target = sponsor.total_invitations

    if len(current) < target:
        # Créer les invitations manquantes
        for n in range(len(current) + 1, target + 1):
            sponsor.invitations.append(Invitation(number=n))
    elif len(current) > target:
        # Supprimer les invitations en trop (par numéro décroissant)
        to_remove = current[target:]
        scanned = [inv for inv in to_remove if inv.scanned_at]
        if scanned:
            raise ValueError(
                f"Impossible de réduire le nombre d'invitations : "
                f"{len(scanned)} invitation(s) à supprimer ont déjà été scannées."
            )
        for inv in to_remove:
            sponsor.invitations.remove(inv)


def _apply_form_to_sponsor(form: SponsorForm, sponsor: Sponsor) -> None:
    sponsor.company_name = form.company_name.data.strip()
    sponsor.contact_name = form.contact_name.data.strip()
    sponsor.contact_email = form.contact_email.data.strip()
    sponsor.contact_phone = (form.contact_phone.data or "").strip() or None
    sponsor.bonus_invitations = form.bonus_invitations.data or 0

    if form.is_donor.data:
        sponsor.tier = Tier.DONOR
        sponsor.amount = form.amount.data
        sponsor.custom_invitations = int(form.custom_invitations.data)
        base = compute_invitations(Tier.DONOR, sponsor.custom_invitations)
    else:
        sponsor.amount = form.amount.data
        sponsor.tier = tier_from_amount(form.amount.data)
        sponsor.custom_invitations = None
        base = compute_invitations(sponsor.tier)

    sponsor.total_invitations = base + sponsor.bonus_invitations
    _sync_invitations(sponsor)


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
            db.session.flush()
            log_action("create_sponsor", f"Sponsor « {sponsor.company_name} » créé avec {sponsor.total_invitations} invitation(s).", "sponsor", sponsor.id)
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
    logo_path = _bal_logo_path()
    total = sponsor.total_invitations
    invitation_qrs = [
        (inv, generate_qr_data_url(inv.token, number=inv.number, total=total, logo_path=logo_path))
        for inv in sponsor.invitations
    ]
    return render_template(
        "sponsors/detail.html",
        sponsor=sponsor,
        invitation_qrs=invitation_qrs,
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
        form.bonus_invitations.data = sponsor.bonus_invitations

    if form.validate_on_submit():
        try:
            _apply_form_to_sponsor(form, sponsor)
            new_logo = _save_logo(form.logo.data)
            if new_logo:
                _delete_logo(sponsor.logo_filename)
                sponsor.logo_filename = new_logo
            log_action("edit_sponsor", f"Sponsor « {sponsor.company_name} » modifié (total : {sponsor.total_invitations}).", "sponsor", sponsor.id)
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
    company = sponsor.company_name
    log_action("delete_sponsor", f"Sponsor « {company} » supprimé.", "sponsor", sponsor.id)
    db.session.delete(sponsor)
    db.session.commit()
    flash("Sponsor supprimé.", "success")
    return redirect(url_for("sponsors.list_sponsors"))


@bp.route("/<int:sponsor_id>/invitations/<int:invitation_id>/qr.png")
@login_required
def qr_png(sponsor_id: int, invitation_id: int):
    invitation = Invitation.query.filter_by(id=invitation_id, sponsor_id=sponsor_id).first_or_404()
    sponsor = invitation.sponsor
    png = generate_qr_png(
        invitation.token,
        number=invitation.number,
        total=sponsor.total_invitations,
        logo_path=_bal_logo_path(),
    )
    return Response(png, mimetype="image/png")


@bp.route("/<int:sponsor_id>/invitations/all.zip")
@login_required
def qr_zip(sponsor_id: int):
    sponsor = Sponsor.query.get_or_404(sponsor_id)
    logo_path = _bal_logo_path()
    total = sponsor.total_invitations

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for inv in sponsor.invitations:
            png = generate_qr_png(
                inv.token, number=inv.number, total=total, logo_path=logo_path
            )
            filename = f"invitation-{inv.number:02d}.png"
            zf.writestr(filename, png)
    buf.seek(0)
    safe_name = sponsor.company_name.replace(" ", "-")
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"qr-{safe_name}.zip",
    )


@bp.route("/<int:sponsor_id>/send-email", methods=["POST"])
@login_required
def send_email(sponsor_id: int):
    sponsor = Sponsor.query.get_or_404(sponsor_id)
    smtp_cfg = SmtpConfig.query.first()
    if not smtp_cfg:
        flash("Configuration SMTP manquante. Renseignez-la dans les paramètres.", "danger")
        return redirect(url_for("sponsors.detail", sponsor_id=sponsor.id))

    template = EmailTemplate.query.first()
    if not template:
        flash("Modèle d'email manquant.", "danger")
        return redirect(url_for("sponsors.detail", sponsor_id=sponsor.id))

    if not sponsor.invitations:
        flash("Ce sponsor n'a aucune invitation à envoyer.", "warning")
        return redirect(url_for("sponsors.detail", sponsor_id=sponsor.id))

    try:
        smtp = SmtpSettings.from_db(smtp_cfg)
        send_invitation_email(smtp, template, sponsor, invitations=list(sponsor.invitations))
        sponsor.email_sent_at = datetime.utcnow()
        log_action(
            "send_email",
            f"Email envoyé à {sponsor.contact_email} ({len(sponsor.invitations)} QR codes).",
            "sponsor",
            sponsor.id,
        )
        db.session.commit()
        flash(f"Email envoyé à {sponsor.contact_email}.", "success")
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Erreur d'envoi d'email")
        flash(f"Erreur lors de l'envoi : {exc}", "danger")
    return redirect(url_for("sponsors.detail", sponsor_id=sponsor.id))


@bp.route("/<int:sponsor_id>/invitations/<int:invitation_id>/rename", methods=["POST"])
@login_required
def rename_invitation(sponsor_id: int, invitation_id: int):
    invitation = Invitation.query.filter_by(id=invitation_id, sponsor_id=sponsor_id).first_or_404()
    name = (request.form.get("guest_name") or "").strip()
    invitation.guest_name = name or None
    log_action(
        "rename_invitation",
        f"Invitation n°{invitation.number} du sponsor « {invitation.sponsor.company_name} » : nom = « {name or '—'} ».",
        "sponsor",
        sponsor_id,
    )
    db.session.commit()
    flash("Nom de l'invité mis à jour.", "success")
    return redirect(url_for("sponsors.detail", sponsor_id=sponsor_id))
