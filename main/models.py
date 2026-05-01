from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db.models.signals import post_save
from django.dispatch import receiver


# =========================
# User Manager
# =========================
class UtilisateurManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError("Username obligatoire")

        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.is_active = True
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(username, email, password, **extra_fields)


# =========================
# Utilisateur
# =========================
class Utilisateur(AbstractBaseUser, PermissionsMixin):
    TYPE_CHOICES = [
        ("invite", "Invité"),
        ("candidat", "Candidat"),
        ("entreprise", "Entreprise"),
    ]

    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)

    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="invite")

    nom = models.CharField(max_length=100, null=True, blank=True)
    prenom = models.CharField(max_length=100, null=True, blank=True)
    telephone = models.CharField(max_length=20, null=True, blank=True)
    dateNaissance = models.DateField(null=True, blank=True)

    photoProfil = models.ImageField(
        null=True,
        blank=True,
        # PAS de upload_to - Cloudinary gère automatiquement
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    dateInscription = models.DateTimeField(auto_now_add=True)

    objects = UtilisateurManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.username

    @property
    def photo_url(self):
        """Retourne l'URL Cloudinary de la photo."""
        if self.photoProfil:
            try:
                url = self.photoProfil.url
                # Si l'URL est déjà Cloudinary, la retourner
                if 'cloudinary.com' in url or 'res.cloudinary.com' in url:
                    return url
                # Sinon, reconstruire l'URL absolue
                from django.conf import settings
                backend_url = getattr(settings, 'BACKEND_URL', '')
                if backend_url and url.startswith('/'):
                    return f"{backend_url.rstrip('/')}{url}"
                return url
            except Exception:
                return ""
        return ""


# =========================
# Entreprise
# =========================
class Entreprise(models.Model):
    entrepriseId = models.AutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="entreprise")

    nomEntreprise = models.CharField(max_length=150)
    secteur = models.CharField(max_length=120, null=True, blank=True)

    ville = models.CharField(max_length=100, null=True, blank=True)
    pays = models.CharField(max_length=100, default="Algérie")

    recevoirCandidatures = models.BooleanField(default=True)

    def __str__(self):
        return self.nomEntreprise


@receiver(post_save, sender=Utilisateur)
def create_entreprise(sender, instance, created, **kwargs):
    if created and instance.type == "entreprise":
        Entreprise.objects.create(
            user=instance,
            nomEntreprise=instance.username,
            ville=None,
            pays="Algérie",
        )


# =========================
# CV
# =========================
class CV(models.Model):
    TYPE_CHOICES = [
        ("cv", "CV"),
        ("video", "Vidéo"),
        ("portfolio", "Portfolio"),
    ]
    AI_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("validated", "Validated"),
        ("rejected", "Rejected"),
    ]

    cvId = models.AutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cvs")

    nom = models.CharField(max_length=100)
    fichier = models.FileField(
        null=True,
        blank=True,
        # PAS de upload_to
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="cv")
    estSupprime = models.BooleanField(default=False)
    ai_status = models.CharField(max_length=20, choices=AI_STATUS_CHOICES, default="pending")
    ai_score = models.PositiveSmallIntegerField(default=0)
    ai_has_photo = models.BooleanField(default=False)
    ai_notes = models.TextField(blank=True, default="")
    ai_checked_at = models.DateTimeField(null=True, blank=True)

    dateCreation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nom


# =========================
# Competence / Langue
# =========================
class Competence(models.Model):
    nom = models.CharField(max_length=80, unique=True)

    def __str__(self):
        return self.nom


class Langue(models.Model):
    nom = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.nom


# =========================
# Offre
# =========================
class Offre(models.Model):
    TYPE_CONTRAT_CHOICES = [
        ("cdi", "CDI"),
        ("cdd", "CDD"),
        ("stage", "Stage"),
        ("freelance", "Freelance"),
        ("alternance", "Alternance"),
    ]

    MODE_TRAVAIL_CHOICES = [
        ("site", "Sur site"),
        ("hybride", "Hybride"),
        ("remote", "Remote"),
    ]

    NIVEAU_CHOICES = [
        ("junior", "Junior"),
        ("intermediaire", "Intermédiaire"),
        ("senior", "Senior"),
        ("lead", "Lead"),
        ("manager", "Manager"),
    ]

    ETUDE_CHOICES = [
        ("aucun", "Aucun"),
        ("bac", "Bac"),
        ("licence", "Licence"),
        ("master", "Master"),
        ("doctorat", "Doctorat"),
    ]

    offreId = models.AutoField(primary_key=True)
    entreprise = models.ForeignKey(Entreprise, on_delete=models.CASCADE, related_name="offres")

    titre = models.CharField(max_length=150)
    poste = models.CharField(max_length=150, null=True, blank=True)

    domaine = models.CharField(max_length=120)
    specialite = models.CharField(max_length=120, null=True, blank=True)

    niveau = models.CharField(max_length=30, choices=NIVEAU_CHOICES, null=True, blank=True)
    type_contrat = models.CharField(max_length=20, choices=TYPE_CONTRAT_CHOICES)
    mode_travail = models.CharField(max_length=20, choices=MODE_TRAVAIL_CHOICES)

    experience_min = models.PositiveIntegerField(null=True, blank=True)
    experience_max = models.PositiveIntegerField(null=True, blank=True)

    etude_min = models.CharField(max_length=20, choices=ETUDE_CHOICES, default="aucun")
    salaire_min = models.PositiveIntegerField(null=True, blank=True)
    salaire_max = models.PositiveIntegerField(null=True, blank=True)
    devise = models.CharField(max_length=10, default="DZD")

    description = models.TextField(null=True, blank=True)
    missions = models.TextField(null=True, blank=True)
    profil_recherche = models.TextField(null=True, blank=True)
    avantages = models.TextField(null=True, blank=True)

    tags = models.CharField(max_length=255, null=True, blank=True)

    competences = models.ManyToManyField(Competence, blank=True)
    langues = models.ManyToManyField(Langue, blank=True)

    ville = models.CharField(max_length=100, null=True, blank=True)
    pays = models.CharField(max_length=100, default="Algérie")

    relance_days = models.PositiveIntegerField(default=7)

    recevoirCandidatures = models.BooleanField(default=False)
    estArchivee = models.BooleanField(default=False)

    dateLimite = models.DateField(null=True, blank=True)
    dateCreation = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["domaine"]),
            models.Index(fields=["specialite"]),
            models.Index(fields=["ville"]),
            models.Index(fields=["pays"]),
            models.Index(fields=["type_contrat"]),
            models.Index(fields=["mode_travail"]),
            models.Index(fields=["niveau"]),
            models.Index(fields=["recevoirCandidatures", "estArchivee"]),
        ]

    def __str__(self):
        return f"{self.titre} - {self.entreprise.nomEntreprise}"


# =========================
# Envoi (CV → Offre)
# =========================
class Envoi(models.Model):
    STATUT_CHOICES = [
        ("envoye", "Envoyé"),
        ("en_attente", "En attente"),
        ("accepte", "Accepté"),
        ("refuse", "Refusé"),
    ]

    envoiId = models.AutoField(primary_key=True)
    cv = models.ForeignKey(CV, on_delete=models.CASCADE, related_name="envois")
    offre = models.ForeignKey(Offre, on_delete=models.CASCADE, related_name="envois")

    entreprise_nom_snapshot = models.CharField(max_length=150, null=True, blank=True)
    offre_titre_snapshot = models.CharField(max_length=150, null=True, blank=True)
    offre_domaine_snapshot = models.CharField(max_length=120, null=True, blank=True)
    offre_ville_snapshot = models.CharField(max_length=100, null=True, blank=True)
    offre_pays_snapshot = models.CharField(max_length=100, null=True, blank=True)

    dateEnvoi = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="envoye")

    class Meta:
        indexes = [
            models.Index(fields=["dateEnvoi"]),
            models.Index(fields=["statut"]),
            models.Index(fields=["cv", "offre", "dateEnvoi"]),
        ]

    def save(self, *args, **kwargs):
        if not self.pk and self.offre_id:
            self.entreprise_nom_snapshot = self.offre.entreprise.nomEntreprise
            self.offre_titre_snapshot = self.offre.titre
            self.offre_domaine_snapshot = self.offre.domaine
            self.offre_ville_snapshot = self.offre.ville
            self.offre_pays_snapshot = self.offre.pays
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cv.nom} → {self.offre.titre}"


# =========================
# EntretienCreneau
# =========================
class EntretienCreneau(models.Model):
    MODE_CHOICES = [
        ("visio", "Visio"),
        ("site", "Sur site"),
    ]

    creneauId = models.AutoField(primary_key=True)
    envoi = models.ForeignKey(Envoi, on_delete=models.CASCADE, related_name="creneaux")
    startAt = models.DateTimeField()
    endAt = models.DateTimeField()
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="visio")
    lieuOuLien = models.CharField(max_length=255, blank=True, default="")
    note = models.TextField(blank=True, default="")

    estReserve = models.BooleanField(default=False)
    reservePar = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entretiens_reserves",
    )
    dateReservation = models.DateTimeField(null=True, blank=True)
    dateCreation = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["startAt"]),
            models.Index(fields=["estReserve"]),
            models.Index(fields=["envoi", "startAt"]),
        ]

    def __str__(self):
        return f"Entretien #{self.creneauId} - Envoi {self.envoi_id}"