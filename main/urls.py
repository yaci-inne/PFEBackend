# main/urls.py
from django.urls import path
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

    
]
