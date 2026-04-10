"""Chiffrement symétrique des mots de passe SMTP (Fernet)."""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _get_cipher() -> Fernet:
    key = current_app.config.get("FERNET_KEY", "")
    if not key:
        raise RuntimeError(
            "FERNET_KEY manquante. Générez-la avec "
            "`python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"` "
            "et ajoutez-la dans .env."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plain: str) -> str:
    if plain is None or plain == "":
        return ""
    return _get_cipher().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _get_cipher().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError(
            "Impossible de déchiffrer le mot de passe SMTP (FERNET_KEY a changé ?)."
        ) from exc
