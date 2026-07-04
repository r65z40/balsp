"""Génération de PDF d'invitations avec QR codes."""
from __future__ import annotations

import io
import os
import tempfile
from typing import Optional

from fpdf import FPDF

from models import Invitation, Sponsor
from utils.qr import generate_qr_png


def _find_ttf_font() -> Optional[str]:
    """Trouve une police TTF Unicode sur le système."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _find_ttf_font_bold() -> Optional[str]:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


class InvitationPDF(FPDF):
    """PDF A4 avec en-tête pompier et QR codes."""

    def __init__(self, sponsor: Sponsor, bal_logo_path: Optional[str] = None):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.sponsor = sponsor
        self.bal_logo_path = bal_logo_path
        self.set_auto_page_break(auto=True, margin=15)

        # Police Unicode pour supporter les accents et tirets
        ttf = _find_ttf_font()
        ttf_bold = _find_ttf_font_bold()
        if ttf:
            self.add_font("CustomFont", "", ttf, uni=True)
            if ttf_bold:
                self.add_font("CustomFont", "B", ttf_bold, uni=True)
            else:
                self.add_font("CustomFont", "B", ttf, uni=True)
            self.font_family_name = "CustomFont"
        else:
            self.font_family_name = "Helvetica"
            self._latin1_mode = True

        self.add_page()

    def safe_text(self, text: str) -> str:
        """Remplace les caractères hors latin-1 si on est en mode Helvetica."""
        if not getattr(self, "_latin1_mode", False):
            return text
        replacements = {
            "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
            "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u20ac": "EUR",
            "\u2264": "<=", "\u2265": ">=",
        }
        for char, repl in replacements.items():
            text = text.replace(char, repl)
        try:
            text.encode("latin-1")
        except UnicodeEncodeError:
            text = text.encode("latin-1", errors="replace").decode("latin-1")
        return text

    def header(self):
        # Bandeau rouge
        self.set_fill_color(200, 16, 46)
        self.rect(0, 0, 210, 32, "F")

        # Logo dans le bandeau (à gauche)
        if self.bal_logo_path:
            try:
                self.image(self.bal_logo_path, x=8, y=3, h=26)
            except Exception:
                pass

        self.set_text_color(255, 255, 255)
        self.set_font(self.font_family_name, "B", 16)
        self.set_y(7)
        self.cell(0, 8, self.safe_text("Bal des Sapeurs-Pompiers d'Auxerre"), align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font(self.font_family_name, "", 11)
        self.set_text_color(240, 165, 0)
        self.cell(0, 6, self.safe_text(f"Invitations - {self.sponsor.company_name}"), align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(8)

    def footer(self):
        self.set_y(-12)
        self.set_font(self.font_family_name, "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, self.safe_text(f"Page {self.page_no()}/{{nb}}"), align="C")


def generate_invitations_pdf(
    sponsor: Sponsor,
    invitations: list[Invitation],
    bal_logo_path: Optional[str] = None,
) -> bytes:
    """Genere un PDF A4 avec 2 QR codes par page."""
    pdf = InvitationPDF(sponsor, bal_logo_path)
    pdf.alias_nb_pages()
    total = len(invitations)

    # Infos sponsor sur la premiere page
    pdf.set_font(pdf.font_family_name, "", 11)
    pdf.cell(0, 6, pdf.safe_text(f"Sponsor : {sponsor.company_name}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, pdf.safe_text(f"Contact : {sponsor.contact_name} ({sponsor.contact_email})"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, pdf.safe_text(f"Nombre d'invitations : {total}"), new_x="LMARGIN", new_y="NEXT")
    if sponsor.tier:
        pdf.cell(0, 6, pdf.safe_text(f"Categorie : {sponsor.tier.label}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Ligne de separation
    pdf.set_draw_color(200, 16, 46)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # 2 QR par page, centres verticalement
    qr_size = 65  # mm
    items_on_page = 0

    for inv in invitations:
        if items_on_page == 2:
            pdf.add_page()
            items_on_page = 0

        # Generer le QR code en PNG (sans le bandeau texte, le PDF ajoute le sien)
        qr_png = generate_qr_png(
            inv.token,
            logo_path=bal_logo_path,
        )

        # Sauvegarder temporairement le PNG pour fpdf
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(qr_png)
            tmp_path = tmp.name

        try:
            start_y = pdf.get_y()

            # Centrer le QR
            x_qr = (210 - qr_size) / 2
            pdf.image(tmp_path, x=x_qr, y=start_y, w=qr_size)

            # Texte sous le QR
            pdf.set_y(start_y + qr_size + 3)
            pdf.set_font(pdf.font_family_name, "B", 14)
            pdf.set_text_color(139, 0, 0)
            label = pdf.safe_text(f"Invitation {inv.number} / {total}")
            pdf.cell(0, 8, label, align="C", new_x="LMARGIN", new_y="NEXT")

            if inv.guest_name:
                pdf.set_font(pdf.font_family_name, "", 11)
                pdf.set_text_color(80, 80, 80)
                pdf.cell(0, 6, pdf.safe_text(f"Au nom de : {inv.guest_name}"), align="C", new_x="LMARGIN", new_y="NEXT")

            # Badge type d'invitation
            pdf.set_font(pdf.font_family_name, "B", 11)
            inv_type = inv.invitation_type.name if inv.invitation_type else "SANS_CONSO"
            if inv_type == "SPONSOR_EXCLUSIF":
                pdf.set_fill_color(139, 0, 0)
                pdf.set_text_color(255, 255, 255)
                type_label = "SPONSOR EXCLUSIF"
            elif inv_type == "AVEC_CONSO":
                pdf.set_fill_color(212, 160, 23)
                pdf.set_text_color(255, 255, 255)
                type_label = "AVEC CONSOMMATION"
            else:
                pdf.set_fill_color(220, 220, 220)
                pdf.set_text_color(100, 100, 100)
                type_label = "Sans consommation"
            label_w = pdf.get_string_width(pdf.safe_text(type_label)) + 10
            pdf.cell(0, 1, "", new_x="LMARGIN", new_y="NEXT")
            x_badge = (210 - label_w) / 2
            pdf.set_x(x_badge)
            pdf.cell(label_w, 7, pdf.safe_text(type_label), align="C", fill=True, new_x="LMARGIN", new_y="NEXT")

            pdf.set_text_color(0, 0, 0)
            pdf.ln(6)

            # Ligne pointillee entre les 2 QR de la page
            if items_on_page == 0:
                pdf.set_draw_color(180, 180, 180)
                pdf.set_line_width(0.2)
                pdf.dashed_line(20, pdf.get_y(), 190, pdf.get_y(), dash_length=3, space_length=2)
                pdf.ln(6)

            items_on_page += 1
        finally:
            os.unlink(tmp_path)

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
