# My Learning Adventure

A colourful, parent-moderated Streamlit learning companion for a young child (built for UKG / CBSE, adaptable to any grade).

## What's new in this version: the Adaptive Gemini Engine

Instead of only rotating a fixed activity bank, the app now builds a fresh, tailored exercise for each subject every day by combining:

- **Approved worksheet uploads** — OCR-extracted text, plus optional Gemini picture descriptions
- **Parent-typed "what she has learned so far" notes** — free-text, no file needed
- **Recent completed missions** — including your star ratings and written feedback

This whole summary is sent to Gemini, which invents a **brand-new** activity (not a repeat) and recommends whether tomorrow's difficulty should go up, stay the same, or come down. The app stores this as a simple 1–10 "level" per subject and feeds it back into the next day's prompt — a real, working feedback loop, not just a label.

**Hindi and Kannada are generated in native script** (Devanagari / Kannada), with an English translation alongside for the parent to follow.

### Generation priority order (with automatic fallback)
1. 🤖 **Gemini adaptive generation** (if API key configured) — tailored, non-repetitive
2. 📚 **Approved uploads rotation** — if Gemini is unavailable
3. 🧩 **Built-in generic CBSE/UKG activity bank** — if neither of the above is available

There is always something to do, even with zero setup.

## Setting up the free Gemini API key
1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey), sign in with a Google account, and click **Create API key**. No credit card required.
2. In the app: **Parent Studio → AI Setup** → paste the key → **Test connection** → **Save**.
3. **Already generated today's missions before adding the key?** Click **"Regenerate today's remaining missions"** in the same tab — it clears not-yet-completed missions only (points already earned are untouched) so they regenerate via Gemini immediately.

**Model name:** defaults to `gemini-2.5-flash` — confirmed stable and free as of September 2026. Google rotates its free-tier lineup periodically (e.g. `gemini-3.5-flash` also entered the free tier in mid-2026 for some accounts, while Pro-tier models moved to paid-only in April 2026). The model name is editable in AI Setup — no code change needed if Google renames things again. Check [aistudio.google.com](https://aistudio.google.com) for the current free lineup if you see a "model not found" error.

**Free tier notes:**
- Uses your own Google account's free quota — nothing is billed unless you separately enable billing.
- Typical free Flash-tier limits as of Sept 2026: ~10 requests/minute, several hundred to ~1,500 requests/day (Google adjusts these periodically) — normal daily home use (5 mission slots + occasional homework help) fits comfortably within this.
- Google's free tier may use inputs/outputs to improve their products. Avoid uploading your child's full name, school ID, address, or other children's faces.
- If you see a "quota" or "429" error, wait a few minutes and try again — the app automatically falls back to the upload-rotation or generic bank in the meantime, so nothing breaks.

## Features
- 30-minute weekday missions across English, Hindi, Kannada, Numeracy, Drawing, and Speaking & Thinking
- Custom sections you can add yourself
- Image/PDF worksheet upload library with OCR text extraction
- Optional Gemini picture understanding (not just printed text)
- **Learning Notes** — type what she's already learned; feeds directly into tomorrow's exercise
- **Homework Helper** — upload a homework photo, get a step-by-step parent-facing explanation (not a bare answer)
- Points, badges, and a per-subject adaptive difficulty level (visible on the Progress page)
- Parent PIN-gated moderation: approve/reject uploads, rate and give feedback on missions
- Local SQLite storage

## Run locally
```bash
pip install -r requirements.txt
# System dependency for OCR (Debian/Ubuntu):
# sudo apt-get install tesseract-ocr tesseract-ocr-hin tesseract-ocr-kan
streamlit run app.py
```
Default parent PIN: `2468`. Change it immediately in Parent Studio.

## Deploy for free (Streamlit Community Cloud)
1. Push this folder to a **private** GitHub repository (`data/` is git-ignored, so no personal data is ever committed).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, and deploy.
   - **Main file path:** if you uploaded this whole folder as a subfolder of your repo, enter `kids_learning_buddy/app.py`. If `app.py` sits at the repo root, enter `app.py`.
3. Streamlit automatically reads `packages.txt` to install Tesseract (+ Hindi/Kannada language packs) on the cloud server.
4. For the Gemini key on cloud: add it as a **Secret** named `GEMINI_API_KEY` under **App settings → Secrets**, instead of typing it into the UI (which stores it in the app's local, non-durable database on shared hosting). The app automatically prefers the secret over the locally stored key.

### If the app fails to open after deploying
Click **"Manage app"** on your Streamlit Cloud dashboard to see the exact build/runtime error. The most common causes are:
- Wrong **Main file path** (see step 2 above)
- `requirements.txt` or `packages.txt` not at the same folder level as `app.py`
- A typo in `packages.txt` (must be exactly `tesseract-ocr`, `tesseract-ocr-hin`, `tesseract-ocr-kan`, one per line)

## How the adaptive engine works (honest summary)
- OCR (Tesseract) reads **printed text only** — it cannot understand illustrations, photos, or handwriting.
- Gemini's picture-description feature fills that gap, but requires your API key.
- The "level" per subject is a lightweight heuristic driven by Gemini's own judgment plus your ratings/notes — not a scientifically validated learning-progression model. It works best when you regularly rate completed missions and add learning notes.
- Hindi/Kannada content is AI-generated in native script; as with any AI output, a quick parent review is recommended.

## Data & privacy
- SQLite (`data/learning.db`) and uploaded images (`data/uploads/`) stay local to wherever you run/host the app.
- Do not upload school IDs, addresses, phone numbers, medical information, or other children's faces.
- Adult supervision is recommended for all activities.
