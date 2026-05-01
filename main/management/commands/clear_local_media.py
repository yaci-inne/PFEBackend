"""
Management command: clear_local_media
======================================
Clears any photoProfil / fichier DB values that point to local Railway paths
(i.e. NOT a Cloudinary URL). Since Railway's filesystem is ephemeral, these
files are already gone — this just removes the broken references from the DB
so the API returns null instead of a 404 URL.

Usage:
    python manage.py clear_local_media           # dry run
    python manage.py clear_local_media --apply   # actually clear
"""

from django.core.management.base import BaseCommand
from main.models import Utilisateur, CV


def is_cloudinary(value: str) -> bool:
    return "cloudinary.com" in value or "res.cloudinary.com" in value


class Command(BaseCommand):
    help = "Clear broken local-storage file references from DB (Railway ephemeral FS)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually clear the references (default is dry-run)",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        self.stdout.write(self.style.WARNING(
            f"\n=== clear_local_media [{'APPLY' if apply else 'DRY RUN'}] ===\n"
        ))

        # ── Photos de profil ──────────────────────────────────────────
        self.stdout.write("Checking photoProfil...")
        photo_cleared = 0
        for user in Utilisateur.objects.exclude(photoProfil="").exclude(photoProfil=None):
            val = str(user.photoProfil)
            if not is_cloudinary(val):
                self.stdout.write(f"  [CLEAR] user={user.username!r}  path={val!r}")
                if apply:
                    user.photoProfil = None
                    user.save(update_fields=["photoProfil"])
                photo_cleared += 1

        # ── CV fichiers ───────────────────────────────────────────────
        self.stdout.write("Checking CV fichiers...")
        cv_cleared = 0
        for cv in CV.objects.exclude(fichier="").exclude(fichier=None):
            val = str(cv.fichier)
            if not is_cloudinary(val):
                self.stdout.write(f"  [CLEAR] cv={cv.cvId} ({cv.nom!r})  path={val!r}")
                if apply:
                    cv.fichier = None
                    cv.save(update_fields=["fichier"])
                cv_cleared += 1

        # ── Summary ───────────────────────────────────────────────────
        self.stdout.write("")
        if apply:
            self.stdout.write(self.style.SUCCESS(
                f"Done. Cleared {photo_cleared} photos, {cv_cleared} CV files."
            ))
        else:
            self.stdout.write(self.style.NOTICE(
                f"Dry run: would clear {photo_cleared} photos, {cv_cleared} CV files.\n"
                f"Run with --apply to actually clear them."
            ))