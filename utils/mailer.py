"""Envoi d'emails SMTP avec plusieurs QR codes inline et template personnalisable."""
from __future__ import annotations

import re
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from string import Template
from typing import Optional

from flask import current_app

from models import EmailTemplate, Invitation, SmtpConfig, Sponsor
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


def _build_qr_codes_html(invitations: list[Invitation], cids: list[str]) -> str:
    """Construit le bloc HTML contenant toutes les images QR inline."""
    parts = []
    for inv, cid in zip(invitations, cids):
        name_block = ""
        if inv.guest_name:
            name_block = (
                f'<div style="color:#555; font-size:14px; margin-top:4px;">'
                f'Au nom de <strong>{inv.guest_name}</strong></div>'
            )
        parts.append(
            f'<div style="display:inline-block; margin:12px; text-align:center; '
            f'vertical-align:top;">'
            f'<img src="cid:{cid}" alt="QR invitation {inv.number}" '
            f'style="max-width:240px; height:auto; border:1px solid #eee; padding:6px; '
            f'background:#fff;">'
            f'{name_block}'
            f'</div>'
        )
    return (
        '<div style="text-align:center; margin:25px 0;">'
        + "".join(parts)
        + "</div>"
    )


def build_context(
    sponsor: Sponsor,
    qr_codes_html: str = "",
) -> dict[str, str]:
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
        "qr_codes": qr_codes_html,
    }


# Regex : ancien pattern <img src="${qr_cid}" ...> ou <img src="cid:${qr_cid}" ...>
# éventuellement enveloppé dans un <p ...> ... </p>
_OLD_QR_CID_WRAPPED = re.compile(
    r"<p[^>]*>\s*<img[^>]*src=[\"'](?:cid:)?\$\{qr_cid\}[\"'][^>]*/?\s*>\s*</p>",
    re.IGNORECASE | re.DOTALL,
)
_OLD_QR_CID_BARE = re.compile(
    r"<img[^>]*src=[\"'](?:cid:)?\$\{qr_cid\}[\"'][^>]*/?\s*>",
    re.IGNORECASE,
)


def upgrade_legacy_template(html: str) -> str:
    """Remplace l'ancien ``<img src="${qr_cid}">`` par ``${qr_codes}``.

    L'ancien schéma utilisait un seul QR par sponsor avec la variable
    ``${qr_cid}`` dans un attribut ``src`` (avec ou sans préfixe ``cid:``).
    Le nouveau schéma injecte un bloc HTML complet via ``${qr_codes}``.
    """
    result = _OLD_QR_CID_WRAPPED.sub("${qr_codes}", html)
    if result != html:
        return result
    return _OLD_QR_CID_BARE.sub("${qr_codes}", html)


def render_template(template_str: str, context: dict[str, str]) -> str:
    """Interpolation des variables via `str.Template` (syntaxe ${var})."""
    upgraded = upgrade_legacy_template(template_str)
    return Template(upgraded).safe_substitute(context)


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


def _bal_logo_path() -> Optional[str]:
    try:
        path = str(current_app.config.get("BAL_LOGO_PATH", ""))
        return path if path else None
    except RuntimeError:
        return None


def send_invitation_email(
    smtp: SmtpSettings,
    template: EmailTemplate,
    sponsor: Sponsor,
    invitations: Optional[list[Invitation]] = None,
    recipient_override: Optional[str] = None,
) -> None:
    """Envoie l'email d'invitation avec tous les QR codes inline."""
    if invitations is None:
        invitations = list(sponsor.invitations)

    # Un CID distinct par invitation
    cids = [make_msgid(domain="balsp.local")[1:-1] for _ in invitations]
    qr_html = _build_qr_codes_html(invitations, cids)

    context = build_context(sponsor, qr_codes_html=qr_html)
    subject = render_template(template.subject, context)
    body_html = render_template(template.body_html, context)
    body_text = _strip_html(body_html)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((smtp.from_name, smtp.from_email))
    msg["To"] = recipient_override or sponsor.contact_email

    msg.set_content(body_text or "Veuillez ouvrir cet email en HTML.")
    msg.add_alternative(body_html, subtype="html")

    # Attache chaque QR code en pièce jointe inline (CID)
    html_part = msg.get_payload()[1]
    logo_path = _bal_logo_path()
    total = len(invitations)
    for inv, cid in zip(invitations, cids):
        qr_png = generate_qr_png(
            inv.token,
            number=inv.number,
            total=total,
            logo_path=logo_path,
        )
        html_part.add_related(
            qr_png,
            maintype="image",
            subtype="png",
            cid=f"<{cid}>",
            filename=f"invitation-{inv.number}.png",
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
