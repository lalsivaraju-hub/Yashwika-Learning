"""
gemini_helper.py
Optional integration with Google's Gemini API for:
  1. Real picture understanding (describing worksheet illustrations)
  2. Step-by-step homework explanations
  3. ADAPTIVE daily exercise generation, tailored to what the child has
     already learned (from uploaded worksheets, typed parent notes, and
     past mission ratings/feedback) - in English, Hindi or Kannada.

This module is fully optional - the rest of the app works without it,
using OCR-only topic suggestions and a built-in generic activity bank as
a fallback. If no API key is configured, or a call fails for any reason,
every function here returns a clear "not available" result instead of
crashing the app - the caller always falls back gracefully.

SETUP (one-time, free):
1. Go to https://aistudio.google.com/apikey and sign in with a Google
   account. Click "Create API key". No credit card is required.
2. Paste the key into Parent Studio -> AI Setup in the app.
   OR, for cloud deployment: add it as a Streamlit secret named
   GEMINI_API_KEY (Streamlit Cloud -> App settings -> Secrets).

MODEL NAME:
Google rotates its free-tier model lineup every few months. As of
September 2026, "gemini-2.5-flash" remains a stable, free-tier model
(10 requests/min, ~250-1500 requests/day on the free "Developer" tier).
Newer models such as "gemini-3.5-flash" have also entered the free tier
for some accounts, while older/Pro-tier models have moved to paid-only.
The model name is editable in Parent Studio -> AI Setup, so if Google
retires the default, you can switch models without any code change -
just check https://aistudio.google.com for what is currently free.

HONESTY NOTES:
- Every Gemini call uses your own free API key and free quota. Google's
  free tier may use these inputs/outputs to improve their products -
  avoid uploading anything with your child's full name, school ID,
  address, or other children's faces.
- Free tier limits are generous for normal home use (a handful of calls
  per day) but are NOT unlimited. If you see errors mentioning "quota" or
  "429", you have briefly hit a rate limit - wait a few minutes.
- Gemini is a general-purpose multilingual model with strong support for
  Hindi and Kannada text generation and understanding, but as with any AI
  model, always have a parent review generated Hindi/Kannada content,
  since occasional phrasing errors are possible.
"""

import base64
import json

DEFAULT_MODEL = "gemini-2.5-flash"

LANGUAGE_SCRIPT_NOTE = {
    "Hindi": "Write the child-facing text in Hindi using Devanagari script "
             "(e.g. \u0905, \u0906, \u092c). Add a short English translation in "
             "parentheses after each Hindi sentence, for the parent's benefit.",
    "Kannada": "Write the child-facing text in Kannada script "
               "(e.g. \u0c85, \u0c86, \u0cac). Add a short English translation in "
               "parentheses after each Kannada sentence, for the parent's benefit.",
    "English": "Write in simple English suitable for a 5-6 year old.",
}


def _get_client(api_key):
    from google import genai
    return genai.Client(api_key=api_key)


def _call_gemini(api_key, model, parts):
    """
    Calls Gemini defensively: tries the modern Interactions API first
    (newer google-genai SDK versions), and falls back to the older
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


def generate_exercise(api_key, model, section, language, learning_context,
                       minutes, points, level):
    """
    THE ADAPTIVE ENGINE.
    Asks Gemini to generate a brand-new, age-appropriate exercise for
    `section`, tailored to what the child has already covered (passed in
    as `learning_context`, a plain-text summary built from her approved
    worksheet uploads, parent-typed learning notes, and recent mission
    ratings/feedback - see app.py's build_learning_context()).

    `level` is a simple 1-10 integer the app maintains per section,
    nudged up/down over time based on Gemini's own "difficulty_next"
    verdict plus parent ratings. This gives the system a lightweight,
    persistent sense of "how hard should the next one be" across days,
    since each Gemini call is otherwise stateless.

    Returns a dict with: title, instructions, topic_covered,
    difficulty_next ("increase" | "same" | "decrease"), rationale
    (a short parent-facing note explaining the level choice).
    """
    if not api_key:
        return {"ok": False, "error": "No Gemini API key configured yet."}

    script_note = LANGUAGE_SCRIPT_NOTE.get(language, LANGUAGE_SCRIPT_NOTE["English"])

    prompt = f"""You are a warm, encouraging CBSE {section} tutor for a UKG
(age 5-6) child in India, planning ONE short home activity for today.

Here is everything known about this child's learning so far in {section}:
---
{learning_context or "No prior worksheet uploads or notes yet - treat this as her very first activity in this subject."}
---

Current difficulty level for {section}: {level} out of 10 (1 = just
starting, 10 = confidently advanced for her age).

Task: design ONE fresh, NEW activity (not a repeat of anything mentioned
above) for a {minutes}-minute home session, appropriately paced for
level {level}/10. {script_note}

Reply strictly as JSON with exactly these keys:
"title": a short, fun activity title (max 8 words);
"instructions": 2-4 sentences a parent can read aloud, telling the child
exactly what to do (concrete, hands-on, age-appropriate - use real
objects, fingers, drawing, or speaking, not abstract worksheets-on-paper
unless the subject needs it);
"topic_covered": a short phrase naming exactly what skill/topic this
activity practises (used to avoid repeating it tomorrow);
"difficulty_next": one of "increase", "same", or "decrease" - your
recommendation for tomorrow's level, based on how advanced her recent
history looks;
"rationale": one short sentence (parent-facing, in English) explaining
why you chose this difficulty level.
No extra text outside the JSON."""

    try:
        raw = _call_gemini(api_key, model or DEFAULT_MODEL,
                            [{"type": "text", "text": prompt}])
        data = _parse_json_reply(raw)
        difficulty_next = data.get("difficulty_next", "same")
        if difficulty_next not in ("increase", "same", "decrease"):
            difficulty_next = "same"
        return {
            "ok": True,
            "title": data.get("title", "").strip() or f"{section} Activity",
            "instructions": data.get("instructions", "").strip(),
            "topic_covered": data.get("topic_covered", "").strip(),
            "difficulty_next": difficulty_next,
            "rationale": data.get("rationale", "").strip(),
        }
    except json.JSONDecodeError:
        return {"ok": False, "error": "Gemini reply could not be understood as JSON."}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
