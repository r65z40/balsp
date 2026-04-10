# balsp — Billetterie Sponsors

Application web légère pour gérer les invitations offertes aux sponsors d'un
concert annuel : saisie des sponsors, génération d'un QR code, envoi par email
personnalisable, et pointage des entrées à l'accueil via la caméra.

## Fonctionnalités

- Gestion de sponsors (logo, nom entreprise, contact, téléphone, email)
- Calcul automatique du nombre d'invitations selon le montant :
  - ≤ 250 € → 1 invitation
  - 251 – 500 € → 2 invitations
  - 501 – 999 € → 3 invitations
  - ≥ 1000 € → Sponsor exclusif (6 + 4 offertes = 10 invitations)
- Sponsor donateur : nombre d'invitations personnalisé
- QR code unique par sponsor, téléchargeable et intégré à l'email
- Envoi d'invitations par email avec **modèle personnalisable** (sujet + HTML)
  et variables dynamiques (`${entreprise}`, `${contact}`, `${nb_invitations}`…)
- Configuration SMTP libre (Gmail, Outlook, Yahoo, serveur custom…)
- Scanner QR code depuis le navigateur (caméra) pour l'accueil
- Pointage des entrées en temps réel, annulation possible du dernier scan
- Tableau de bord avec statistiques

## Installation

### Prérequis
- Python 3.10+
- pip

### Étapes

```bash
git clone <url-du-repo>
cd balsp

python -m venv venv
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate           # Windows

pip install -r requirements.txt

cp .env.example .env
# Éditer .env et renseigner :
#   - SECRET_KEY (générer avec : python -c "import secrets; print(secrets.token_hex(32))")
#   - FERNET_KEY (générer avec : python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
#   - ADMIN_USERNAME et ADMIN_PASSWORD

flask --app app init-db           # Crée la base SQLite et le compte admin
flask --app app run               # Lance le serveur sur http://localhost:5000
```

## Configuration SMTP

Après le premier lancement, connectez-vous et allez dans **Paramètres →
Configuration SMTP** pour renseigner les informations de votre fournisseur :

| Fournisseur | Host                 | Port | STARTTLS | Notes                                |
|-------------|----------------------|------|----------|--------------------------------------|
| Gmail       | `smtp.gmail.com`     | 587  | ✅        | Mot de passe d'application requis    |
| Outlook     | `smtp.office365.com` | 587  | ✅        | Compte Microsoft                     |
| Yahoo       | `smtp.mail.yahoo.com`| 587  | ✅        | Mot de passe d'application           |

Le mot de passe SMTP est chiffré en base avec Fernet avant stockage.

Utilisez le bouton **« Envoyer un email de test »** pour vérifier la
configuration avant de commencer à envoyer des invitations.

## Personnalisation du modèle d'email

Dans **Paramètres → Modèle d'email**, vous pouvez :

- Modifier le sujet et le corps HTML du mail envoyé aux sponsors
- Insérer des variables dynamiques (listées dans le panneau latéral) :
  - `${entreprise}`, `${contact}`, `${email}`, `${telephone}`
  - `${nb_invitations}`, `${tier}`, `${montant}`
  - `${qr_cid}` — image du QR code (à utiliser dans un `<img src="${qr_cid}">`)
- Générer un aperçu avec un sponsor fictif
- Envoyer un email de test à l'adresse de votre choix
- Restaurer le modèle par défaut à tout moment

## Utilisation de la caméra pour le scan

Les navigateurs exigent **HTTPS** pour autoriser l'accès à la caméra (sauf sur
`localhost`). Pour utiliser un téléphone sur le réseau local à l'entrée du
concert :

```bash
pip install pyopenssl           # Certificat auto-signé
flask --app app run --host 0.0.0.0 --cert=adhoc
```

Puis accédez à `https://<IP-du-serveur>:5000/scan` depuis le téléphone et
acceptez le certificat.

## Structure du projet

```
balsp/
├── app.py                   # Factory Flask + CLI init-db
├── config.py
├── extensions.py
├── models.py                # Sponsor, User, ScanLog, SmtpConfig, EmailTemplate
├── forms.py
├── utils/
│   ├── tiers.py             # Règles tier ↔ nb invitations
│   ├── qr.py                # Génération QR PNG
│   ├── mailer.py            # Envoi SMTP + templating
│   ├── crypto.py            # Fernet (mot de passe SMTP)
│   └── defaults.py          # Modèle d'email par défaut
├── routes/
│   ├── auth.py
│   ├── dashboard.py
│   ├── sponsors.py
│   ├── scan.py
│   └── settings.py
├── templates/
│   ├── base.html, login.html, dashboard.html, scan.html
│   ├── sponsors/{list,form,detail}.html
│   └── settings/{smtp,email_template}.html
├── static/
│   ├── css/app.css
│   ├── js/scanner.js        # Intégration html5-qrcode
│   └── uploads/logos/       # Logos sponsors (gitignoré)
├── instance/balsp.db        # SQLite (gitignoré)
├── requirements.txt
├── .env.example
└── README.md
```

## Sécurité

- Mot de passe admin hashé avec Werkzeug
- Mot de passe SMTP chiffré avec Fernet (clé dans `.env`, jamais commitée)
- CSRF activé globalement
- Token QR = UUID v4 (128 bits, non devinable)
- Upload de logo limité à 2 Mo et aux extensions image courantes

## Licence

Projet interne.
