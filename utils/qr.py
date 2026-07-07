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
        label_height = 70
        margin = 30
        bottom_pad = 15

        font = _load_font(42)
        if total:
            text = f"Invitation {number} / {total}"
        else:
            text = f"Invitation n°{number}"

        # Measure all text to determine canvas size
        tmp_img = Image.new("RGB", (1, 1))
        tmp_draw = ImageDraw.Draw(tmp_img)
        try:
            bbox = tmp_draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        except Exception:
            text_w, text_h = tmp_draw.textsize(text, font=font)

        needed_w = text_w + margin * 2
        badge_pad = 14
        cw, ch = 0, 0
        badge_zone_h = 0
        if badge_cfg:
            badge_font = _load_font(32)
            badge_text = badge_cfg["text"]
            try:
                bbox = tmp_draw.textbbox((0, 0), badge_text, font=badge_font)
                cw = bbox[2] - bbox[0]
                ch = bbox[3] - bbox[1]
            except Exception:
                cw, ch = tmp_draw.textsize(badge_text, font=badge_font)
            needed_w = max(needed_w, cw + badge_pad * 2 + margin * 2)
            badge_zone_h = ch + badge_pad * 2 + 10

        canvas_w = max(img.size[0], needed_w)
        canvas_h = img.size[1] + label_height + badge_zone_h + bottom_pad
        canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
        canvas.paste(img, ((canvas_w - img.size[0]) // 2, 0))

        draw = ImageDraw.Draw(canvas)
        draw.text(
            ((canvas_w - text_w) // 2, img.size[1] + (label_height - text_h) // 2),
            text,
            fill="#8b0000",
            font=font,
        )

        if badge_cfg:
            ry = img.size[1] + label_height + 2
            rx = (canvas_w - cw) // 2 - badge_pad
            draw.rounded_rectangle(
                [rx, ry, rx + cw + badge_pad * 2, ry + ch + badge_pad],
                radius=8, fill=badge_cfg["fill"],
            )
            draw.text(
                ((canvas_w - cw) // 2, ry + badge_pad // 2),
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
