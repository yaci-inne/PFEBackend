# main/serializers_auth.py - COMPLETE VERSION
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from .models import Utilisateur, Entreprise
from .services.email_service import EmailService


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    type = serializers.ChoiceField(choices=Utilisateur.TYPE_CHOICES, required=True)
    
    # Additional fields
    nom = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    prenom = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    telephone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    dateNaissance = serializers.DateField(required=False, allow_null=True)
    
    # Entreprise specific fields
    nomEntreprise = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    secteur = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ville = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    pays = serializers.CharField(required=False, default="Algérie")

    class Meta:
        model = Utilisateur
        fields = ('username', 'email', 'password', 'password2', 'type', 
                  'nom', 'prenom', 'telephone', 'dateNaissance',
                  'nomEntreprise', 'secteur', 'ville', 'pays')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password2": "Les mots de passe ne correspondent pas."})
        
        if Utilisateur.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({"email": "Cet email est déjà utilisé."})
        
        if Utilisateur.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError({"username": "Ce nom d'utilisateur est déjà pris."})
        
        return attrs

    def create(self, validated_data):
        # Extract entreprise fields
        nom_entreprise = validated_data.pop('nomEntreprise', None)
        secteur = validated_data.pop('secteur', None)
        ville_entreprise = validated_data.pop('ville', None)
        pays_entreprise = validated_data.pop('pays', 'Algérie')
        
        # Extract password2
        validated_data.pop('password2')
        
        # Get user type
        user_type = validated_data.pop('type', 'candidat')
        
        # Create user
        user = Utilisateur.objects.create_user(**validated_data)
        user.type = user_type
        user.is_active = False
        user.save()
        
        # Create Entreprise profile if user is an entreprise
        if user_type == 'entreprise':
            Entreprise.objects.create(
                user=user,
                nomEntreprise=nom_entreprise or validated_data.get('username', user.username),
                secteur=secteur,
                ville=ville_entreprise,
                pays=pays_entreprise,
                recevoirCandidatures=True,
            )
        
        # Send verification email
        try:
            EmailService.send_verification_email(user)
        except Exception as e:
            print(f"Email error: {e}")
        
        return user


class VerifyEmailSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    token = serializers.CharField()

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs['uidb64']))
            self.user = Utilisateur.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Utilisateur.DoesNotExist):
            raise serializers.ValidationError('Lien de vérification invalide.')
        
        if not default_token_generator.check_token(self.user, attrs['token']):
            raise serializers.ValidationError('Lien de vérification invalide ou expiré.')
        
        return attrs

    def save(self):
        if not self.user.is_active:
            self.user.is_active = True
            self.user.save()
        return self.user


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            self.user = Utilisateur.objects.get(email=value, is_active=True)
        except Utilisateur.DoesNotExist:
            pass
        return value

    def save(self):
        if hasattr(self, 'user'):
            try:
                EmailService.send_password_reset_email(self.user)
            except Exception as e:
                print(f"Password reset email error: {e}")


class ResetPasswordSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password2": "Les mots de passe ne correspondent pas."})
        
        try:
            uid = force_str(urlsafe_base64_decode(attrs['uidb64']))
            self.user = Utilisateur.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Utilisateur.DoesNotExist):
            raise serializers.ValidationError('Lien de réinitialisation invalide.')
        
        if not default_token_generator.check_token(self.user, attrs['token']):
            raise serializers.ValidationError('Lien de réinitialisation invalide ou expiré.')
        
        return attrs

    def save(self):
        self.user.set_password(self.validated_data['password'])
        self.user.save()
        return self.user