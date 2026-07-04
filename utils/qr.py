"""Génération des QR codes d'invitation avec logo central et numéro."""
from __future__ import annotations

import base64
import os
from io import BytesIO
from typing import Optional

import qrcode
from PIL import Image, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_H


def _load_font(size: int) -> ImageFont.ImageFont:
    """Charge une police TrueType si possible, sinon police par défaut."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _overlay_logo(qr_img: Image.Image, logo_path: str) -> Image.Image:
    """Colle le logo au centre du QR, avec un fond blanc pour la lisibilité."""
    try:
        logo = Image.open(logo_path).convert("RGBA")
    except Exception:
        return qr_img

    qr_w, qr_h = qr_img.size
    target = qr_w // 5  # 20% de la largeur
    logo.thumbnail((target, target), Image.LANCZOS)
    lw, lh = logo.size

    # Fond blanc carré légèrement plus grand que le logo
    pad = 8
    box_size = max(lw, lh) + pad * 2
    box = Image.new("RGBA", (box_size, box_size), (255, 255, 255, 255))
    box.paste(logo, ((box_size - lw) // 2, (box_size - lh) // 2), mask=logo)

    pos = ((qr_w - box_size) // 2, (qr_h - box_size) // 2)
    qr_img.paste(box, pos, mask=box)
    return qr_img


_BADGE_CONFIG = {
    "AVEC_CONSO": {"text": "AVEC CONSOMMATION", "fill": "#d4a017"},
    "SPONSOR_EXCLUSIF": {"text": "SPONSOR EXCLUSIF", "fill": "#8b0000"},
}


def _build_qr_image(
    data: str,
    number: Optional[int] = None,
    total: Optional[int] = None,
    logo_path: Optional[str] = None,
    invitation_type_name: Optional[str] = None,
) -> Image.Image:
    """Construit l'image PIL du QR code avec logo et numéro."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    if logo_path and os.path.exists(logo_path):
        img = _overlay_logo(img, logo_path)

    if number is not None:
        badge_cfg = _BADGE_CONFIG.get(invitation_type_name)
        badge_height = 50 if badge_cfg else 0
        label_height = 80
        canvas = Image.new("RGB", (img.size[0], img.size[1] + label_height + badge_height), "white")
        canvas.paste(img, (0, 0))

        draw = ImageDraw.Draw(canvas)
        font = _load_font(48)
        if total:
            text = f"Invitation {number} / {total}"
        else:
            text = f"Invitation n°{number}"
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        except Exception:
            text_w, text_h = draw.textsize(text, font=font)

        draw.text(
            ((canvas.size[0] - text_w) // 2, img.size[1] + (label_height - text_h) // 2 - 4),
            text,
            fill="#8b0000",
            font=font,
        )

        if badge_cfg:
            badge_font = _load_font(36)
            badge_text = badge_cfg["text"]
            try:
                bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
                cw = bbox[2] - bbox[0]
                ch = bbox[3] - bbox[1]
            except Exception:
                cw, ch = draw.textsize(badge_text, font=badge_font)
            pad = 8
            rx = (canvas.size[0] - cw) // 2 - pad
            ry = img.size[1] + label_height + (badge_height - ch) // 2 - pad // 2
            draw.rounded_rectangle(
                [rx, ry, rx + cw + pad * 2, ry + ch + pad],
                radius=8, fill=badge_cfg["fill"],
            )
            draw.text(
                ((canvas.size[0] - cw) // 2, ry + pad // 2),
                badge_text, fill="#ffffff", font=badge_font,
            )

        img = canvas

    return img


def generate_qr_png(
    data: str,
    number: Optional[int] = None,
    total: Optional[int] = None,
    logo_path: Optional[str] = None,
    invitation_type_name: Optional[str] = None,
) -> bytes:
    """Génère un QR code PNG (bytes) avec logo optionnel et numéro."""
    img = _build_qr_image(data, number=number, total=total, logo_path=logo_path, invitation_type_name=invitation_type_name)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_qr_data_url(
    data: str,
    number: Optional[int] = None,
    total: Optional[int] = None,
    logo_path: Optional[str] = None,
    invitation_type_name: Optional[str] = None,
) -> str:
    """Retourne le QR code encodé en data URL (pour affichage inline HTML)."""
    png = generate_qr_png(data, number=number, total=total, logo_path=logo_path, invitation_type_name=invitation_type_name)
    b64 = base64.b64encode(png).decode()
    return f"data:image/png;base64,{b64}"
