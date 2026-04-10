"""Envoi d'emails SMTP avec QR code inline et template personnalisable."""
from __future__ import annotations

import re
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from string import Template
from typing import Optional

from models import EmailTemplate, SmtpConfig, Sponsor
from utils.crypto import decrypt
from utils.qr import generate_qr_png


@dataclass
class SmtpSettings:
    host: str
    port: int
    username: str
    password: str
    use_tls: bool
    use_ssl: bool
    from_name: str
    from_email: str

    @classmethod
    def from_db(cls, cfg: SmtpConfig) -> "SmtpSettings":
        return cls(
            host=cfg.host,
            port=cfg.port,
            username=cfg.username or "",
            password=decrypt(cfg.password_encrypted) if cfg.password_encrypted else "",
            use_tls=cfg.use_tls,
            use_ssl=cfg.use_ssl,
            from_name=cfg.from_name,
            from_email=cfg.from_email,
        )


def _strip_html(html: str) -> str:
    """Retire les balises HTML pour générer une version texte brut basique."""
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</\s*p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_context(sponsor: Sponsor, qr_cid: str) -> dict[str, str]:
    """Variables disponibles pour la substitution dans le template d'email."""
    montant = f"{sponsor.amount:.2f} €" if sponsor.amount is not None else "—"
    return {
        "entreprise": sponsor.company_name or "",
        "contact": sponsor.contact_name or "",
        "email": sponsor.contact_email or "",
        "telephone": sponsor.contact_phone or "",
        "nb_invitations": str(sponsor.total_invitations),
        "tier": sponsor.tier.label if sponsor.tier else "",
        "montant": montant,
        "qr_cid": f"cid:{qr_cid}",
    }


def render_template(template_str: str, context: dict[str, str]) -> str:
    """Interpolation des variables via `str.Template` (syntaxe ${var})."""
    return Template(template_str).safe_substitute(context)


def _send(smtp: SmtpSettings, msg: EmailMessage) -> None:
    context = ssl.create_default_context()
    if smtp.use_ssl:
        with smtplib.SMTP_SSL(smtp.host, smtp.port, context=context, timeout=30) as server:
            if smtp.username:
                server.login(smtp.username, smtp.password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp.host, smtp.port, timeout=30) as server:
            server.ehlo()
            if smtp.use_tls:
                server.starttls(context=context)
                server.ehlo()
            if smtp.username:
                server.login(smtp.username, smtp.password)
            server.send_message(msg)


def send_invitation_email(
    smtp: SmtpSettings,
    template: EmailTemplate,
    sponsor: Sponsor,
    qr_payload: str,
    recipient_override: Optional[str] = None,
) -> None:
    """Envoie l'email d'invitation avec QR code inline au sponsor."""
    qr_cid = make_msgid(domain="balsp.local")[1:-1]  # retire <>
    context = build_context(sponsor, qr_cid)

    subject = render_template(template.subject, context)
    body_html = render_template(template.body_html, context)
    body_text = _strip_html(body_html)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((smtp.from_name, smtp.from_email))
    msg["To"] = recipient_override or sponsor.contact_email

    msg.set_content(body_text or "Veuillez ouvrir cet email en HTML.")
    msg.add_alternative(body_html, subtype="html")

    # Pièce jointe inline : QR code
    qr_png = generate_qr_png(qr_payload)
    html_part = msg.get_payload()[1]
    html_part.add_related(
        qr_png,
        maintype="image",
        subtype="png",
        cid=f"<{qr_cid}>",
        filename="invitation-qr.png",
    )

    _send(smtp, msg)


def send_simple_email(
    smtp: SmtpSettings, to: str, subject: str, body_html: str
) -> None:
    """Email simple sans QR code (utilisé pour les tests de connexion)."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((smtp.from_name, smtp.from_email))
    msg["To"] = to
    msg.set_content(_strip_html(body_html) or "Test")
    msg.add_alternative(body_html, subtype="html")
    _send(smtp, msg)
