"""Tableau de bord : statistiques globales."""
from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func

from extensions import db
from models import Invitation, Sponsor

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    total_sponsors = db.session.query(func.count(Sponsor.id)).scalar() or 0
    total_invitations = (
        db.session.query(func.sum(Sponsor.total_invitations)).scalar() or 0
    )
    # entries_count est une property Python : on compte directement les
    # invitations scannées via la table Invitation.
    total_entries = (
        db.session.query(func.count(Invitation.id))
        .filter(Invitation.scanned_at.isnot(None))
        .scalar()
        or 0
    )
    sponsors = Sponsor.query.order_by(Sponsor.created_at.desc()).all()
    return render_template(
        "dashboard.html",
        total_sponsors=total_sponsors,
        total_invitations=int(total_invitations),
        total_entries=int(total_entries),
        sponsors=sponsors,
    )
