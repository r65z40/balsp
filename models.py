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


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

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
    entries_count = db.Column(db.Integer, nullable=False, default=0)

    invitation_token = db.Column(
        db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    email_sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    scan_logs = db.relationship(
        "ScanLog",
        backref="sponsor",
        cascade="all, delete-orphan",
        order_by="ScanLog.scanned_at.desc()",
    )
    guests = db.relationship(
        "Guest",
        backref="sponsor",
        cascade="all, delete-orphan",
        order_by="Guest.id",
    )

    @property
    def remaining_invitations(self) -> int:
        return max(0, self.total_invitations - self.entries_count)

    @property
    def is_full(self) -> bool:
        return self.entries_count >= self.total_invitations


class ScanLog(db.Model):
    __tablename__ = "scan_logs"

    id = db.Column(db.Integer, primary_key=True)
    sponsor_id = db.Column(
        db.Integer, db.ForeignKey("sponsors.id", ondelete="CASCADE"), nullable=False
    )
    count = db.Column(db.Integer, nullable=False, default=1)
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Guest(db.Model):
    __tablename__ = "guests"

    id = db.Column(db.Integer, primary_key=True)
    sponsor_id = db.Column(
        db.Integer, db.ForeignKey("sponsors.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.String(200), nullable=False)
    checked_in = db.Column(db.Boolean, nullable=False, default=False)
    checked_in_at = db.Column(db.DateTime, nullable=True)


class SmtpConfig(db.Model):
    __tablename__ = "smtp_config"

    id = db.Column(db.Integer, primary_key=True)
    host = db.Column(db.String(200), nullable=False)
    port = db.Column(db.Integer, nullable=False, default=587)
    username = db.Column(db.String(200), nullable=True)
    password_encrypted = db.Column(db.Text, nullable=True)
    use_tls = db.Column(db.Boolean, nullable=False, default=True)
    use_ssl = db.Column(db.Boolean, nullable=False, default=False)
    from_name = db.Column(db.String(150), nullable=False, default="Billetterie Sponsors")
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
