# main/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework_simplejwt.views import TokenObtainPairView

from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .models import Utilisateur, Entreprise, CV, Envoi, Offre, EntretienCreneau, Notification
from .services.cv_ai_analyzer import analyze_cv_file
from .serializers import (
    UtilisateurSerializer,
    UtilisateurReadSerializer,
    EntrepriseSerializer,
    CVSerializer,
    CVListSerializer,
    OffreSerializer,
    OffreListSerializer,
    EnvoiSerializer,
    EnvoiListSerializer,
    EnvoiStatutSerializer,
    EntretienCreneauCreateSerializer,
    EntretienCreneauReadSerializer,
    CustomTokenObtainPairSerializer,
    NotificationSerializer,
)

from rest_framework import viewsets
# ==========================
# Custom Permissions
# ==========================
class IsEntreprise(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.type == "entreprise"


class IsCandidat(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.type == "candidat"


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# ==========================
# Utilisateur APIView
# ==========================
class UtilisateurListCreate(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    def get(self, request):
        utilisateurs = Utilisateur.objects.all().order_by("-dateInscription")
        serializer = UtilisateurReadSerializer(utilisateurs, many=True, context={"request": request})
        return Response({"count": utilisateurs.count(), "utilisateurs": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = UtilisateurSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            try:
                user = serializer.save()
                return Response(
                    {
                        "message": "Inscription réussie",
                        "user": UtilisateurReadSerializer(user, context={"request": request}).data,
                    },
                    status=status.HTTP_201_CREATED,
                )
            except IntegrityError:
                return Response(
                    {"error": "Erreur d'intégrité", "details": "Username ou email déjà utilisé"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as e:
                return Response(
                    {"error": "Erreur création", "details": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response({"error": "Données invalides", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class UtilisateurDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self, pk, request):
        user = get_object_or_404(Utilisateur, pk=pk)
        if user != request.user and not request.user.is_staff:
            raise PermissionDenied("Vous ne pouvez accéder qu'à votre propre profil")
        return user

    def get(self, request, pk):
        user = self.get_object(pk, request)
        return Response(
            UtilisateurReadSerializer(user, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    def put(self, request, pk):
        user = self.get_object(pk, request)
        serializer = UtilisateurSerializer(user, data=request.data, partial=False, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Profil mis à jour",
                    "user": UtilisateurReadSerializer(user, context={"request": request}).data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        user = self.get_object(pk, request)

        # ── Gestion suppression photo ──────────────────────────────────────
        # Le frontend envoie photoProfil="" SANS fichier dans request.FILES.
        # Si un vrai fichier est présent dans request.FILES, c'est un upload
        # → on NE doit PAS supprimer.
        has_real_file = "photoProfil" in request.FILES
        raw_photo = request.data.get("photoProfil", None)

        if not has_real_file and (raw_photo == "" or raw_photo == "null"):
            if user.photoProfil:
                user.photoProfil.delete(save=False)
                user.photoProfil = None
                user.save(update_fields=["photoProfil"])
            return Response(
                {
                    "message": "Photo supprimée avec succès.",
                    "user": UtilisateurReadSerializer(user, context={"request": request}).data,
                },
                status=status.HTTP_200_OK,
            )

        # ── Mise à jour normale (champs texte + éventuelle nouvelle photo) ──
        serializer = UtilisateurSerializer(user, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            user.refresh_from_db()
            return Response(
                {
                    "message": "Profil mis à jour",
                    "user": UtilisateurReadSerializer(user, context={"request": request}).data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    def delete(self, request, pk):
        user = self.get_object(pk, request)
        user.is_active = False
        user.save()
        return Response({"message": "Compte désactivé"}, status=status.HTTP_200_OK)


# ==========================
# Entreprise APIView
# ==========================
class EntrepriseListCreate(APIView):

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get(self, request):
        entreprises = (
            Entreprise.objects
            .filter(recevoirCandidatures=True)
            .select_related("user")
            .order_by("nomEntreprise")
        )
        serializer = EntrepriseSerializer(entreprises, many=True, context={"request": request})
        return Response({"count": entreprises.count(), "entreprises": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        if request.user.type != "entreprise":
            return Response({"error": "Action réservée aux entreprises"}, status=status.HTTP_403_FORBIDDEN)

        try:
            entreprise = Entreprise.objects.get(user=request.user)
            serializer = EntrepriseSerializer(entreprise, data=request.data, partial=True, context={"request": request})
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {"message": "Profil entreprise mis à jour", "entreprise": serializer.data},
                    status=status.HTTP_200_OK,
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Entreprise.DoesNotExist:
            serializer = EntrepriseSerializer(data=request.data, context={"request": request})
            if serializer.is_valid():
                entreprise = serializer.save(user=request.user)
                return Response(
                    {"message": "Profil entreprise créé", "entreprise": serializer.data},
                    status=status.HTTP_201_CREATED,
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EntrepriseDetail(APIView):

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_object(self, pk):
        return get_object_or_404(Entreprise, pk=pk)

    def get(self, request, pk):
        entreprise = self.get_object(pk)
        return Response(EntrepriseSerializer(entreprise, context={"request": request}).data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        entreprise = self.get_object(pk)
        if entreprise.user != request.user:
            raise PermissionDenied("Vous ne pouvez modifier que votre propre entreprise")
        serializer = EntrepriseSerializer(entreprise, data=request.data, partial=False, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Entreprise mise à jour", "entreprise": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        entreprise = self.get_object(pk)
        if entreprise.user != request.user:
            raise PermissionDenied("Vous ne pouvez modifier que votre propre entreprise")
        serializer = EntrepriseSerializer(entreprise, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Entreprise mise à jour", "entreprise": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        entreprise = self.get_object(pk)
        if entreprise.user != request.user:
            raise PermissionDenied("Vous ne pouvez désactiver que votre propre entreprise")
        entreprise.recevoirCandidatures = False
        entreprise.save()
        return Response({"message": "Entreprise désactivée (ne reçoit plus)"}, status=status.HTTP_200_OK)


# ==========================
# CV APIView
# ==========================
class CVListCreate(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCandidat]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        cvs = CV.objects.filter(user=request.user, estSupprime=False).order_by("-dateCreation")
        return Response(
            {"count": cvs.count(), "cvs": CVListSerializer(cvs, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = CVSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            cv = serializer.save()
            return Response(
                {"message": "CV créé", "cv": CVSerializer(cv, context={"request": request}).data},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CVDetail(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCandidat]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self, pk, request):
        return get_object_or_404(CV, pk=pk, user=request.user, estSupprime=False)

    def get(self, request, pk):
        cv = self.get_object(pk, request)
        return Response(CVSerializer(cv, context={"request": request}).data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        cv = self.get_object(pk, request)
        serializer = CVSerializer(cv, data=request.data, partial=False, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "CV mis à jour", "cv": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        cv = self.get_object(pk, request)
        serializer = CVSerializer(cv, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "CV mis à jour", "cv": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        cv = self.get_object(pk, request)
        cv_nom = cv.nom
        cv.estSupprime = True
        cv.save(update_fields=["estSupprime"])
        return Response({"message": f'CV "{cv_nom}" supprimé'}, status=status.HTTP_200_OK)


# ==========================
# OFFRES APIViews
# ==========================
class OffreList(APIView):

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get(self, request):
        qs = Offre.objects.filter(
            recevoirCandidatures=True,
            estArchivee=False,
            entreprise__recevoirCandidatures=True,
        ).select_related("entreprise")

        domaine = request.query_params.get("domaine")
        specialite = request.query_params.get("specialite")
        ville = request.query_params.get("ville")
        pays = request.query_params.get("pays")
        type_contrat = request.query_params.get("type_contrat")
        mode_travail = request.query_params.get("mode_travail")
        q = request.query_params.get("q")

        if domaine:
            qs = qs.filter(domaine__icontains=domaine)
        if specialite:
            qs = qs.filter(specialite__icontains=specialite)
        if ville:
            qs = qs.filter(ville__icontains=ville)
        if pays:
            qs = qs.filter(pays__icontains=pays)
        if type_contrat:
            qs = qs.filter(type_contrat=type_contrat)
        if mode_travail:
            qs = qs.filter(mode_travail=mode_travail)
        if q:
            qs = qs.filter(
                Q(titre__icontains=q) |
                Q(poste__icontains=q) |
                Q(description__icontains=q) |
                Q(missions__icontains=q) |
                Q(profil_recherche__icontains=q) |
                Q(tags__icontains=q)
            )

        qs = qs.order_by("-dateCreation")
        serializer = OffreListSerializer(qs, many=True, context={"request": request})
        return Response({"count": qs.count(), "offres": serializer.data}, status=status.HTTP_200_OK)


class OffreEntrepriseListCreate(APIView):
    permission_classes = [permissions.IsAuthenticated, IsEntreprise]

    def get(self, request):
        qs = Offre.objects.filter(entreprise=request.user.entreprise).order_by("-dateCreation")
        serializer = OffreSerializer(qs, many=True, context={"request": request})
        return Response({"count": qs.count(), "offres": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = OffreSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            offre = serializer.save()
            return Response(
                {"message": "Offre créée", "offre": OffreSerializer(offre, context={"request": request}).data},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OffreDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(Offre.objects.select_related("entreprise"), pk=pk)

    def _must_own(self, request, offre):
        if request.user.type != "entreprise":
            raise PermissionDenied("Réservé aux entreprises")
        if offre.entreprise != request.user.entreprise:
            raise PermissionDenied("Vous ne pouvez modifier que vos offres")

    def _is_visible_to_candidates(self, offre):
        return (
            offre.recevoirCandidatures
            and not offre.estArchivee
            and offre.entreprise.recevoirCandidatures
        )

    def get(self, request, pk):
        offre = self.get_object(pk)
        if request.user.type == "entreprise" and hasattr(request.user, "entreprise"):
            if offre.entreprise == request.user.entreprise:
                return Response(OffreSerializer(offre, context={"request": request}).data, status=status.HTTP_200_OK)
        if not self._is_visible_to_candidates(offre):
            raise PermissionDenied("Offre non accessible.")
        return Response(OffreSerializer(offre, context={"request": request}).data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        offre = self.get_object(pk)
        self._must_own(request, offre)
        serializer = OffreSerializer(offre, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Offre mise à jour", "offre": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        offre = self.get_object(pk)
        self._must_own(request, offre)
        serializer = OffreSerializer(offre, data=request.data, partial=False, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Offre mise à jour", "offre": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        offre = self.get_object(pk)
        self._must_own(request, offre)
        offre.estArchivee = True
        offre.recevoirCandidatures = False
        offre.save()
        return Response({"message": "Offre archivée"}, status=status.HTTP_200_OK)


class OffreToggleRecevoir(APIView):
    permission_classes = [permissions.IsAuthenticated, IsEntreprise]

    def _parse_bool(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ["true", "1", "yes", "on"]:
                return True
            if v in ["false", "0", "no", "off"]:
                return False
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        raise ValidationError({"recevoirCandidatures": "Valeur invalide (true/false)."})

    def patch(self, request, pk):
        offre = get_object_or_404(Offre.objects.select_related("entreprise"), pk=pk)
        if offre.entreprise != request.user.entreprise:
            raise PermissionDenied("Vous ne pouvez modifier que vos offres")

        value = request.data.get("recevoirCandidatures")
        if value is None:
            raise ValidationError({"recevoirCandidatures": "Ce champ est requis (true/false)."})

        offre.recevoirCandidatures = self._parse_bool(value)
        offre.save()

        return Response(
            {
                "message": "Mise à jour réussie",
                "offreId": offre.offreId,
                "recevoirCandidatures": offre.recevoirCandidatures,
            },
            status=status.HTTP_200_OK,
        )


# ==========================
# ENVOIS APIViews
# ==========================
class EnvoiListCreate(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.type == "candidat":
            qs = Envoi.objects.filter(cv__user=user)
        elif user.type == "entreprise":
            qs = Envoi.objects.filter(offre__entreprise=user.entreprise)
        elif user.is_staff:
            qs = Envoi.objects.all()
        else:
            return Response({"error": "Accès refusé"}, status=status.HTTP_403_FORBIDDEN)

        qs = (
            qs.select_related("cv", "cv__user", "offre", "offre__entreprise")
            .prefetch_related("creneaux", "creneaux__reservePar")
            .order_by("-dateEnvoi")
        )
        serializer = EnvoiListSerializer(qs, many=True, context={"request": request})
        return Response({"count": qs.count(), "envois": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        if request.user.type != "candidat":
            return Response({"error": "Action réservée aux candidats"}, status=status.HTTP_403_FORBIDDEN)

        cv_id = request.data.get("cv_id")
        offre_ids = request.data.get("offre_ids", [])

        if not cv_id:
            return Response({"error": "L'identifiant du CV est requis"}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(offre_ids, list) or len(offre_ids) == 0:
            return Response({"error": "Aucune offre sélectionnée"}, status=status.HTTP_400_BAD_REQUEST)

        cleaned_ids = []
        for x in offre_ids:
            try:
                cleaned_ids.append(int(x))
            except (TypeError, ValueError):
                continue
        cleaned_ids = list(dict.fromkeys(cleaned_ids))

        if len(cleaned_ids) == 0:
            return Response({"error": "Liste d'offres invalide"}, status=status.HTTP_400_BAD_REQUEST)

        if len(cleaned_ids) > 100:
            return Response({"error": "Trop d'offres (max 100)"}, status=status.HTTP_400_BAD_REQUEST)

        cv = get_object_or_404(CV, cvId=cv_id, user=request.user, estSupprime=False)
        if cv.type != "cv":
            return Response(
                {"error": "Seuls les fichiers de type CV peuvent etre envoyes aux entreprises."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if cv.ai_status == "pending":
            ai_result = analyze_cv_file(cv.fichier)
            cv.ai_status = "validated" if ai_result["is_valid"] else "rejected"
            cv.ai_score = ai_result["score"]
            cv.ai_has_photo = ai_result["has_photo"]
            cv.ai_notes = ai_result["notes"]
            cv.ai_checked_at = timezone.now()
            cv.save(update_fields=["ai_status", "ai_score", "ai_has_photo", "ai_notes", "ai_checked_at"])

            if not ai_result["is_valid"]:
                reason = (ai_result.get("reasons") or ["Ce document ne ressemble pas a un CV professionnel."])[0]
                return Response(
                    {"error": "Ce CV n'a pas passe la verification IA.", "details": reason},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if cv.ai_status != "validated":
            return Response(
                {
                    "error": "Ce CV n'a pas passe la verification IA.",
                    "details": "Mettez a jour le document pour qu'il soit reconnu comme un CV professionnel.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        offres = Offre.objects.filter(
            offreId__in=cleaned_ids,
            recevoirCandidatures=True,
            estArchivee=False,
            entreprise__recevoirCandidatures=True,
        ).select_related("entreprise").distinct()

        if not offres.exists():
            return Response(
                {
                    "success": False,
                    "message": "Aucune offre valide trouvée dans votre sélection",
                    "created_count": 0,
                    "refused_count": 0,
                    "envois_ids": [],
                    "refusees": None,
                },
                status=status.HTTP_200_OK,
            )

        created_ids = []
        refused = []

        for offre in offres:
            payload = {"cv": cv.cvId, "offre": offre.offreId}
            ser = EnvoiSerializer(data=payload, context={"request": request})
            if ser.is_valid():
                envoi = ser.save()
                created_ids.append(envoi.envoiId)
                
                candidat_nom = f"{cv.user.prenom} {cv.user.nom}" if cv.user.prenom and cv.user.nom else cv.user.username
                Notification.objects.create(
                    utilisateur=offre.entreprise.user,
                    titre="Nouvelle candidature",
                    message=f"Le candidat {candidat_nom} a postulé à l'offre '{offre.titre}'.",
                    type="candidature",
                    lien="/entreprise/candidatures"
                )
            else:
                refused.append(
                    {
                        "offre": offre.titre,
                        "offreId": offre.offreId,
                        "entreprise": offre.entreprise.nomEntreprise,
                        "errors": ser.errors,
                    }
                )

        created_count = len(created_ids)
        refused_count = len(refused)

        if created_count == 0:
            first_reason = None
            if refused:
                first_errors = refused[0].get("errors")
                if isinstance(first_errors, dict):
                    parts = []
                    for value in first_errors.values():
                        if isinstance(value, (list, tuple)):
                            parts.extend(str(v) for v in value)
                        else:
                            parts.append(str(value))
                    if parts:
                        first_reason = " ".join(parts)
                elif first_errors:
                    first_reason = str(first_errors)

            message = "Aucune candidature n'a pu etre creee (toutes refusees)."
            if first_reason:
                message += f" Motif: {first_reason}"

            return Response(
                {
                    "success": False,
                    "message": message,
                    "created_count": created_count,
                    "refused_count": refused_count,
                    "envois_ids": created_ids,
                    "refusees": refused if refused else None,
                    "details": {"cv": cv.nom, "offres_total": offres.count()},
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "success": True,
                "message": f"{created_count} candidatures créées, {refused_count} refusées.",
                "created_count": created_count,
                "refused_count": refused_count,
                "envois_ids": created_ids,
                "refusees": refused if refused else None,
                "details": {"cv": cv.nom, "offres_total": offres.count()},
            },
            status=status.HTTP_201_CREATED,
        )


class EnvoiDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, request):
        envoi = get_object_or_404(Envoi.objects.select_related("cv", "cv__user", "offre", "offre__entreprise"), pk=pk)

        if request.user.type == "candidat":
            if envoi.cv.user != request.user:
                raise PermissionDenied("Vous ne pouvez voir que vos propres candidatures")
        elif request.user.type == "entreprise":
            if not hasattr(request.user, "entreprise"):
                raise PermissionDenied("Profil entreprise non trouvé")
            if envoi.offre.entreprise != request.user.entreprise:
                raise PermissionDenied("Vous ne pouvez voir que les candidatures de vos offres")
        elif not request.user.is_staff:
            raise PermissionDenied("Permission refusée")

        return envoi

    def get(self, request, pk):
        envoi = self.get_object(pk, request)
        return Response(EnvoiSerializer(envoi, context={"request": request}).data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        envoi = self.get_object(pk, request)

        if request.user.type != "entreprise":
            return Response({"error": "Seules les entreprises peuvent modifier le statut"}, status=status.HTTP_403_FORBIDDEN)

        if envoi.offre.entreprise != request.user.entreprise:
            raise PermissionDenied("Accès refusé")

        serializer = EnvoiStatutSerializer(envoi, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            
            if request.data.get("statut") in ["accepte", "refuse"]:
                statut_str = "acceptée" if request.data.get("statut") == "accepte" else "refusée"
                Notification.objects.create(
                    utilisateur=envoi.cv.user,
                    titre=f"Candidature {statut_str}",
                    message=f"Votre candidature pour l'offre '{envoi.offre.titre}' chez {envoi.offre.entreprise.nomEntreprise} a été {statut_str}.",
                    type="candidature",
                    lien="/candidatures"
                )

            return Response(
                {
                    "message": f"Statut mis à jour: {envoi.get_statut_display()}",
                    "envoi": EnvoiSerializer(envoi, context={"request": request}).data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        envoi = self.get_object(pk, request)
        envoi_info = f"{envoi.cv.nom} → {envoi.offre.titre}"
        envoi.delete()
        return Response({"message": f"Candidature supprimée: {envoi_info}"}, status=status.HTTP_200_OK)


# ==========================
# Entretien Créneau APIViews
# ==========================
class EntretienCreneauListCreate(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_envoi(self, request, envoi_id):
        envoi = get_object_or_404(
            Envoi.objects.select_related("cv__user", "offre__entreprise"),
            pk=envoi_id,
        )
        if request.user.type == "entreprise":
            if envoi.offre.entreprise != request.user.entreprise:
                raise PermissionDenied("Acces refuse.")
        elif request.user.type == "candidat":
            if envoi.cv.user != request.user:
                raise PermissionDenied("Acces refuse.")
        elif not request.user.is_staff:
            raise PermissionDenied("Acces refuse.")
        return envoi

    def get(self, request, envoi_id):
        envoi = self._get_envoi(request, envoi_id)
        qs = envoi.creneaux.all().order_by("startAt")
        serializer = EntretienCreneauReadSerializer(qs, many=True, context={"request": request})
        return Response({"count": qs.count(), "creneaux": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request, envoi_id):
        envoi = self._get_envoi(request, envoi_id)
        if request.user.type != "entreprise":
            return Response({"error": "Action reservee aux entreprises."}, status=status.HTTP_403_FORBIDDEN)
        if envoi.offre.entreprise != request.user.entreprise:
            raise PermissionDenied("Acces refuse.")
        if envoi.statut != "accepte":
            return Response(
                {"error": "Impossible de proposer un entretien tant que la candidature n'est pas acceptee."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = request.data
        is_batch = isinstance(payload, list)
        serializer = EntretienCreneauCreateSerializer(data=payload, many=is_batch, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if is_batch:
            created = [EntretienCreneau.objects.create(envoi=envoi, **item) for item in serializer.validated_data]
            
            Notification.objects.create(
                utilisateur=envoi.cv.user,
                titre="Nouveaux créneaux d'entretien",
                message=f"L'entreprise {envoi.offre.entreprise.nomEntreprise} a proposé {len(created)} créneau(x) pour l'offre '{envoi.offre.titre}'.",
                type="rendez_vous",
                lien="/candidatures"
            )

            output = EntretienCreneauReadSerializer(created, many=True, context={"request": request}).data
            return Response(
                {"message": f"{len(created)} creneaux proposes avec succes.", "creneaux": output},
                status=status.HTTP_201_CREATED,
            )

        creneau = serializer.save(envoi=envoi)
        
        Notification.objects.create(
            utilisateur=envoi.cv.user,
            titre="Nouveau créneau d'entretien",
            message=f"L'entreprise {envoi.offre.entreprise.nomEntreprise} a proposé un créneau d'entretien pour l'offre '{envoi.offre.titre}'.",
            type="rendez_vous",
            lien="/candidatures"
        )
        
        output = EntretienCreneauReadSerializer(creneau, context={"request": request}).data
        return Response({"message": "Creneau propose avec succes.", "creneau": output}, status=status.HTTP_201_CREATED)


class EntretienCreneauReserve(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCandidat]

    def post(self, request, creneau_id):
        creneau = get_object_or_404(
            EntretienCreneau.objects.select_related("envoi__cv__user", "envoi__offre__entreprise"),
            pk=creneau_id,
        )

        if creneau.envoi.cv.user != request.user:
            raise PermissionDenied("Vous ne pouvez reserver que vos propres entretiens.")
        if creneau.envoi.statut != "accepte":
            return Response({"error": "La candidature doit etre acceptee pour reserver un creneau."}, status=status.HTTP_400_BAD_REQUEST)
        if creneau.estReserve:
            return Response({"error": "Ce creneau est deja reserve."}, status=status.HTTP_400_BAD_REQUEST)
        if creneau.startAt <= timezone.now():
            return Response({"error": "Ce creneau est deja passe."}, status=status.HTTP_400_BAD_REQUEST)

        already_reserved = EntretienCreneau.objects.filter(
            envoi=creneau.envoi, estReserve=True, reservePar=request.user
        ).exists()
        if already_reserved:
            return Response(
                {"error": "Vous avez deja reserve un creneau pour cette candidature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        creneau.estReserve = True
        creneau.reservePar = request.user
        creneau.dateReservation = timezone.now()
        creneau.save(update_fields=["estReserve", "reservePar", "dateReservation"])

        candidat_nom = f"{request.user.prenom} {request.user.nom}" if request.user.prenom and request.user.nom else request.user.username
        Notification.objects.create(
            utilisateur=creneau.envoi.offre.entreprise.user,
            titre="Créneau réservé",
            message=f"Le candidat {candidat_nom} a réservé un créneau d'entretien pour l'offre '{creneau.envoi.offre.titre}'.",
            type="rendez_vous",
            lien="/entreprise/candidatures"
        )

        serializer = EntretienCreneauReadSerializer(creneau, context={"request": request})
        return Response({"message": "Creneau reserve avec succes.", "creneau": serializer.data}, status=status.HTTP_200_OK)


class EntretienMeetingInfo(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, creneau_id):
        creneau = get_object_or_404(
            EntretienCreneau.objects.select_related("envoi__cv__user", "envoi__offre__entreprise"),
            pk=creneau_id,
        )

        is_owner_candidat = request.user.type == "candidat" and creneau.envoi.cv.user == request.user
        is_owner_entreprise = (
            request.user.type == "entreprise"
            and hasattr(request.user, "entreprise")
            and creneau.envoi.offre.entreprise == request.user.entreprise
        )
        if not (is_owner_candidat or is_owner_entreprise or request.user.is_staff):
            raise PermissionDenied("Acces refuse.")

        if not creneau.estReserve:
            return Response({"error": "Ce creneau n'est pas encore reserve."}, status=status.HTTP_400_BAD_REQUEST)

        room_name = f"pfe-entretien-{creneau.creneauId}"
        meeting_url = f"https://meet.jit.si/{room_name}"
        now = timezone.now()
        can_join = (creneau.startAt - timedelta(minutes=10)) <= now <= (creneau.endAt + timedelta(minutes=30))

        return Response(
            {
                "creneauId": creneau.creneauId,
                "room_name": room_name,
                "meeting_url": meeting_url,
                "start_at": creneau.startAt,
                "end_at": creneau.endAt,
                "can_join": can_join,
                "mode": creneau.mode,
                "lieu_ou_lien": creneau.lieuOuLien,
            },
            status=status.HTTP_200_OK,
        )


# ==========================
# Dashboard Stats
# ==========================
class DashboardStats(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.type == "candidat":
            cvs = CV.objects.filter(user=user, estSupprime=False)
            envois = Envoi.objects.filter(cv__user=user)
            stats = {
                "total_cvs": cvs.count(),
                "total_envois": envois.count(),
                "envois_par_statut": {
                    "envoye": envois.filter(statut="envoye").count(),
                    "en_attente": envois.filter(statut="en_attente").count(),
                    "accepte": envois.filter(statut="accepte").count(),
                    "refuse": envois.filter(statut="refuse").count(),
                },
                "taux_reponse": self._calculer_taux_reponse(envois),
            }

        elif user.type == "entreprise":
            if not hasattr(user, "entreprise"):
                return Response({"error": "Profil entreprise non trouvé"}, status=status.HTTP_404_NOT_FOUND)
            envois = Envoi.objects.filter(offre__entreprise=user.entreprise)
            stats = {
                "total_offres": Offre.objects.filter(entreprise=user.entreprise).count(),
                "total_candidatures": envois.count(),
                "candidatures_par_statut": {
                    "envoye": envois.filter(statut="envoye").count(),
                    "en_attente": envois.filter(statut="en_attente").count(),
                    "accepte": envois.filter(statut="accepte").count(),
                    "refuse": envois.filter(statut="refuse").count(),
                },
                "candidatures_non_traitees": envois.filter(statut="envoye").count(),
            }

        else:
            stats = {
                "total_utilisateurs": Utilisateur.objects.count(),
                "total_entreprises": Entreprise.objects.count(),
                "total_cvs": CV.objects.filter(estSupprime=False).count(),
                "total_offres": Offre.objects.count(),
                "total_envois": Envoi.objects.count(),
            }

        return Response(stats, status=status.HTTP_200_OK)

    def _calculer_taux_reponse(self, envois):
        total = envois.count()
        if total == 0:
            return 0
        reponses = envois.filter(statut__in=["en_attente", "accepte", "refuse"]).count()
        return round((reponses / total) * 100, 2)


class EntretienCreneauAnnuler(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, creneau_id):
        creneau = get_object_or_404(
            EntretienCreneau.objects.select_related("envoi__cv__user", "envoi__offre__entreprise"),
            pk=creneau_id,
        )

        if request.user.type == "candidat":
            if creneau.envoi.cv.user != request.user:
                raise PermissionDenied("Acces refuse.")
        elif request.user.type == "entreprise":
            if creneau.envoi.offre.entreprise != request.user.entreprise:
                raise PermissionDenied("Acces refuse.")
        else:
            raise PermissionDenied("Acces refuse.")

        if not creneau.estReserve:
            return Response({"error": "Ce creneau n'est pas reserve."}, status=status.HTTP_400_BAD_REQUEST)
        if creneau.startAt <= timezone.now():
            return Response({"error": "Impossible d'annuler un creneau deja passe."}, status=status.HTTP_400_BAD_REQUEST)

        creneau.estReserve = False
        creneau.reservePar = None
        creneau.dateReservation = None
        creneau.save(update_fields=["estReserve", "reservePar", "dateReservation"])

        if request.user.type == "candidat":
            candidat_nom = f"{request.user.prenom} {request.user.nom}" if request.user.prenom and request.user.nom else request.user.username
            Notification.objects.create(
                utilisateur=creneau.envoi.offre.entreprise.user,
                titre="Entretien annulé",
                message=f"Le candidat {candidat_nom} a annulé son rendez-vous pour l'offre '{creneau.envoi.offre.titre}'.",
                type="rendez_vous",
                lien="/entreprise/candidatures"
            )
        elif request.user.type == "entreprise":
            Notification.objects.create(
                utilisateur=creneau.envoi.cv.user,
                titre="Entretien annulé",
                message=f"L'entreprise {creneau.envoi.offre.entreprise.nomEntreprise} a annulé le rendez-vous pour l'offre '{creneau.envoi.offre.titre}'.",
                type="rendez_vous",
                lien="/candidatures"
            )

        return Response({"message": "Creneau annule avec succes."}, status=status.HTTP_200_OK)


# ==========================
# Notifications
# ==========================
from rest_framework.decorators import action

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(utilisateur=self.request.user)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        self.get_queryset().update(lu=True)
        return Response({"message": "Toutes les notifications ont été marquées comme lues."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.lu = True
        notification.save(update_fields=['lu'])
        return Response(self.get_serializer(notification).data, status=status.HTTP_200_OK)