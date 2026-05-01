import io
import re
import unicodedata
import zipfile
from datetime import datetime

from PIL import Image

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".jfif", ".webp", ".bmp", ".tiff")
SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".doc", ".odt", ".rtf") + IMAGE_EXTENSIONS

# Keywords CV enrichis FR + EN
CV_KEYWORDS = {
    # Français
    "experience", "experiences", "formation", "education", "competences",
    "projet", "projets", "langues", "certification", "certifications",
    "stage", "stages", "profil", "contact", "objectif", "references",
    "realisation", "realisations", "activites", "benevolat", "publications",
    "prix", "distinctions", "interets", "loisirs", "poste", "emploi",
    "responsabilites", "missions", "entreprise", "societe", "diplome",
    "baccalaureat", "licence", "master", "doctorat", "ingenieur",
    "technicien", "developpeur", "programmeur", "analyste", "consultant",
    # Anglais
    "skills", "summary", "objective", "work", "internship", "volunteer",
    "achievements", "awards", "interests", "hobbies", "references",
    "professional", "career", "position", "responsibilities", "projects",
    "languages", "tools", "technologies", "frameworks", "profile",
    "developer", "engineer", "analyst", "manager", "coordinator",
    # Commun
    "linkedin", "github", "portfolio", "email", "telephone", "phone",
    "adresse", "address", "ville", "city", "nationality", "nationalite",
}

SECTION_KEYWORDS = {
    "experience": [
        "experience", "experiences", "internship", "stage", "stages",
        "emploi", "poste", "work experience", "professional experience",
        "parcours professionnel", "carriere", "historique professionnel",
    ],
    "education": [
        "formation", "education", "diplome", "universite", "ecole",
        "baccalaureat", "licence", "master", "doctorat", "ingenieur",
        "academic", "studies", "scolarite", "cursus", "etudes",
    ],
    "skills": [
        "competences", "skills", "technologies", "outils", "tools",
        "frameworks", "langages", "savoir", "maitrise", "expertise",
        "connaissances", "aptitudes", "capacites",
    ],
    "contact": [
        "contact", "email", "telephone", "phone", "linkedin",
        "adresse", "address", "coordonnees", "joindre",
    ],
    "profil": [
        "profil", "profile", "summary", "objectif", "objective",
        "a propos", "about", "introduction", "presentation", "resume",
    ],
    "langues": [
        "langues", "languages", "langue", "francais", "anglais",
        "arabe", "espagnol", "allemand", "italien", "bilingue",
    ],
    "certifications": [
        "certification", "certifications", "certificat", "diplome",
        "award", "prix", "distinction", "formation certifiante",
    ],
    "projets": [
        "projet", "projets", "projects", "realisation", "realisations",
        "portfolio", "github", "application", "developpement",
    ],
}

LOW_QUALITY_MARKERS = {
    "lorem", "ipsum", "asdf", "qwerty", "testtest",
    "xxxxx", "dummy", "placeholder", "sample text",
    "votre nom", "your name", "your email", "nom prenom",
}

# Mots qui indiquent que c'est PAS un CV
NON_CV_MARKERS = {
    # Lettre de motivation
    "madame", "monsieur", "je me permets", "je vous adresse",
    "je vous prie", "veuillez agreer", "cordialement",
    "je suis interesse", "candidature spontanee",
    # Contrat
    "contrat de travail", "entre les soussignes", "article 1",
    "clause", "resiliation", "preavis",
    # Facture
    "facture", "montant ttc", "tva", "avoir",
    # Article/rapport
    "abstract", "introduction", "conclusion", "bibliographie",
    "references bibliographiques", "chapitre",
}


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def _read_file_bytes(uploaded_file):
    uploaded_file.seek(0)
    data = uploaded_file.read()
    uploaded_file.seek(0)
    return data


def _normalize(text):
    """Minuscule + suppression accents pour comparaison."""
    text = text.lower()
    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", text).strip()


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACTION TEXTE
# ══════════════════════════════════════════════════════════════════════════════

def _extract_text_from_pdf(file_bytes):
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        # Si PDF scanné → texte vide, on tente pdfminer
        if len(text.strip()) < 100:
            try:
                from pdfminer.high_level import extract_text as pm_extract
                text = pm_extract(io.BytesIO(file_bytes)) or text
            except Exception:
                pass
        return text
    except Exception:
        raw = file_bytes.decode("latin-1", errors="ignore")
        return " ".join(re.findall(r"[A-Za-zÀ-ÿ]{3,}", raw))


def _extract_text_from_docx(file_bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
            text = re.sub(r"<[^>]+>", " ", xml)
            return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return ""


def _extract_text_from_doc(file_bytes):
    try:
        import docx2txt
        return docx2txt.process(io.BytesIO(file_bytes)) or ""
    except Exception:
        return file_bytes.decode("latin-1", errors="ignore")


def _extract_text_from_odt(file_bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            xml = zf.read("content.xml").decode("utf-8", errors="ignore")
            text = re.sub(r"<[^>]+>", " ", xml)
            return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return ""


def _extract_text_from_rtf(file_bytes):
    try:
        from striprtf.striprtf import rtf_to_text
        return rtf_to_text(file_bytes.decode("latin-1", errors="ignore"))
    except Exception:
        raw = file_bytes.decode("latin-1", errors="ignore")
        return " ".join(re.findall(r"[A-Za-zÀ-ÿ]{3,}", raw))


def _extract_text(filename, file_bytes):
    if filename.endswith(".pdf"):
        return _extract_text_from_pdf(file_bytes)
    if filename.endswith(".docx"):
        return _extract_text_from_docx(file_bytes)
    if filename.endswith(".doc"):
        return _extract_text_from_doc(file_bytes)
    if filename.endswith(".odt"):
        return _extract_text_from_odt(file_bytes)
    if filename.endswith(".rtf"):
        return _extract_text_from_rtf(file_bytes)
    return ""


# ══════════════════════════════════════════════════════════════════════════════
# DÉTECTION PHOTO
# ══════════════════════════════════════════════════════════════════════════════

def _detect_photo_presence(filename, file_bytes):
    if filename.endswith((".docx", ".odt")):
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                return any(
                    re.search(r"\.(jpg|jpeg|png|bmp|gif|webp)", n, re.I)
                    for n in zf.namelist()
                )
        except Exception:
            return False

    if filename.endswith(".pdf"):
        return b"/Image" in file_bytes or b"/XObject" in file_bytes

    if filename.endswith(IMAGE_EXTENSIONS):
        return True

    return False


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSE IMAGE (photo de visage → rejet immédiat)
# ══════════════════════════════════════════════════════════════════════════════

def _analyze_image_cv(file_bytes):
    reasons = []
    try:
        Image.MAX_IMAGE_PIXELS = 50_000_000
        img = Image.open(io.BytesIO(file_bytes))
        width, height = img.size
        ratio = width / max(height, 1)

        # ── Rejet photo de visage / selfie ────────────────────────────────
        # Une photo de visage est typiquement carrée ou presque carrée
        if ratio > 0.88:
            return {
                "is_valid": False,
                "score": 5,
                "reasons": [
                    "Format carré ou paysage détecté — il semble que vous avez importé "
                    "une photo personnelle. Un CV doit être un document texte en format portrait (A4). "
                    "Veuillez importer votre CV au format PDF ou DOCX."
                ],
                "word_count": 0, "keyword_hits": 0,
                "section_hits": 0, "detected_sections": [],
            }

        # ── Trop petite → photo d'identité ────────────────────────────────
        if width < 500 or height < 700:
            return {
                "is_valid": False,
                "score": 5,
                "reasons": [
                    "Image trop petite — cela ressemble à une photo d'identité ou miniature. "
                    "Veuillez importer votre CV complet (PDF ou DOCX recommandé)."
                ],
                "word_count": 0, "keyword_hits": 0,
                "section_hits": 0, "detected_sections": [],
            }

        # ── Ratio trop étroit → pas un A4 ─────────────────────────────────
        if ratio < 0.45:
            return {
                "is_valid": False,
                "score": 10,
                "reasons": ["Format trop étroit — ce n'est pas un document CV standard."],
                "word_count": 0, "keyword_hits": 0,
                "section_hits": 0, "detected_sections": [],
            }

        # ── Analyse couleurs (détecter photo naturelle) ────────────────────
        # Une photo naturelle a beaucoup de variation de couleurs
        # Un CV image a généralement fond blanc/clair dominant
        try:
            img_rgb = img.convert("RGB")
            # Echantillon de pixels sur les bords (fond d'un CV = blanc)
            pixels = list(img_rgb.getdata())
            sample = pixels[::max(1, len(pixels) // 500)]  # 500 pixels max

            # Calculer la luminosité moyenne
            brightness = sum((r + g + b) / 3 for r, g, b in sample) / len(sample)

            # CV image → fond clair (luminosité > 180 généralement)
            if brightness < 100:
                reasons.append(
                    "L'image semble être une photo (fond sombre). "
                    "Un CV en image doit avoir un fond blanc/clair."
                )
                return {
                    "is_valid": False,
                    "score": 15,
                    "reasons": reasons,
                    "word_count": 0, "keyword_hits": 0,
                    "section_hits": 0, "detected_sections": [],
                }

            # Calculer la variance des couleurs
            avg_r = sum(r for r, g, b in sample) / len(sample)
            avg_g = sum(g for r, g, b in sample) / len(sample)
            avg_b = sum(b for r, g, b in sample) / len(sample)

            variance = sum(
                abs(r - avg_r) + abs(g - avg_g) + abs(b - avg_b)
                for r, g, b in sample
            ) / len(sample)

            # Photo naturelle → grande variance de couleurs (> 60)
            # Document CV → faible variance (fond blanc + texte noir)
            if variance > 65:
                return {
                    "is_valid": False,
                    "score": 10,
                    "reasons": [
                        "L'image semble être une photo et non un document CV. "
                        "Veuillez importer votre CV en format PDF ou DOCX."
                    ],
                    "word_count": 0, "keyword_hits": 0,
                    "section_hits": 0, "detected_sections": [],
                }

        except Exception:
            pass

        # ── L'image passe tous les filtres → probablement un CV scanné ────
        score = 60
        if width >= 1000 and height >= 1400:
            score += 10  # haute résolution = bonus
        if img.mode in ("1", "P"):
            score -= 5

        return {
            "is_valid": score >= 55,
            "score": min(score, 100),
            "reasons": reasons,
            "word_count": 0, "keyword_hits": 0,
            "section_hits": 0, "detected_sections": [],
        }

    except Exception:
        return {
            "is_valid": False,
            "score": 0,
            "reasons": ["Image invalide ou corrompue."],
            "word_count": 0, "keyword_hits": 0,
            "section_hits": 0, "detected_sections": [],
        }


# ══════════════════════════════════════════════════════════════════════════════
# SCORING TEXTE
# ══════════════════════════════════════════════════════════════════════════════

def _score_cv_text(text, has_photo):
    normalized = _normalize(text)
    words = re.findall(r"[a-zA-Z\u00C0-\u017E]{2,}", normalized)
    word_count = len(words)
    word_set = set(words)
    unique_ratio = (len(word_set) / word_count) if word_count else 0

    # ── Détection NON-CV (lettre, contrat, article...) ────────────────────
    non_cv_hits = sum(1 for marker in NON_CV_MARKERS if marker in normalized)
    if non_cv_hits >= 2:
        return {
            "is_valid": False,
            "score": 5,
            "reasons": [
                "Ce document ne semble pas être un CV — "
                "il ressemble à une lettre de motivation, un contrat ou un autre document. "
                "Veuillez importer uniquement votre CV."
            ],
            "word_count": word_count,
            "keyword_hits": 0,
            "section_hits": 0,
            "detected_sections": [],
        }

    # ── Keywords CV ───────────────────────────────────────────────────────
    keyword_hits = len(CV_KEYWORDS.intersection(word_set))

    # ── Sections détectées ────────────────────────────────────────────────
    section_hits = 0
    detected_sections = []
    for section_name, terms in SECTION_KEYWORDS.items():
        if any(term in normalized for term in terms):
            section_hits += 1
            detected_sections.append(section_name)

    # ── Qualité basse ─────────────────────────────────────────────────────
    low_quality_hits = sum(1 for m in LOW_QUALITY_MARKERS if m in normalized)

    # ── Calcul score ──────────────────────────────────────────────────────
    score = 0

    # Volume texte
    if word_count >= 200:
        score += 25
    elif word_count >= 150:
        score += 22
    elif word_count >= 100:
        score += 18
    elif word_count >= 60:
        score += 12
    elif word_count >= 30:
        score += 5

    # Keywords (max 25 pts)
    score += min(keyword_hits * 5, 25)

    # Sections (max 30 pts sur 8 sections possibles)
    score += min(section_hits * 6, 30)

    # Diversité vocabulaire
    if unique_ratio >= 0.45:
        score += 10
    elif unique_ratio >= 0.35:
        score += 7
    elif unique_ratio >= 0.25:
        score += 4

    # Bonus email détecté
    if re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", normalized):
        score += 5

    # Bonus téléphone détecté
    if re.search(r"(\+?\d[\d\s\-().]{7,}\d)", normalized):
        score += 3

    # Bonus années (expériences datées)
    years = re.findall(r"\b(19[7-9]\d|20[0-2]\d)\b", normalized)
    if len(years) >= 3:
        score += 7
    elif len(years) >= 1:
        score += 3

    # Bonus photo
    if has_photo:
        score += 5

    # Pénalité contenu bas de gamme
    if low_quality_hits > 0:
        score -= min(low_quality_hits * 10, 25)

    score = max(0, min(score, 100))

    # ── Validation finale ─────────────────────────────────────────────────
    is_valid = (
        score >= 45
        and word_count >= 50
        and keyword_hits >= 2
        and section_hits >= 2
    )

    # ── Messages d'erreur précis ──────────────────────────────────────────
    reasons = []
    if word_count < 50:
        reasons.append(
            f"Document trop court ({word_count} mots détectés). "
            "Un CV complet contient généralement au moins 100 mots."
        )
    if keyword_hits < 2:
        reasons.append(
            "Vocabulaire professionnel CV insuffisant. "
            "Vérifiez que le document est bien un CV (expérience, formation, compétences...)."
        )
    if section_hits < 2:
        detected_str = ", ".join(detected_sections) if detected_sections else "aucune"
        reasons.append(
            f"Sections CV insuffisantes (détectées : {detected_str}). "
            "Un CV doit contenir au moins 2 sections parmi : "
            "expérience, formation, compétences, contact, profil, langues."
        )
    if low_quality_hits > 0:
        reasons.append("Contenu factice ou placeholder détecté dans le document.")

    return {
        "is_valid": is_valid,
        "score": score,
        "reasons": reasons,
        "word_count": word_count,
        "keyword_hits": keyword_hits,
        "section_hits": section_hits,
        "detected_sections": detected_sections,
    }


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def analyze_cv_file(uploaded_file):
    Image.MAX_IMAGE_PIXELS = 50_000_000

    file_bytes = _read_file_bytes(uploaded_file)
    filename = (uploaded_file.name or "").lower()

    # ── Format non supporté ───────────────────────────────────────────────
    if not filename.endswith(SUPPORTED_EXTENSIONS):
        return {
            "is_valid": False,
            "score": 0,
            "has_photo": False,
            "notes": "format_non_supporte",
            "reasons": [
                "Format non supporté. Formats acceptés : "
                "PDF, DOCX, DOC, ODT, RTF, JPG, PNG, WEBP, BMP, TIFF."
            ],
            "detected_sections": [],
        }

    has_photo = _detect_photo_presence(filename, file_bytes)

    # ── Routing analyse ───────────────────────────────────────────────────
    if filename.endswith(IMAGE_EXTENSIONS):
        scoring = _analyze_image_cv(file_bytes)
    else:
        text = _extract_text(filename, file_bytes)
        scoring = _score_cv_text(text, has_photo)

    # ── Notes de debug ────────────────────────────────────────────────────
    notes = [
        f"score={scoring['score']}",
        f"mots={scoring['word_count']}",
        f"sections={scoring['section_hits']}",
        f"keywords={scoring['keyword_hits']}",
        f"photo={has_photo}",
        f"checked_at={datetime.utcnow().isoformat()}Z",
    ]

    return {
        "is_valid": scoring["is_valid"],
        "score": scoring["score"],
        "has_photo": has_photo,
        "notes": " | ".join(notes),
        "reasons": scoring["reasons"],
        "detected_sections": scoring.get("detected_sections", []),
    }