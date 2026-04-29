# main/services/email_service.py
import threading
import requests
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.utils.html import strip_tags


def _send_brevo_email(subject, html_message, from_email, recipient_email, plain_message):
    try:
        print(f"[EmailService] Sending email to {recipient_email} via Brevo API")
        api_key = getattr(settings, 'BREVO_API_KEY', '')

        response = requests.post(
            'https://api.brevo.com/v3/smtp/email',
            headers={
                'api-key': api_key,
                'Content-Type': 'application/json',
            },
            json={
                'sender': {'name': 'AutoCandidature', 'email': from_email},
                'to': [{'email': recipient_email}],
                'subject': subject,
                'htmlContent': html_message,
                'textContent': plain_message,
            },
            timeout=15,
        )

        if response.status_code == 201:
            print(f"[EmailService] Email sent successfully to {recipient_email}")
        else:
            print(f"[EmailService] Brevo error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[EmailService] Failed to send email: {type(e).__name__}: {e}")


class EmailService:
    @staticmethod
    def send_verification_email(user, request=None):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        verification_link = f"{frontend_url}/verify-email/{uid}/{token}/"

        subject = 'Vérifiez votre adresse email'

        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background-color: #f9fafb; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #4F46E5; color: white;
                          text-decoration: none; border-radius: 8px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #6b7280; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Bienvenue sur AutoCandidature</h2>
                </div>
                <div class="content">
                    <p>Bonjour {user.username},</p>
                    <p>Merci de vous être inscrit ! Pour activer votre compte, veuillez vérifier votre adresse email en cliquant sur le bouton ci-dessous :</p>
                    <div style="text-align: center;">
                        <a href="{verification_link}" class="button">Vérifier mon email</a>
                    </div>
                    <p>Si le bouton ne fonctionne pas, copiez et collez ce lien dans votre navigateur :</p>
                    <p><a href="{verification_link}">{verification_link}</a></p>
                    <p>Ce lien expirera dans 3 jours.</p>
                    <p>Si vous n'avez pas créé de compte, ignorez simplement cet email.</p>
                </div>
                <div class="footer">
                    <p>© 2024 AutoCandidature - Tous droits réservés</p>
                </div>
            </div>
        </body>
        </html>
        """

        plain_message = strip_tags(html_message)
        from_email = getattr(settings, 'EMAIL_HOST_USER', 'noreply@autocandidature.com')

        t = threading.Thread(
            target=_send_brevo_email,
            args=(subject, html_message, from_email, user.email, plain_message)
        )
        t.daemon = True
        t.start()

    @staticmethod
    def send_password_reset_email(user, request=None):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        reset_link = f"{frontend_url}/reset-password/{uid}/{token}/"

        subject = 'Réinitialisation de votre mot de passe'

        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background-color: #f9fafb; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #4F46E5; color: white;
                          text-decoration: none; border-radius: 8px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #6b7280; }}
                .warning {{ background-color: #fef3c7; padding: 15px; border-radius: 8px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Réinitialisation du mot de passe</h2>
                </div>
                <div class="content">
                    <p>Bonjour {user.username},</p>
                    <p>Vous avez demandé la réinitialisation de votre mot de passe. Cliquez sur le bouton ci-dessous pour créer un nouveau mot de passe :</p>
                    <div style="text-align: center;">
                        <a href="{reset_link}" class="button">Réinitialiser mon mot de passe</a>
                    </div>
                    <p>Si le bouton ne fonctionne pas, copiez et collez ce lien dans votre navigateur :</p>
                    <p><a href="{reset_link}">{reset_link}</a></p>
                    <div class="warning">
                        <p><strong>⚠️ Attention :</strong> Ce lien expirera dans 3 jours. Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.</p>
                    </div>
                </div>
                <div class="footer">
                    <p>© 2024 AutoCandidature - Tous droits réservés</p>
                </div>
            </div>
        </body>
        </html>
        """

        plain_message = strip_tags(html_message)
        from_email = getattr(settings, 'EMAIL_HOST_USER', 'noreply@autocandidature.com')

        t = threading.Thread(
            target=_send_brevo_email,
            args=(subject, html_message, from_email, user.email, plain_message)
        )
        t.daemon = True
        t.start()