"""Génération des QR codes d'invitation."""
from __future__ import annotations

import base64
from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def generate_qr_png(data: str) -> bytes:
    """Génère un QR code PNG (bytes) à partir d'une chaîne."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_qr_data_url(data: str) -> str:
    """Retourne le QR code encodé en data URL (pour affichage inline HTML)."""
    png = generate_qr_png(data)
    b64 = base64.b64encode(png).decode()
    return f"data:image/png;base64,{b64}"
