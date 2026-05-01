# main/urls.py
from django.urls import path
from .views_auth import (
    RegisterView,
    VerifyEmailView,
    ForgotPasswordView,
    ResetPasswordView
)
from .views import (
    # Utilisateur
    UtilisateurListCreate,
    UtilisateurDetail,

    # Entreprise
    EntrepriseListCreate,
    EntrepriseDetail,

    # CV
    CVListCreate,
    CVDetail,

    # Offres
    OffreList,
    OffreEntrepriseListCreate,
    OffreDetail,
    OffreToggleRecevoir,

    # Envoi
    EnvoiListCreate,
    EnvoiDetail,
    EntretienCreneauListCreate,
    EntretienCreneauReserve,
    EntretienMeetingInfo,

    # Statistiques
    DashboardStats,EntretienCreneauAnnuler
)
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from main.models import Utilisateur, CV
def cleanup(request):
    if request.GET.get("key") != "clean2026":
        return JsonResponse({"error": "403"}, status=403)
    apply = request.GET.get("apply") == "true"
    photos, cvs = [], []
    for u in Utilisateur.objects.exclude(photoProfil="").exclude(photoProfil=None):
        val = str(u.photoProfil)
        if "cloudinary.com" not in val:
            photos.append(u.username)
            if apply:
                u.photoProfil = None
                u.save(update_fields=["photoProfil"])
    for c in CV.objects.exclude(fichier="").exclude(fichier=None):
        val = str(c.fichier)
        if "cloudinary.com" not in val:
            cvs.append(c.cvId)
            if apply:
                c.fichier = None
                c.save(update_fields=["fichier"])
    return JsonResponse({"photos": photos, "cvs": cvs, "applied": apply})

# Dans urlpatterns :

app_name = "main"

urlpatterns = [
    # ==========================
    # Utilisateurs
    # ==========================
    path("utilisateurs/", UtilisateurListCreate.as_view(), name="utilisateur-list-create"),
    path("utilisateurs/<int:pk>/", UtilisateurDetail.as_view(), name="utilisateur-detail"),

    # ==========================
    # Entreprises
    # ==========================
    path("entreprises/", EntrepriseListCreate.as_view(), name="entreprise-list-create"),
    path("entreprises/<int:pk>/", EntrepriseDetail.as_view(), name="entreprise-detail"),

    # ==========================
    # CVs
    # ==========================
    path("cvs/", CVListCreate.as_view(), name="cv-list-create"),
    path("cvs/<int:pk>/", CVDetail.as_view(), name="cv-detail"),

    # ==========================
    # Offres
    # ==========================
    # Public (candidats): listes + filtres query params
    path("offres/", OffreList.as_view(), name="offre-list"),
    # Entreprise: mes offres (GET) + créer (POST)
    path("entreprise/offres/", OffreEntrepriseListCreate.as_view(), name="offre-entreprise-list-create"),
    # Détails / update / archive
    path("offres/<int:pk>/", OffreDetail.as_view(), name="offre-detail"),
    # Toggle bouton recevoir candidatures
    path("offres/<int:pk>/toggle-recevoir/", OffreToggleRecevoir.as_view(), name="offre-toggle-recevoir"),

    # ==========================
    # Envois (Candidatures)
    # ==========================
    path("envois/", EnvoiListCreate.as_view(), name="envoi-list-create"),
    path("envois/<int:pk>/", EnvoiDetail.as_view(), name="envoi-detail"),
    path("envois/<int:envoi_id>/creneaux/", EntretienCreneauListCreate.as_view(), name="entretien-creneau-list-create"),
    path("creneaux/<int:creneau_id>/reserver/", EntretienCreneauReserve.as_view(), name="entretien-creneau-reserver"),
    path("creneaux/<int:creneau_id>/meeting/", EntretienMeetingInfo.as_view(), name="entretien-meeting-info"),

    # ==========================
    # Dashboard Stats
    # ==========================
    path("dashboard/stats/", DashboardStats.as_view(), name="dashboard-stats"),
    path("creneaux/<int:creneau_id>/annuler/", EntretienCreneauAnnuler.as_view(), name="entretien-creneau-annuler"),
    # ==========================
    # Authentication with Email
    # ==========================
    path("api/auth/register/", RegisterView.as_view(), name="auth-register"),
    path("api/auth/verify-email/", VerifyEmailView.as_view(), name="auth-verify-email"),
    path("api/auth/forgot-password/", ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("api/auth/reset-password/", ResetPasswordView.as_view(), name="auth-reset-password"),
    path("cleanup/", cleanup),
]
