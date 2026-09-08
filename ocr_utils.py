"""
ocr_utils.py
Automatic "reading" of uploaded worksheet images/PDFs using classic OCR.

WHAT THIS DOES:
- Uses Tesseract OCR to extract PRINTED text (English, Hindi, Kannada scripts).
- Detects the script/language from the Unicode ranges found in the text.
- Detects simple patterns (single big letter + few words -> phonics page;
  lots of digits -> numeracy page).
- Suggests a short topic phrase from frequent words.

WHAT THIS DOES NOT DO:
- Cannot understand illustrations, photos, or handwriting.
- Is not an AI model - classic text recognition + simple rules.
For real picture understanding and adaptive exercise generation, this app
also uses Gemini (see gemini_helper.py), which is far more capable and
multilingual.
"""

import re
from collections import Counter
from io import BytesIO

import pytesseract
from PIL import Image

try:
    import fitz  # PyMuPDF, used to turn PDF pages into images for OCR
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

STOPWORDS = {
    "the", "and", "a", "an", "of", "to", "in", "is", "it", "for", "on", "with",
    "this", "that", "are", "was", "were", "be", "as", "at", "by", "or", "if",
    "worksheet", "name", "date", "class", "school", "page", "chapter",
}

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
KANNADA_RE = re.compile(r"[\u0C80-\u0CFF]")
WORD_RE = re.compile(r"[A-Za-z\u0900-\u097F\u0C80-\u0CFF]{2,}")
DIGIT_RE = re.compile(r"\d")


def _ocr_image(img: Image.Image) -> str:
    try:
        return pytesseract.image_to_string(img, lang="eng+hin+kan")
    except Exception:
        return pytesseract.image_to_string(img, lang="eng")


def extract_text(file_bytes: bytes, filename: str) -> str:
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
    text = extract_text(file_bytes, filename).strip()
    return {
        "raw_text": text,
        "language_hint": detect_language_hint(text) if text else "Unknown",
        "suggested_topic": suggest_topic(text, section) if text else "",
        "word_count": len(WORD_RE.findall(text)),
    }
