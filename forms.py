"""Formulaires WTForms."""
from __future__ import annotations

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    BooleanField,
    DecimalField,
    EmailField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)


class LoginForm(FlaskForm):
    username = StringField("Nom d'utilisateur", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Mot de passe", validators=[DataRequired()])
    submit = SubmitField("Se connecter")


class SponsorForm(FlaskForm):
    company_name = StringField(
        "Nom de l'entreprise", validators=[DataRequired(), Length(max=150)]
    )
    contact_name = StringField(
        "Nom du contact", validators=[DataRequired(), Length(max=150)]
    )
    contact_email = EmailField(
        "Email du contact", validators=[DataRequired(), Email(), Length(max=200)]
    )
    contact_phone = StringField(
        "Téléphone", validators=[Optional(), Length(max=40)]
    )
    logo = FileField(
        "Logo",
        validators=[
            Optional(),
            FileAllowed(
                ["png", "jpg", "jpeg", "webp", "gif"],
                "Formats acceptés : PNG, JPG, WEBP, GIF.",
            ),
        ],
    )

    is_donor = BooleanField("Sponsor donateur (nombre d'invitations personnalisé)")
    amount = DecimalField(
        "Montant du sponsoring (€)",
        validators=[Optional(), NumberRange(min=0)],
        places=2,
    )
    custom_invitations = IntegerField(
        "Nombre d'invitations (donateur)",
        validators=[Optional(), NumberRange(min=0, max=200)],
    )
    bonus_invitations = IntegerField(
        "Invitations bonus supplémentaires",
        validators=[Optional(), NumberRange(min=0, max=200)],
        default=0,
    )

    custom_email_body = TextAreaField(
        "Message personnalisé (HTML)",
        validators=[Optional()],
        render_kw={"rows": 8, "style": "font-family: monospace; font-size: 0.85rem;"},
    )

    submit = SubmitField("Enregistrer")

    def validate(self, extra_validators=None) -> bool:  # type: ignore[override]
        if not super().validate(extra_validators=extra_validators):
            return False
        ok = True
        if self.is_donor.data:
            if self.custom_invitations.data is None:
                self.custom_invitations.errors.append(
                    "Nombre d'invitations requis pour un sponsor donateur."
                )
                ok = False
        else:
            if self.amount.data is None:
                self.amount.errors.append(
                    "Montant requis (ou cochez « sponsor donateur »)."
                )
                ok = False
        return ok


class BrandingForm(FlaskForm):
    logo = FileField(
        "Logo du bal (centre des QR codes)",
        validators=[
            Optional(),
            FileAllowed(
                ["png", "jpg", "jpeg"],
                "Formats acceptés : PNG, JPG.",
            ),
        ],
    )
    submit = SubmitField("Enregistrer le logo")
    remove = SubmitField("Supprimer le logo")


class UserForm(FlaskForm):
    username = StringField("Nom d'utilisateur", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("Mot de passe", validators=[Optional(), Length(min=4)])
    role = SelectField("Rôle", choices=[("USER", "Utilisateur"), ("ADMIN", "Administrateur")])
    submit = SubmitField("Enregistrer")


class SmtpConfigForm(FlaskForm):
    host = StringField("Serveur SMTP", validators=[DataRequired(), Length(max=200)])
    port = IntegerField("Port", validators=[DataRequired(), NumberRange(min=1, max=65535)])
    username = StringField("Nom d'utilisateur", validators=[Optional(), Length(max=200)])
    password = PasswordField(
        "Mot de passe (laisser vide pour conserver l'actuel)", validators=[Optional()]
    )
    use_tls = BooleanField("Utiliser STARTTLS", default=True)
    use_ssl = BooleanField("Utiliser SSL/TLS direct", default=False)
    from_name = StringField(
        "Nom de l'expéditeur", validators=[DataRequired(), Length(max=150)]
    )
    from_email = EmailField(
        "Email de l'expéditeur", validators=[DataRequired(), Email(), Length(max=200)]
    )
    admin_cc_email = EmailField(
        "Email administrateur en copie (CC)",
        validators=[Optional(), Email(), Length(max=200)],
    )
    submit = SubmitField("Enregistrer")
    test_recipient = EmailField(
        "Adresse de test", validators=[Optional(), Email(), Length(max=200)]
    )
    test = SubmitField("Envoyer un email de test")

    def validate_use_ssl(self, field):
        if field.data and self.use_tls.data:
            raise ValidationError(
                "Choisir SSL direct OU STARTTLS, pas les deux à la fois."
            )


class EmailTemplateForm(FlaskForm):
    subject = StringField(
        "Sujet de l'email", validators=[DataRequired(), Length(max=255)]
    )
    body_html = TextAreaField(
        "Corps HTML",
        validators=[DataRequired()],
        render_kw={"rows": 20, "style": "font-family: monospace;"},
    )
    submit = SubmitField("Enregistrer le modèle")
    restore = SubmitField("Restaurer le modèle par défaut")
    preview = SubmitField("Aperçu")
    test_recipient = EmailField(
        "Adresse de test", validators=[Optional(), Email(), Length(max=200)]
    )
    send_test = SubmitField("Envoyer un test")
