# main/serializers.py
from datetime import date, timedelta

from django.utils import timezone
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from .models import (
    Utilisateur,
    Entreprise,
    CV,
    Envoi,
    Offre,
    Competence,
    Langue,
    EntretienCreneau,
    Notification,
)
from .services.cv_ai_analyzer import analyze_cv_file



# ========================
# Mixin URL Cloudinary
# ========================
class CloudinaryUrlMixin:
    """
    Retourne l'URL publique d'un FileField/ImageField.
    Avec Cloudinary storage, .url retourne directement https://res.cloudinary.com/...
    """
    def _resolve_url(self, field_file):
        if not field_file:
            return None
        try:
            url = field_file.url
            if url.startswith('http://') or url.startswith('https://'):
                return url
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(url)
            return url
        except Exception:
            return None


# ========================
# Utilisateur (create/update)
# ========================
class UtilisateurSerializer(CloudinaryUrlMixin, serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})
    photo_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Utilisateur
        fields = [
            "id",
            "email",
            "username",
            "type",
            "nom",
            "prenom",
            "telephone",
            "dateNaissance",
            "photoProfil",
            "photo_url",
            "dateInscription",
            "password",
            "password_confirm",
        ]
        read_only_fields = ["id", "dateInscription", "photo_url"]
        extra_kwargs = {
            "photoProfil": {"required": False, "allow_null": True},
        }

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("L'email est obligatoire.")
        qs = Utilisateur.objects.filter(email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Cet email est déjà utilisé.")
        return value

    def validate_type(self, value):
        valid_types = ["invite", "candidat", "entreprise"]
        if value not in valid_types:
            raise serializers.ValidationError(f"Type invalide. Choix possibles : {', '.join(valid_types)}")
        return value

    def validate_telephone(self, value):
        if value:
            cleaned = "".join(filter(str.isdigit, value))
            if len(cleaned) < 9 or len(cleaned) > 15:
                raise serializers.ValidationError("Le numéro de téléphone doit contenir entre 9 et 15 chiffres.")
        return value

    def validate(self, data):
        if not self.instance:
            password = data.get("password")
            password_confirm = data.get("password_confirm")

            if not password:
                raise serializers.ValidationError({"password": "Le mot de passe est obligatoire."})

            if password != password_confirm:
                raise serializers.ValidationError({"password_confirm": "Les mots de passe ne correspondent pas."})

            try:
                validate_password(password)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"password": list(e.messages)})

        return data

    def get_photo_url(self, obj):
        return self._resolve_url(obj.photoProfil)
        return None

    def create(self, validated_data):
        validated_data.pop("password_confirm", None)
        password = validated_data.pop("password")

        user = Utilisateur(**validated_data)
        user.set_password(password)
        user.is_active = False
        user.save()

        from .services.email_service import EmailService
        EmailService.send_verification_email(user)

        return user

    def update(self, instance, validated_data):
        validated_data.pop("password_confirm", None)
        password = validated_data.pop("password", None)

        # Gestion de la photo
        photo = validated_data.pop("photoProfil", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if photo is not None:
            if photo:
                # Supprimer l'ancienne photo si elle existe
                if instance.photoProfil and instance.photoProfil != photo:
                    try:
                        instance.photoProfil.delete(save=False)
                    except Exception:
                        pass
                instance.photoProfil = photo
            else:
                # Supprimer la photo existante
                if instance.photoProfil:
                    try:
                        instance.photoProfil.delete(save=False)
                    except Exception:
                        pass
                    instance.photoProfil = None

        if password:
            try:
                validate_password(password, user=instance)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"password": list(e.messages)})
            instance.set_password(password)

        instance.save()
        return instance


class UtilisateurReadSerializer(CloudinaryUrlMixin, serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Utilisateur
        fields = [
            "id",
            "username",
            "email",
            "type",
            "nom",
            "prenom",
            "telephone",
            "dateNaissance",
            "photo_url",
            "dateInscription",
        ]
        read_only_fields = fields

    def get_photo_url(self, obj):
        return self._resolve_url(obj.photoProfil)
        return None


# ========================
# Entreprise
# ========================
class EntrepriseSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    user_type = serializers.CharField(source="user.type", read_only=True)

    class Meta:
        model = Entreprise
        fields = [
            "entrepriseId",
            "user",
            "nomEntreprise",
            "secteur",
            "ville",
            "pays",
            "recevoirCandidatures",
            "username",
            "email",
            "user_type",
        ]
        read_only_fields = ["entrepriseId", "user", "username", "email", "user_type"]
        extra_kwargs = {"nomEntreprise": {"required": True}}

    def validate_nomEntreprise(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Le nom de l'entreprise doit contenir au moins 2 caractères.")
        return value

    def validate(self, data):
        request = self.context.get("request")
        if not self.instance and request and request.user.is_authenticated:
            if request.user.type != "entreprise":
                raise serializers.ValidationError(
                    "Seuls les utilisateurs de type 'entreprise' peuvent avoir un profil entreprise."
                )
        return data


# ========================
# CV - Version Cloudinary
# ========================
class CVSerializer(CloudinaryUrlMixin, serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    fichier_url = serializers.SerializerMethodField()
    taille_fichier = serializers.SerializerMethodField()

    class Meta:
        model = CV
        fields = [
            "cvId",
            "user",
            "nom",
            "fichier",
            "fichier_url",
            "type",
            "dateCreation",
            "user_username",
            "taille_fichier",
            "ai_status",
            "ai_score",
            "ai_has_photo",
            "ai_notes",
            "ai_checked_at",
        ]
        read_only_fields = [
            "cvId",
            "dateCreation",
            "user",
            "user_username",
            "fichier_url",
            "taille_fichier",
            "ai_status",
            "ai_score",
            "ai_has_photo",
            "ai_notes",
            "ai_checked_at",
        ]
        extra_kwargs = {
            "nom": {"required": True},
            "type": {"required": True},
            "fichier": {"required": True},
        }

    def get_fichier_url(self, obj):
        return self._resolve_url(obj.fichier)
        return None

    def get_taille_fichier(self, obj):
        if obj.fichier and hasattr(obj.fichier, 'size'):
            try:
                size_mb = obj.fichier.size / (1024 * 1024)
                return round(size_mb, 2)
            except Exception:
                return None
        return None

    def validate_fichier(self, value):
        if not value:
            return value
        max_size = 10 * 1024 * 1024  # 10 MB
        if value.size > max_size:
            raise serializers.ValidationError("La taille du fichier ne doit pas dépasser 10 MB.")
        return value

    def validate(self, data):
        fichier = data.get("fichier") or (self.instance.fichier if self.instance else None)
        type_cv = data.get("type") or (self.instance.type if self.instance else None)
        incoming_file = data.get("fichier")

        valid_extensions = {
            "cv": [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".jfif"],
            "video": [".mp4", ".avi", ".mov", ".mkv"],
            "portfolio": [".pdf", ".zip", ".rar"],
        }

        if fichier and type_cv:
            file_extension = "." + fichier.name.split(".")[-1].lower()
            allowed = valid_extensions.get(type_cv, [])
            if allowed and file_extension not in allowed:
                raise serializers.ValidationError({
                    "fichier": (
                        f"Extension invalide pour le type '{type_cv}'. "
                        f"Extensions autorisées : {', '.join(allowed)}"
                    )
                })

        if incoming_file and type_cv == "cv":
            ai_result = analyze_cv_file(incoming_file)
            if not ai_result["is_valid"]:
                reasons = ai_result.get("reasons") or ["Le fichier ne ressemble pas a un CV professionnel."]
                raise serializers.ValidationError({
                    "fichier": "Analyse IA refusee: " + " ".join(reasons)
                })
            self._ai_result = ai_result

        return data

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["user"] = request.user
        ai_result = getattr(self, "_ai_result", None)
        if ai_result:
            validated_data["ai_status"] = "validated"
            validated_data["ai_score"] = ai_result["score"]
            validated_data["ai_has_photo"] = ai_result["has_photo"]
            validated_data["ai_notes"] = ai_result["notes"]
            validated_data["ai_checked_at"] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        fichier = validated_data.pop("fichier", None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if fichier is not None:
            if fichier:
                if instance.fichier and instance.fichier != fichier:
                    try:
                        instance.fichier.delete(save=False)
                    except Exception:
                        pass
                instance.fichier = fichier
        
        instance.save()
        return instance


class CVListSerializer(CloudinaryUrlMixin, serializers.ModelSerializer):
    fichier_url = serializers.SerializerMethodField()

    class Meta:
        model = CV
        fields = [
            "cvId",
            "nom",
            "type",
            "dateCreation",
            "ai_status",
            "ai_score",
            "ai_has_photo",
            "ai_notes",
            "ai_checked_at",
            "fichier_url",
        ]
        read_only_fields = fields

    def get_fichier_url(self, obj):
        return self._resolve_url(obj.fichier)
        return None


# ========================
# Compétences / Langues
# ========================
class CompetenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Competence
        fields = ["id", "nom"]
        read_only_fields = ["id"]


class LangueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Langue
        fields = ["id", "nom"]
        read_only_fields = ["id"]


# ========================
# Offre
# ========================
class OffreSerializer(serializers.ModelSerializer):
    entreprise_nom = serializers.CharField(source="entreprise.nomEntreprise", read_only=True)
    entreprise_id = serializers.IntegerField(source="entreprise.entrepriseId", read_only=True)

    competences = CompetenceSerializer(many=True, read_only=True)
    langues = LangueSerializer(many=True, read_only=True)

    competences_ids = serializers.PrimaryKeyRelatedField(
        queryset=Competence.objects.all(),
        many=True,
        write_only=True,
        required=False,
        source="competences",
    )
    langues_ids = serializers.PrimaryKeyRelatedField(
        queryset=Langue.objects.all(),
        many=True,
        write_only=True,
        required=False,
        source="langues",
    )

    class Meta:
        model = Offre
        fields = [
            "offreId",
            "entreprise",
            "entreprise_id",
            "entreprise_nom",
            "titre",
            "poste",
            "domaine",
            "specialite",
            "niveau",
            "type_contrat",
            "mode_travail",
            "experience_min",
            "experience_max",
            "etude_min",
            "salaire_min",
            "salaire_max",
            "devise",
            "description",
            "missions",
            "profil_recherche",
            "avantages",
            "tags",
            "ville",
            "pays",
            "relance_days",
            "recevoirCandidatures",
            "estArchivee",
            "dateLimite",
            "dateCreation",
            "competences",
            "langues",
            "competences_ids",
            "langues_ids",
        ]
        read_only_fields = ["offreId", "entreprise", "dateCreation", "entreprise_id", "entreprise_nom", "competences", "langues"]

    def validate(self, data):
        request = self.context.get("request")
        if not self.instance and request:
            if not request.user.is_authenticated or request.user.type != "entreprise":
                raise serializers.ValidationError("Seules les entreprises peuvent créer une offre.")
            data["entreprise"] = request.user.entreprise

        salaire_min = data.get("salaire_min")
        salaire_max = data.get("salaire_max")
        if salaire_min is not None and salaire_max is not None and salaire_min > salaire_max:
            raise serializers.ValidationError({"salaire_min": "Le salaire min ne peut pas dépasser le salaire max."})

        exp_min = data.get("experience_min")
        exp_max = data.get("experience_max")
        if exp_min is not None and exp_max is not None and exp_min > exp_max:
            raise serializers.ValidationError({"experience_min": "L'expérience min ne peut pas dépasser l'expérience max."})

        return data

    def create(self, validated_data):
        competences = validated_data.pop("competences", [])
        langues = validated_data.pop("langues", [])
        offre = Offre.objects.create(**validated_data)
        if competences:
            offre.competences.set(competences)
        if langues:
            offre.langues.set(langues)
        return offre

    def update(self, instance, validated_data):
        competences = validated_data.pop("competences", None)
        langues = validated_data.pop("langues", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if competences is not None:
            instance.competences.set(competences)
        if langues is not None:
            instance.langues.set(langues)
        return instance


class OffreListSerializer(serializers.ModelSerializer):
    entreprise_nom = serializers.CharField(source="entreprise.nomEntreprise", read_only=True)
    entreprise_id = serializers.IntegerField(source="entreprise.entrepriseId", read_only=True)

    class Meta:
        model = Offre
        fields = [
            "offreId",
            "titre",
            "poste",
            "domaine",
            "specialite",
            "type_contrat",
            "mode_travail",
            "niveau",
            "experience_min",
            "salaire_min",
            "etude_min",
            "tags",
            "relance_days",
            "ville",
            "pays",
            "recevoirCandidatures",
            "estArchivee",
            "entreprise_id",
            "entreprise_nom",
        ]
        read_only_fields = fields

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        identifier = attrs.get('username')
        password = attrs.get('password')
        
        if not identifier or not password:
            raise serializers.ValidationError('Identifiant et mot de passe requis.')
        
        user = None
        
        # Si c'est un email, chercher l'utilisateur par email
        if '@' in identifier:
            try:
                user_obj = Utilisateur.objects.get(email=identifier)
                user = authenticate(username=user_obj.username, password=password)
            except Utilisateur.DoesNotExist:
                pass
        
        # Sinon chercher par username
        if user is None:
            user = authenticate(username=identifier, password=password)
        
        if user is None:
            raise serializers.ValidationError('Identifiants invalides.')
        
        if not user.is_active:
            raise serializers.ValidationError('Ce compte est désactivé.')
        
        refresh = self.get_token(user)
        
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'type': user.type,
        }
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["email"] = user.email
        token["type"] = user.type
        token["user_id"] = user.id
        return token


# ========================
# Envoi (CV -> Offre)
# ========================
class EnvoiSerializer(CloudinaryUrlMixin, serializers.ModelSerializer):
    cv_nom = serializers.CharField(source="cv.nom", read_only=True)
    cv_type = serializers.CharField(source="cv.type", read_only=True)
    cv_fichier_url = serializers.SerializerMethodField()

    candidat_id = serializers.IntegerField(source="cv.user.id", read_only=True)
    candidat_nom = serializers.CharField(source="cv.user.nom", read_only=True)
    candidat_prenom = serializers.CharField(source="cv.user.prenom", read_only=True)
    candidat_email = serializers.EmailField(source="cv.user.email", read_only=True)
    candidat_telephone = serializers.CharField(source="cv.user.telephone", read_only=True)

    offre_titre = serializers.CharField(source="offre.titre", read_only=True)
    offre_poste = serializers.CharField(source="offre.poste", read_only=True)
    offre_domaine = serializers.CharField(source="offre.domaine", read_only=True)
    offre_specialite = serializers.CharField(source="offre.specialite", read_only=True)
    offre_ville = serializers.CharField(source="offre.ville", read_only=True)
    offre_pays = serializers.CharField(source="offre.pays", read_only=True)
    offre_type_contrat = serializers.CharField(source="offre.type_contrat", read_only=True)
    offre_mode_travail = serializers.CharField(source="offre.mode_travail", read_only=True)

    entreprise_nom = serializers.CharField(source="offre.entreprise.nomEntreprise", read_only=True)
    entreprise_id = serializers.IntegerField(source="offre.entreprise.entrepriseId", read_only=True)

    cv = serializers.PrimaryKeyRelatedField(queryset=CV.objects.all(), write_only=True)
    offre = serializers.PrimaryKeyRelatedField(queryset=Offre.objects.all(), write_only=True)

    statut = serializers.CharField(read_only=True)

    class Meta:
        model = Envoi
        fields = [
            "envoiId", "cv", "offre", "dateEnvoi", "statut",
            "cv_nom", "cv_type", "cv_fichier_url",
            "candidat_id", "candidat_nom", "candidat_prenom", "candidat_email", "candidat_telephone",
            "offre_titre", "offre_poste", "offre_domaine", "offre_specialite",
            "offre_type_contrat", "offre_mode_travail", "offre_ville", "offre_pays",
            "entreprise_id", "entreprise_nom",
        ]
        read_only_fields = ["envoiId", "dateEnvoi", "statut"]

    def get_cv_fichier_url(self, obj):
        return self._resolve_url(obj.cv.fichier if obj.cv else None)
        return None

    def validate_cv(self, value):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            if request.user.type != "candidat":
                raise serializers.ValidationError("Seuls les candidats peuvent envoyer des CVs.")
            if value.user != request.user:
                raise serializers.ValidationError("Vous ne pouvez envoyer que vos propres CVs.")
        return value

    def validate_offre(self, value):
        if not value.recevoirCandidatures:
            raise serializers.ValidationError("Cette offre ne reçoit pas de candidatures (bouton désactivé).")
        if not value.entreprise.recevoirCandidatures:
            raise serializers.ValidationError("L'entreprise de cette offre n'accepte pas de candidatures.")
        if bool(getattr(value, "estArchivee", False)):
            raise serializers.ValidationError("Cette offre est archivée.")
        return value

    def validate(self, data):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return data

        offre = data.get("offre")
        if not offre:
            return data

        delay_days = getattr(offre, "relance_days", 7) or 7

        last = (
            Envoi.objects
            .filter(cv__user=request.user, offre=offre)
            .order_by("-dateEnvoi")
            .first()
        )

        if last:
            allowed_at = last.dateEnvoi + timedelta(days=delay_days)
            if timezone.now() < allowed_at:
                raise serializers.ValidationError(
                    f"Vous avez déjà postulé à cette offre. "
                    f"Ré-envoi possible à partir du {allowed_at.strftime('%Y-%m-%d %H:%M')}."
                )

        return data

    def create(self, validated_data):
        validated_data["statut"] = "envoye"
        return Envoi.objects.create(**validated_data)


class EnvoiListSerializer(CloudinaryUrlMixin, serializers.ModelSerializer):
    cv_nom = serializers.CharField(source="cv.nom", read_only=True)
    cv_fichier_url = serializers.SerializerMethodField()
    offre_titre = serializers.CharField(source="offre.titre", read_only=True)
    offre_poste = serializers.CharField(source="offre.poste", read_only=True)
    offre_domaine = serializers.CharField(source="offre.domaine", read_only=True)
    offre_specialite = serializers.CharField(source="offre.specialite", read_only=True)
    offre_type_contrat = serializers.CharField(source="offre.type_contrat", read_only=True)
    offre_mode_travail = serializers.CharField(source="offre.mode_travail", read_only=True)
    offre_ville = serializers.CharField(source="offre.ville", read_only=True)
    offre_pays = serializers.CharField(source="offre.pays", read_only=True)
    entreprise_nom = serializers.CharField(source="offre.entreprise.nomEntreprise", read_only=True)
    candidat_nom = serializers.SerializerMethodField()
    creneaux = serializers.SerializerMethodField()

    class Meta:
        model = Envoi
        fields = [
            "envoiId",
            "cv_nom",
            "cv_fichier_url",
            "offre_titre",
            "offre_poste",
            "offre_domaine",
            "offre_specialite",
            "offre_type_contrat",
            "offre_mode_travail",
            "offre_ville",
            "offre_pays",
            "entreprise_nom",
            "candidat_nom",
            "creneaux",
            "dateEnvoi",
            "statut",
        ]
        read_only_fields = fields

    def get_cv_fichier_url(self, obj):
        return self._resolve_url(obj.cv.fichier if obj.cv else None)
        return None

    def get_candidat_nom(self, obj):
        user = obj.cv.user
        if user.nom and user.prenom:
            return f"{user.prenom} {user.nom}"
        return user.username

    def get_creneaux(self, obj):
        request = self.context.get("request")
        creneaux = obj.creneaux.all().order_by("startAt")
        return EntretienCreneauReadSerializer(creneaux, many=True, context={"request": request}).data


# ========================
# Entretien Créneau
# ========================
class EntretienCreneauCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntretienCreneau
        fields = ["creneauId", "startAt", "endAt", "mode", "lieuOuLien", "note"]
        read_only_fields = ["creneauId"]
        extra_kwargs = {
            "endAt": {"required": False, "allow_null": True},
        }

    def validate(self, data):
        start_at = data.get("startAt")
        end_at = data.get("endAt")
        if start_at and not end_at:
            data["endAt"] = start_at + timedelta(minutes=60)
            end_at = data["endAt"]
        if start_at and end_at and end_at <= start_at:
            raise serializers.ValidationError("Le creneau est invalide: heure de fin <= heure de debut.")
        return data


class EntretienCreneauReadSerializer(serializers.ModelSerializer):
    reserve_par_nom = serializers.SerializerMethodField()
    duree_minutes = serializers.SerializerMethodField()

    class Meta:
        model = EntretienCreneau
        fields = [
            "creneauId",
            "startAt",
            "endAt",
            "mode",
            "lieuOuLien",
            "note",
            "estReserve",
            "dateReservation",
            "reserve_par_nom",
            "duree_minutes",
        ]
        read_only_fields = fields

    def get_reserve_par_nom(self, obj):
        user = obj.reservePar
        if not user:
            return None
        if user.prenom and user.nom:
            return f"{user.prenom} {user.nom}"
        return user.username

    def get_duree_minutes(self, obj):
        delta = obj.endAt - obj.startAt
        return int(delta.total_seconds() // 60)


class EnvoiStatutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Envoi
        fields = ["statut"]

    def validate_statut(self, value):
        valid_statuts = ["envoye", "en_attente", "accepte", "refuse"]
        if value not in valid_statuts:
            raise serializers.ValidationError(f"Statut invalide. Choix : {', '.join(valid_statuts)}")
        return value


# ========================
# Notification
# ========================
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["notificationId", "titre", "message", "type", "lu", "lien", "dateCreation"]
        read_only_fields = fields