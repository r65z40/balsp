"""Modèles SQLAlchemy."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


class Tier(enum.Enum):
    UNDER_250 = "≤ 250 €"
    BETWEEN_251_500 = "251 – 500 €"
    BETWEEN_501_999 = "501 – 999 €"
    EXCLUSIVE = "Sponsor exclusif"
    DONOR = "Sponsor donateur"

    @property
    def label(self) -> str:
        return self.value


class Role(enum.Enum):
    ADMIN = "admin"
    USER = "utilisateur"

    @property
    def label(self) -> str:
        return self.value


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(Role), nullable=False, default=Role.USER)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Sponsor(db.Model):
    __tablename__ = "sponsors"

    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False)
    contact_name = db.Column(db.String(150), nullable=False)
    contact_email = db.Column(db.String(200), nullable=False)
    contact_phone = db.Column(db.String(40), nullable=True)
    logo_filename = db.Column(db.String(255), nullable=True)

    amount = db.Column(db.Numeric(10, 2), nullable=True)
    tier = db.Column(db.Enum(Tier), nullable=False)
    custom_invitations = db.Column(db.Integer, nullable=True)
    bonus_invitations = db.Column(db.Integer, nullable=False, default=0)
    total_invitations = db.Column(db.Integer, nullable=False, default=0)

    email_sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    invitations = db.relationship(
        "Invitation",
        backref="sponsor",
        cascade="all, delete-orphan",
        order_by="Invitation.number",
    )

    @property
    def entries_count(self) -> int:
        return sum(1 for inv in self.invitations if inv.scanned_at is not None)

    @property
    def remaining_invitations(self) -> int:
        return max(0, self.total_invitations - self.entries_count)

    @property
    def is_full(self) -> bool:
        return self.entries_count >= self.total_invitations


class Invitation(db.Model):
    __tablename__ = "invitations"

    id = db.Column(db.Integer, primary_key=True)
    sponsor_id = db.Column(
        db.Integer, db.ForeignKey("sponsors.id", ondelete="CASCADE"), nullable=False
    )
    number = db.Column(db.Integer, nullable=False)
    token = db.Column(
        db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    guest_name = db.Column(db.String(200), nullable=True)
    scanned_at = db.Column(db.DateTime, nullable=True)
    scanned_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    scanned_by = db.relationship("User", foreign_keys=[scanned_by_user_id], lazy=True)

    @property
    def is_scanned(self) -> bool:
        return self.scanned_at is not None


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    username = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    target_type = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id], backref="audit_logs", lazy=True)


class SmtpConfig(db.Model):
    __tablename__ = "smtp_config"

    id = db.Column(db.Integer, primary_key=True)
    host = db.Column(db.String(200), nullable=False)
    port = db.Column(db.Integer, nullable=False, default=587)
    username = db.Column(db.String(200), nullable=True)
    password_encrypted = db.Column(db.Text, nullable=True)
    use_tls = db.Column(db.Boolean, nullable=False, default=True)
    use_ssl = db.Column(db.Boolean, nullable=False, default=False)
    from_name = db.Column(db.String(150), nullable=False, default="Bal des Pompiers d'Auxerre")
    from_email = db.Column(db.String(200), nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class EmailTemplate(db.Model):
    __tablename__ = "email_template"

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(255), nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
