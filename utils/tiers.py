"""Règles métier : tranches de sponsoring → nombre d'invitations."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from models import Tier

TIER_INVITATIONS: dict[Tier, int] = {
    Tier.UNDER_250: 1,
    Tier.BETWEEN_251_500: 2,
    Tier.BETWEEN_501_999: 3,
    Tier.EXCLUSIVE: 10,  # 6 places + 4 offertes
}


def tier_from_amount(amount: Decimal) -> Tier:
    """Retourne le tier correspondant à un montant de sponsoring.

    Tranches :
      - ≤ 250 € → UNDER_250
      - 251 – 500 € → BETWEEN_251_500
      - 501 – 999 € → BETWEEN_501_999
      - ≥ 1000 € → EXCLUSIVE
    """
    if amount is None:
        raise ValueError("Montant requis pour calculer le tier.")
    amount = Decimal(amount)
    if amount <= Decimal("250"):
        return Tier.UNDER_250
    if amount <= Decimal("500"):
        return Tier.BETWEEN_251_500
    if amount <= Decimal("999"):
        return Tier.BETWEEN_501_999
    return Tier.EXCLUSIVE


def compute_invitations(tier: Tier, custom_invitations: Optional[int] = None) -> int:
    """Nombre total d'invitations pour un tier.

    Pour un sponsor donateur, on utilise la valeur personnalisée saisie.
    """
    if tier == Tier.DONOR:
        if custom_invitations is None or custom_invitations < 0:
            raise ValueError(
                "Un sponsor donateur doit avoir un nombre d'invitations défini."
            )
        return int(custom_invitations)
    return TIER_INVITATIONS[tier]
