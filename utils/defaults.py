"""Valeurs par défaut (modèle d'email, etc.)."""

DEFAULT_EMAIL_SUBJECT = "Vos invitations pour le Bal des Pompiers d'Auxerre"

DEFAULT_EMAIL_BODY = """\
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; color: #222; max-width: 640px; margin: 0 auto;">
  <div style="background: linear-gradient(135deg, #8b0000 0%, #c8102e 100%); padding: 25px; text-align: center; border-radius: 8px 8px 0 0;">
    <h1 style="color: #fff; margin: 0; font-size: 24px;">&#x1F6A8; Bal des Sapeurs-Pompiers</h1>
    <p style="color: #f0a500; margin: 5px 0 0; font-size: 16px;">Auxerre</p>
  </div>

  <div style="padding: 25px; background: #fff; border: 1px solid #eee; border-top: 0;">
    <h2 style="color: #c8102e;">Bonjour ${contact},</h2>

    <p>
      Au nom de toute l'Amicale des Sapeurs-Pompiers d'Auxerre, nous tenons
      à remercier chaleureusement <strong>${entreprise}</strong> pour son
      soutien en tant que <em>${tier}</em>.
    </p>

    <p>
      Votre sponsoring vous donne droit à
      <strong style="color: #c8102e;">${nb_invitations} invitation(s)</strong>
      pour le Bal des Pompiers.
    </p>

    <p>
      Vous trouverez ci-dessous <strong>un QR code par personne</strong>.
      Chaque QR code est valable pour une seule entrée et doit être présenté
      à l'accueil le soir de l'événement (sur téléphone ou imprimé).
    </p>

    ${qr_codes}

    <p>
      En cas de question, n'hésitez pas à répondre directement à cet email.
    </p>

    <p>Nous comptons sur votre présence !<br>
    <strong>L'Amicale des Sapeurs-Pompiers d'Auxerre</strong></p>
  </div>

  <div style="text-align: center; padding: 15px; color: #999; font-size: 12px;">
    Bal des Sapeurs-Pompiers d'Auxerre
  </div>
</body>
</html>
"""
