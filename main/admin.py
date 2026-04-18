# main/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    Utilisateur,
    Entreprise,
    CV,
    Competence,
    Langue,
    Offre,
    Envoi,
)


# =========================
# Utilisateur
# =========================
@admin.register(Utilisateur)
class UtilisateurAdmin(DjangoUserAdmin):
    # ✅ IMPORTANT: dateInscription est non-editable -> mettre en readonly_fields
    readonly_fields = ("dateInscription", "last_login")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informations personnelles", {"fields": (
            "username", "type", "nom", "prenom",
            "telephone", "dateNaissance", "photoProfil",
        )}),
        ("Permissions", {"fields": (
            "is_active", "is_staff", "is_superuser", "groups", "user_permissions"
        )}),
        # ✅ dateInscription retiré des fields (non-editable)
        ("Dates importantes", {"fields": ("last_login",)}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email", "username", "password1", "password2", "type",
                "nom", "prenom", "telephone", "dateNaissance", "photoProfil",
            ),
        }),
    )

    list_display = ("email", "username", "type", "is_staff", "is_active", "dateInscription")
    list_filter = ("type", "is_staff", "is_active")
    search_fields = ("email", "username", "nom", "prenom", "telephone")
    ordering = ("email",)
    filter_horizontal = ("groups", "user_permissions")


# =========================
# Entreprise
# =========================
@admin.register(Entreprise)
class EntrepriseAdmin(admin.ModelAdmin):
    list_display = (
        "entrepriseId", "nomEntreprise", "secteur", "ville",
        "pays", "recevoirCandidatures"
    )
    list_filter = ("secteur", "ville", "pays", "recevoirCandidatures")
    search_fields = ("nomEntreprise", "secteur", "ville", "pays", "user__email", "user__username")
    readonly_fields = ("entrepriseId",)
    ordering = ("nomEntreprise",)


# =========================
# CV
# =========================
@admin.register(CV)
class CVAdmin(admin.ModelAdmin):
    list_display = ("cvId", "nom", "user", "dateCreation")
    list_filter = ("dateCreation",)
    search_fields = ("nom", "user__username", "user__email")
    readonly_fields = ("cvId", "dateCreation")
    ordering = ("-dateCreation",)


# =========================
# Competence / Langue
# =========================
@admin.register(Competence)
class CompetenceAdmin(admin.ModelAdmin):
    list_display = ("id", "nom")
    search_fields = ("nom",)
    ordering = ("nom",)


@admin.register(Langue)
class LangueAdmin(admin.ModelAdmin):
    list_display = ("id", "nom")
    search_fields = ("nom",)
    ordering = ("nom",)


# =========================
# Offre
# =========================
@admin.register(Offre)
class OffreAdmin(admin.ModelAdmin):
    list_display = (
        "offreId",
        "titre",
        "get_entreprise",
        "domaine",
        "specialite",
        "type_contrat",
        "mode_travail",
        "ville",
        "pays",
        "recevoirCandidatures",
        
        "dateCreation",
    )

    list_filter = (
        "type_contrat",
        "mode_travail",
        "domaine",
        "specialite",
        "ville",
        "pays",
        "recevoirCandidatures",
       
        "dateCreation",
    )

    search_fields = (
        "titre",
        "domaine",
        "specialite",
        "ville",
        "pays",
        "entreprise__nomEntreprise",
        "entreprise__user__email",
    )

    readonly_fields = ("offreId", "dateCreation")

    fieldsets = (
        ("Entreprise", {"fields": ("entreprise",)}),
        ("Détails de l'offre", {"fields": (
            "titre", "domaine", "specialite",
            "type_contrat", "mode_travail",
        )}),
        ("Compétences & langues", {"fields": ("competences", "langues")}),
        ("Localisation", {"fields": ("ville", "pays")}),
        ("Paramètres", {"fields": ("recevoirCandidatures",)}),
        ("Dates", {"fields": ("dateCreation",)}),
    )

    filter_horizontal = ("competences", "langues")
    ordering = ("-dateCreation",)

    def get_entreprise(self, obj):
        return obj.entreprise.nomEntreprise if obj.entreprise else "-"
    get_entreprise.short_description = "Entreprise"


# =========================
# Envoi (CV -> Offre)
# =========================
@admin.register(Envoi)
class EnvoiAdmin(admin.ModelAdmin):
    list_display = (
        "envoiId",
        "get_cv_nom",
        "get_candidat",
        "get_offre",
        "get_entreprise",
        "get_domaine",
        "get_specialite",
        "get_ville",
        "statut",
        "dateEnvoi",
    )

    list_filter = (
        "statut",
        "dateEnvoi",
        "offre__domaine",
        "offre__specialite",
        "offre__type_contrat",
        "offre__mode_travail",
        "offre__ville",
        "offre__pays",
        "offre__recevoirCandidatures",
        
    )

    search_fields = (
        "cv__nom",
        "cv__user__username",
        "cv__user__email",
        "offre__titre",
        "offre__domaine",
        "offre__specialite",
        "offre__ville",
        "offre__entreprise__nomEntreprise",
    )

    fieldsets = (
        ("Envoi", {"fields": ("cv", "offre", "statut")}),
        ("Dates", {"fields": ("dateEnvoi",)}),
    )

    readonly_fields = ("envoiId", "dateEnvoi")
    ordering = ("-dateEnvoi",)

    def get_cv_nom(self, obj):
        return obj.cv.nom if obj.cv else "-"
    get_cv_nom.short_description = "CV"

    def get_candidat(self, obj):
        if obj.cv and obj.cv.user:
            u = obj.cv.user
            if u.prenom and u.nom:
                return f"{u.prenom} {u.nom}"
            return u.username
        return "-"
    get_candidat.short_description = "Candidat"

    def get_offre(self, obj):
        return obj.offre.titre if obj.offre else "-"
    get_offre.short_description = "Offre"

    def get_entreprise(self, obj):
        if obj.offre and obj.offre.entreprise:
            return obj.offre.entreprise.nomEntreprise
        return "-"
    get_entreprise.short_description = "Entreprise"

    def get_domaine(self, obj):
        return obj.offre.domaine if obj.offre else "-"
    get_domaine.short_description = "Domaine"

    def get_specialite(self, obj):
        return obj.offre.specialite if obj.offre else "-"
    get_specialite.short_description = "Spécialité"

    def get_ville(self, obj):
        return obj.offre.ville if obj.offre else "-"
    get_ville.short_description = "Ville"
