"""Page scanner + endpoints JSON pour le pointage à l'accueil."""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request, url_for
from flask_login import login_required

from extensions import csrf, db
from models import Guest, ScanLog, Sponsor

bp = Blueprint("scan", __name__, url_prefix="/scan")


@bp.route("/")
@login_required
def page():
    return render_template("scan.html")


def _sponsor_payload(sponsor: Sponsor) -> dict:
    logo_url = None
    if sponsor.logo_filename:
        logo_url = url_for("static", filename=f"uploads/logos/{sponsor.logo_filename}")
    guests = [
        {
            "id": g.id,
            "name": g.name,
            "checked_in": g.checked_in,
        }
        for g in sponsor.guests
    ]
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
        "guests": guests,
    }


@bp.route("/verify", methods=["POST"])
@login_required
def verify():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    if not token:
        return jsonify({"ok": False, "error": "Token manquant."}), 400

    sponsor = Sponsor.query.filter_by(invitation_token=token).first()
    if not sponsor:
        return jsonify({"ok": False, "error": "QR code inconnu."}), 404

    return jsonify({"ok": True, "sponsor": _sponsor_payload(sponsor)})


@bp.route("/check-in", methods=["POST"])
@login_required
def check_in():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    try:
        count = int(data.get("count", 1))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Nombre invalide."}), 400

    if count <= 0:
        return jsonify({"ok": False, "error": "Nombre doit être positif."}), 400

    sponsor = Sponsor.query.filter_by(invitation_token=token).first()
    if not sponsor:
        return jsonify({"ok": False, "error": "QR code inconnu."}), 404

    if sponsor.entries_count + count > sponsor.total_invitations:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": (
                        f"Quota dépassé : {sponsor.entries_count}/"
                        f"{sponsor.total_invitations} déjà utilisées."
                    ),
                    "sponsor": _sponsor_payload(sponsor),
                }
            ),
            409,
        )

    sponsor.entries_count += count
    log = ScanLog(sponsor_id=sponsor.id, count=count)
    db.session.add(log)
    db.session.commit()

    return jsonify({"ok": True, "sponsor": _sponsor_payload(sponsor)})


@bp.route("/undo", methods=["POST"])
@login_required
def undo():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    sponsor = Sponsor.query.filter_by(invitation_token=token).first()
    if not sponsor:
        return jsonify({"ok": False, "error": "QR code inconnu."}), 404

    last_log = (
        ScanLog.query.filter_by(sponsor_id=sponsor.id)
        .order_by(ScanLog.scanned_at.desc())
        .first()
    )
    if not last_log:
        return jsonify({"ok": False, "error": "Aucun pointage à annuler."}), 400

    sponsor.entries_count = max(0, sponsor.entries_count - last_log.count)
    db.session.delete(last_log)
    db.session.commit()
    return jsonify({"ok": True, "sponsor": _sponsor_payload(sponsor)})


@bp.route("/guest-toggle", methods=["POST"])
@login_required
def guest_toggle():
    """Bascule le statut checked_in d'un invité nommé."""
    data = request.get_json(silent=True) or {}
    guest_id = data.get("guest_id")
    if not guest_id:
        return jsonify({"ok": False, "error": "ID invité manquant."}), 400

    guest = db.session.get(Guest, guest_id)
    if not guest:
        return jsonify({"ok": False, "error": "Invité inconnu."}), 404

    from datetime import datetime

    guest.checked_in = not guest.checked_in
    guest.checked_in_at = datetime.utcnow() if guest.checked_in else None
    db.session.commit()

    sponsor = guest.sponsor
    return jsonify({
        "ok": True,
        "guest": {"id": guest.id, "name": guest.name, "checked_in": guest.checked_in},
        "sponsor": _sponsor_payload(sponsor),
    })
