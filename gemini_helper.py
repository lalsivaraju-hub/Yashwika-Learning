"""
gemini_helper.py
Optional integration with Google's Gemini API for real picture understanding
and homework explanation.

This module is fully optional - the rest of the app works without it, using
OCR-only topic suggestions and the built-in generic activity bank. If no API
key is configured, every function here returns a clear "not configured"
result instead of crashing the app.

SETUP (one-time, free):
1. Go to https://aistudio.google.com/apikey and sign in with a Google
   account. Click "Create API key". No credit card is required for the
   free tier.
2. Paste the key into Parent Studio -> AI Setup in the app. It is stored
   only in the app's local database (data/learning.db, which is
   git-ignored and never uploaded anywhere by this app).
   OR, for cloud deployment: add it as a Streamlit secret named
   GEMINI_API_KEY (Streamlit Cloud -> App settings -> Secrets).

MODEL NAME:
Google renames/rotates its free-tier model lineup every few months
(e.g. gemini-2.5-flash, gemini-3-flash, gemini-3.8-flash...). This module
defaults to "gemini-2.5-flash", a stable model with generous free-tier
limits as of September 2026. If Google retires it, update the model name
in Parent Studio -> AI Setup - no code change is required.

HONESTY NOTE:
- Every Gemini call uses your own free API key and free quota. Google's
  free tier may use these inputs/outputs to improve their products - avoid
  uploading anything with your child's full name, school ID, address, or
  other children's faces.
- Free tier has daily/per-minute limits (commonly ~250-500 requests/day for
  gemini-2.5-flash as of Sept 2026). This app makes at most one call per
  upload or per homework question, so normal home use should stay well
  within limits.
"""

import base64
import json

DEFAULT_MODEL = "gemini-2.5-flash"


def _get_client(api_key):
    from google import genai
    return genai.Client(api_key=api_key)


def _call_gemini(api_key, model, parts):
    """
    Calls Gemini defensively: tries the modern Interactions API first
    (google-genai SDK, late-2026 versions), and falls back to the older
    generate_content method if that call fails (e.g. an older SDK is
    installed). Returns the raw text response.
    """
    client = _get_client(api_key)

    if hasattr(client, "interactions"):
        try:
            result = client.interactions.create(model=model, input=parts)
            text = getattr(result, "output_text", None)
            if text:
                return text
        except Exception:
            pass  # fall through to the legacy call below

    contents = []
    for part in parts:
        if part["type"] == "text":
            contents.append(part["text"])
        elif part["type"] == "image":
            data = part["data"]
            if isinstance(data, str):
                data = base64.b64decode(data)
            contents.append({"mime_type": part["mime_type"], "data": data})
    response = client.models.generate_content(model=model, contents=contents)
    return response.text


def _parse_json_reply(raw):
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned.strip())


def test_connection(api_key, model=None):
    """Simple one-word ping to confirm the key/model work before relying on it."""
    if not api_key:
        return {"ok": False, "error": "No API key entered."}
    try:
        text = _call_gemini(
            api_key, model or DEFAULT_MODEL,
            [{"type": "text", "text": "Reply with exactly one word: Ready"}],
        )
        return {"ok": True, "reply": text.strip()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def describe_worksheet(api_key, model, image_bytes, mime_type, section, grade="UKG"):
    """
    Sends a worksheet photo to Gemini and asks for a plain-language
    description plus a short suggested topic and follow-up questions.
    """
    if not api_key:
        return {"ok": False, "error": "No Gemini API key configured yet."}

    prompt = (
        f"You are looking at a photo of a {section} worksheet or textbook "
        f"page used by a {grade} (age 5-6) CBSE student in India. "
        "In simple, parent-friendly language: "
        "1) Describe what is on the page in 2-3 sentences, including any "
        "pictures, letters, numbers or words visible. "
        "2) Suggest a short topic label (5-8 words). "
        "3) Suggest 2 short follow-up questions a parent could ask the "
        "child about this page. "
        'Reply strictly as JSON: {"description": "...", "topic": "...", '
        '"questions": ["...", "..."]}. No extra text outside the JSON.'
    )
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    parts = [
        {"type": "text", "text": prompt},
        {"type": "image", "data": b64, "mime_type": mime_type},
    ]
    try:
        raw = _call_gemini(api_key, model or DEFAULT_MODEL, parts)
        data = _parse_json_reply(raw)
        return {
            "ok": True,
            "description": data.get("description", ""),
            "topic": data.get("topic", ""),
            "questions": data.get("questions", []),
        }
    except json.JSONDecodeError:
        return {"ok": True, "description": raw, "topic": "", "questions": []}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def explain_homework(api_key, model, image_bytes, mime_type, section, extra_notes=""):
    """
    Sends a photo of a homework/worksheet question to Gemini and asks for
    a step-by-step, age-appropriate explanation a parent can use to teach
    the concept - not just a bare answer key.
    """
    if not api_key:
        return {"ok": False, "error": "No Gemini API key configured yet."}

    context_line = f"Extra context from the parent: {extra_notes}. " if extra_notes else ""
    prompt = (
        f"You are a warm, patient CBSE {section} tutor helping a parent "
        "teach their 5-6 year old (UKG) child at home. Look at the photo "
        "of the homework/worksheet question. " + context_line +
        "Provide, in very simple language a parent can read aloud: "
        '"question": a plain restatement of what is being asked; '
        '"steps": a list of 3-5 short, concrete steps a parent can use to '
        "GUIDE the child to the answer (use fingers, real objects, "
        "drawing, or sounding out letters - age-appropriate methods, not "
        'abstract rules or jargon); "answer": the final correct answer, '
        "clearly stated, so the parent can check the child's work; "
        '"try_next": one similar practice question to try next; '
        '"encouragement": one short, warm sentence to say to the child. '
        'Reply strictly as JSON with exactly these keys: "question", '
        '"steps" (a list), "answer", "try_next", "encouragement". No '
        "extra text outside the JSON."
    )
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    parts = [
        {"type": "text", "text": prompt},
        {"type": "image", "data": b64, "mime_type": mime_type},
    ]
    try:
        raw = _call_gemini(api_key, model or DEFAULT_MODEL, parts)
        data = _parse_json_reply(raw)
        return {"ok": True, **data}
    except json.JSONDecodeError:
        return {
            "ok": True, "question": "", "steps": [raw],
            "answer": "", "try_next": "", "encouragement": "",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
