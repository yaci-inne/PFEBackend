import io
import re
import zipfile
from datetime import datetime

from PIL import Image


CV_KEYWORDS = {
    "experience",
    "experiences",
    "formation",
    "education",
    "competences",
    "skills",
    "projet",
    "projets",
    "langues",
    "certification",
    "stage",
    "profil",
    "contact",
}

SECTION_KEYWORDS = {
    "experience": ["experience", "experiences", "internship", "stage"],
    "education": ["formation", "education", "diplome", "universite"],
    "skills": ["competences", "skills", "technologies", "outils"],
    "contact": ["contact", "email", "telephone", "phone", "linkedin"],
}

LOW_QUALITY_MARKERS = {
    "lorem",
    "ipsum",
    "asdf",
    "qwerty",
    "testtest",
    "xxxxx",
    "dummy",
}
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".jfif")


def _read_file_bytes(uploaded_file):
    uploaded_file.seek(0)
    data = uploaded_file.read()
    uploaded_file.seek(0)
    return data


def _extract_text_from_pdf(file_bytes):
    # Primary path: parse true PDF text if pypdf exists.
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(file_bytes))
        chunks = []
        for page in reader.pages:
            chunks.append(page.extract_text() or "")
        return "\n".join(chunks)
    except Exception:
        # Fallback: keep only readable tokens.
        raw = file_bytes.decode("latin-1", errors="ignore")
        return " ".join(re.findall(r"[A-Za-zÀ-ÿ]{3,}", raw))


def _extract_text_from_docx(file_bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
            return " ".join(re.findall(r">([^<]+)<", xml))
    except Exception:
        return ""


def _extract_text_from_doc(file_bytes):
    return file_bytes.decode("latin-1", errors="ignore")


def _detect_photo_presence(filename, file_bytes):
    lower = filename.lower()
    if lower.endswith(".docx"):
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                media_files = [n for n in zf.namelist() if n.startswith("word/media/")]
                return len(media_files) > 0
        except Exception:
            return False

    if lower.endswith(".pdf"):
        return file_bytes.count(b"/Image") > 0

    if lower.endswith(IMAGE_EXTENSIONS):
        return True

    return False


def _analyze_image_cv(file_bytes):
    reasons = []
    score = 55
    try:
        img = Image.open(io.BytesIO(file_bytes))
        width, height = img.size
        ratio = width / max(height, 1)

        if width < 700 or height < 900:
            reasons.append("Image de CV trop petite. Utilisez une image plus nette.")
            score -= 15

        if ratio < 0.55 or ratio > 0.85:
            reasons.append("Le format de l'image ne ressemble pas a une page CV (portrait recommande).")
            score -= 12

        if img.mode in ("1", "P"):
            score -= 5

        is_valid = score >= 50
        if not is_valid and not reasons:
            reasons.append("Le document image ne semble pas etre un CV lisible.")

        return {
            "is_valid": is_valid,
            "score": max(0, min(score, 100)),
            "reasons": reasons,
            "word_count": 0,
            "keyword_hits": 0,
            "section_hits": 0,
        }
    except Exception:
        return {
            "is_valid": False,
            "score": 0,
            "reasons": ["Image invalide ou corrompue."],
            "word_count": 0,
            "keyword_hits": 0,
            "section_hits": 0,
        }


def _score_cv_text(text, has_photo):
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    words = re.findall(r"[a-zà-ÿ]{2,}", normalized)
    word_count = len(words)
    unique_ratio = (len(set(words)) / word_count) if word_count else 0

    keyword_hits = len(CV_KEYWORDS.intersection(set(words)))
    section_hits = 0
    for terms in SECTION_KEYWORDS.values():
        if any(term in normalized for term in terms):
            section_hits += 1

    low_quality_hits = sum(1 for marker in LOW_QUALITY_MARKERS if marker in normalized)

    score = 0
    if word_count >= 120:
        score += 25
    elif word_count >= 80:
        score += 18
    elif word_count >= 50:
        score += 10

    score += min(keyword_hits * 4, 24)
    score += section_hits * 8
    if unique_ratio >= 0.35:
        score += 10
    elif unique_ratio >= 0.25:
        score += 5

    if has_photo:
        score += 6
    else:
        score -= 5

    if low_quality_hits > 0:
        score -= min(low_quality_hits * 8, 24)

    score = max(0, min(score, 100))

    reasons = []
    if word_count < 80:
        reasons.append("Le document semble trop court pour un CV complet.")
    if keyword_hits < 3:
        reasons.append("Le vocabulaire CV detecte est insuffisant.")
    if section_hits < 2:
        reasons.append("Sections CV non detectees (experience, formation, competences, contact).")
    if not has_photo:
        reasons.append("Aucune photo detectee. Une photo professionnelle est recommandee.")

    is_valid = score >= 60 and word_count >= 80 and keyword_hits >= 3 and section_hits >= 2
    return {
        "is_valid": is_valid,
        "score": score,
        "reasons": reasons,
        "word_count": word_count,
        "keyword_hits": keyword_hits,
        "section_hits": section_hits,
    }


def analyze_cv_file(uploaded_file):
    file_bytes = _read_file_bytes(uploaded_file)
    filename = (uploaded_file.name or "").lower()

    if filename.endswith(IMAGE_EXTENSIONS):
        text = ""
    elif filename.endswith(".pdf"):
        text = _extract_text_from_pdf(file_bytes)
    elif filename.endswith(".docx"):
        text = _extract_text_from_docx(file_bytes)
    elif filename.endswith(".doc"):
        text = _extract_text_from_doc(file_bytes)
    else:
        text = ""

    has_photo = _detect_photo_presence(filename, file_bytes)
    if filename.endswith(IMAGE_EXTENSIONS):
        scoring = _analyze_image_cv(file_bytes)
    else:
        scoring = _score_cv_text(text, has_photo)

    # Optional image sanity check when file is image-based profile doc.
    try:
        Image.MAX_IMAGE_PIXELS = 50_000_000
    except Exception:
        pass

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
    }
