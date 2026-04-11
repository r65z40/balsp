"""Page scanner + endpoints JSON pour le pointage à l'accueil.

Flux nouvelle génération : chaque QR code correspond à UNE invitation
spécifique (un QR par personne), pas au sponsor entier. Le scan marque
l'invitation comme utilisée et refuse si elle l'est déjà.
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db, log_action
from models import Invitation, Sponsor

bp = Blueprint("scan", __name__, url_prefix="/scan")


@bp.route("/")
@login_required
def page():
    return render_template("scan.html")


def _invitation_dict(inv: Invitation) -> dict:
    return {
        "id": inv.id,
        "number": inv.number,
        "guest_name": inv.guest_name,
        "scanned": inv.scanned_at is not None,
        "scanned_at": inv.scanned_at.strftime("%d/%m/%Y %H:%M:%S") if inv.scanned_at else None,
        "scanned_by": inv.scanned_by.username if inv.scanned_by else None,
    }


def _sponsor_payload(sponsor: Sponsor, current_invitation_id: int | None = None) -> dict:
    logo_url = None
    if sponsor.logo_filename:
        logo_url = url_for("static", filename=f"uploads/logos/{sponsor.logo_filename}")
    invitations = [_invitation_dict(inv) for inv in sponsor.invitations]
    return {
        "id": sponsor.id,
        "company_name": sponsor.company_name,
        "contact_name": sponsor.contact_name,
        "contact_email": sponsor.contact_email,
        "tier": sponsor.tier.label,
        "total_invitations": sponsor.total_invitations,
        "entries_count": sponsor.entries_count,
        "remaining": sponsor.remaining_invitations,
        "is_full": sponsor.is_full,
        "logo_url": logo_url,
        "invitations": invitations,
        "current_invitation_id": current_invitation_id,
    }


def _find_invitation(token: str) -> Invitation | None:
    return Invitation.query.filter_by(token=token).first()


@bp.route("/verify", methods=["POST"])
@login_required
def verify():
    """Vérifie un token d'invitation et renvoie le sponsor + l'invitation."""
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    if not token:
        return jsonify({"ok": False, "error": "Token manquant."}), 400

    invitation = _find_invitation(token)
    if not invitation:
        return jsonify({"ok": False, "error": "QR code inconnu."}), 404

    return jsonify({
        "ok": True,
        "invitation": _invitation_dict(invitation),
        "sponsor": _sponsor_payload(invitation.sponsor, current_invitation_id=invitation.id),
    })


@bp.route("/check-in", methods=["POST"])
@login_required
def check_in():
    """Marque une invitation comme utilisée (par son token)."""
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    guest_name = (data.get("guest_name") or "").strip()

    invitation = _find_invitation(token)
    if not invitation:
        return jsonify({"ok": False, "error": "QR code inconnu."}), 404

    if invitation.scanned_at is not None:
        return jsonify({
            "ok": False,
            "error": (
                f"Invitation n°{invitation.number} déjà utilisée le "
                f"{invitation.scanned_at.strftime('%d/%m/%Y à %H:%M')}"
                + (f" ({invitation.scanned_by.username})" if invitation.scanned_by else "")
                + "."
            ),
            "invitation": _invitation_dict(invitation),
            "sponsor": _sponsor_payload(invitation.sponsor, current_invitation_id=invitation.id),
        }), 409

    if guest_name and not invitation.guest_name:
        invitation.guest_name = guest_name
    invitation.scanned_at = datetime.utcnow()
    invitation.scanned_by_user_id = current_user.id

    desc = f"Invitation n°{invitation.number} pointée — sponsor « {invitation.sponsor.company_name} »"
    if invitation.guest_name:
        desc += f" — {invitation.guest_name}"
    log_action("check_in", desc + ".", "sponsor", invitation.sponsor_id)
    db.session.commit()

    return jsonify({
        "ok": True,
        "invitation": _invitation_dict(invitation),
        "sponsor": _sponsor_payload(invitation.sponsor, current_invitation_id=invitation.id),
    })


@bp.route("/undo", methods=["POST"])
@login_required
def undo():
    """Annule le pointage d'une invitation donnée (par token)."""
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()

    invitation = _find_invitation(token)
    if not invitation:
        return jsonify({"ok": False, "error": "QR code inconnu."}), 404

    if invitation.scanned_at is None:
        return jsonify({"ok": False, "error": "Cette invitation n'a pas encore été pointée."}), 400

    invitation.scanned_at = None
    invitation.scanned_by_user_id = None
    log_action(
        "undo_check_in",
        f"Annulation du pointage n°{invitation.number} — sponsor « {invitation.sponsor.company_name} ».",
        "sponsor",
        invitation.sponsor_id,
    )
    db.session.commit()

    return jsonify({
        "ok": True,
        "invitation": _invitation_dict(invitation),
        "sponsor": _sponsor_payload(invitation.sponsor, current_invitation_id=invitation.id),
    })


@bp.route("/toggle-invitation", methods=["POST"])
@login_required
def toggle_invitation():
    """Toggle manuel d'une invitation depuis la liste (par id).

    Sert au personnel pour corriger : pointer/dépointer une invitation
    sans avoir à re-scanner le QR, directement depuis la liste affichée
    après le scan d'un autre QR du même sponsor.
    """
    data = request.get_json(silent=True) or {}
    invitation_id = data.get("invitation_id")
    if not invitation_id:
        return jsonify({"ok": False, "error": "ID manquant."}), 400

    invitation = db.session.get(Invitation, invitation_id)
    if not invitation:
        return jsonify({"ok": False, "error": "Invitation inconnue."}), 404

    if invitation.scanned_at is None:
        invitation.scanned_at = datetime.utcnow()
        invitation.scanned_by_user_id = current_user.id
        action_desc = "pointée"
    else:
        invitation.scanned_at = None
        invitation.scanned_by_user_id = None
        action_desc = "dépointée"

    log_action(
        "toggle_invitation",
        f"Invitation n°{invitation.number} {action_desc} — sponsor « {invitation.sponsor.company_name} ».",
        "sponsor",
        invitation.sponsor_id,
    )
    db.session.commit()

    return jsonify({
        "ok": True,
        "invitation": _invitation_dict(invitation),
        "sponsor": _sponsor_payload(invitation.sponsor, current_invitation_id=invitation.id),
    })
