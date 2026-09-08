"""
ocr_utils.py
Automatic "reading" of uploaded worksheet images/PDFs using classic OCR.

RESILIENCE NOTE (important):
Tesseract OCR requires a SYSTEM package (installed via packages.txt on
Streamlit Cloud), not just a Python package. Streamlit Cloud's build
servers occasionally hit a transient, Streamlit-side infrastructure issue
where the underlying Debian package mirror is stale, causing apt-get to
fail - this is a known, recurring Streamlit Cloud bug unrelated to this
app's code (see: discuss.streamlit.io threads on "bullseye-security
InRelease is expired"). If that happens, packages.txt installation fails
and pytesseract has nothing to talk to.

To make this app resilient to that class of failure, ALL OCR-related
imports and calls in this file are wrapped so that if Tesseract/PyMuPDF
are unavailable for any reason, the rest of the app (Gemini generation,
missions, scoring, homework helper, etc.) keeps working perfectly -
only the OCR-specific "read printed text automatically" feature is
skipped, with a clear message to the parent instead of a crash.
"""

import re
from collections import Counter
from io import BytesIO

OCR_AVAILABLE = True
OCR_UNAVAILABLE_REASON = ""

try:
    import pytesseract
    from PIL import Image
except ImportError as exc:
    OCR_AVAILABLE = False
    OCR_UNAVAILABLE_REASON = f"pytesseract/Pillow not installed ({exc})"

try:
    import fitz  # PyMuPDF, used to turn PDF pages into images for OCR
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

if OCR_AVAILABLE:
    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:
        # The Python package is installed, but the system Tesseract binary
        # is missing (e.g. packages.txt failed to install on the host due
        # to a Streamlit Cloud infra hiccup). Treat OCR as unavailable
        # rather than crashing every time a worksheet is uploaded.
        OCR_AVAILABLE = False
        OCR_UNAVAILABLE_REASON = f"Tesseract system binary not found ({exc})"

STOPWORDS = {
    "the", "and", "a", "an", "of", "to", "in", "is", "it", "for", "on", "with",
    "this", "that", "are", "was", "were", "be", "as", "at", "by", "or", "if",
    "worksheet", "name", "date", "class", "school", "page", "chapter",
}

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
KANNADA_RE = re.compile(r"[\u0C80-\u0CFF]")
WORD_RE = re.compile(r"[A-Za-z\u0900-\u097F\u0C80-\u0CFF]{2,}")
DIGIT_RE = re.compile(r"\d")


def _ocr_image(img) -> str:
    try:
        return pytesseract.image_to_string(img, lang="eng+hin+kan")
    except Exception:
        try:
            return pytesseract.image_to_string(img, lang="eng")
        except Exception:
            return ""


def extract_text(file_bytes: bytes, filename: str) -> str:
    if not OCR_AVAILABLE:
        return ""
    name = filename.lower()
    if name.endswith(".pdf") and HAS_PDF:
        text_parts = []
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc[:3]:
            pix = page.get_pixmap(dpi=200)
            img = Image.open(BytesIO(pix.tobytes("png")))
            text_parts.append(_ocr_image(img))
        return "\n".join(text_parts)
    else:
        img = Image.open(BytesIO(file_bytes)).convert("RGB")
        return _ocr_image(img)


def detect_language_hint(text: str) -> str:
    if DEVANAGARI_RE.search(text):
        return "Hindi"
    if KANNADA_RE.search(text):
        return "Kannada"
    return "English"


def suggest_topic(text: str, section: str) -> str:
    words = WORD_RE.findall(text)
    digits = DIGIT_RE.findall(text)

    if section == "Numeracy" and len(digits) >= 3:
        nums = sorted(set(int(d) for d in digits if d.isdigit()))[:6]
        if nums:
            return f"numbers and counting (seen: {', '.join(map(str, nums))})"

    lower_words = [w.lower() for w in words if w.lower() not in STOPWORDS]
    if not lower_words:
        return ""

    single_letters = [w for w in words if len(w) == 1 and w.isalpha()]
    if len(single_letters) >= 2 and len(lower_words) <= 12:
        letter = single_letters[0].upper()
        rest = [w for w in lower_words if len(w) > 1][:4]
        if rest:
            return f"the letter {letter} ({', '.join(rest)})"
        return f"the letter {letter}"

    freq = Counter(lower_words)
    top = [w for w, _ in freq.most_common(6) if len(w) > 1]
    if not top:
        return ""
    return ", ".join(top[:5])


def analyse_upload(file_bytes: bytes, filename: str, section: str) -> dict:
    if not OCR_AVAILABLE:
        return {
            "raw_text": "", "language_hint": "Unknown",
            "suggested_topic": "", "word_count": 0,
            "ocr_available": False,
        }
    text = extract_text(file_bytes, filename).strip()
    return {
        "raw_text": text,
        "language_hint": detect_language_hint(text) if text else "Unknown",
        "suggested_topic": suggest_topic(text, section) if text else "",
        "word_count": len(WORD_RE.findall(text)),
        "ocr_available": True,
    }
