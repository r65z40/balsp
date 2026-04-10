"""Valeurs par défaut (modèle d'email, etc.)."""

DEFAULT_EMAIL_SUBJECT = "Votre invitation pour notre concert annuel"

DEFAULT_EMAIL_BODY = """\
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; color: #222; max-width: 600px; margin: 0 auto;">
  <h2 style="color: #0d6efd;">Bonjour ${contact},</h2>

  <p>
    Au nom de toute l'équipe, nous tenons à remercier
    <strong>${entreprise}</strong> pour son soutien à notre concert annuel
    en tant que <em>${tier}</em>.
  </p>

  <p>
    Votre sponsoring vous donne droit à
    <strong>${nb_invitations} invitation(s)</strong> pour l'événement.
  </p>

  <p>
    Merci de présenter ce QR code à l'accueil le jour du concert :
  </p>

  <p style="text-align: center; margin: 30px 0;">
    <img src="${qr_cid}" alt="QR code invitation" style="max-width: 260px;">
  </p>

  <p>
    En cas de question, n'hésitez pas à répondre directement à cet email.
  </p>

  <p>À très bientôt,<br>L'équipe organisatrice</p>
</body>
</html>
"""
