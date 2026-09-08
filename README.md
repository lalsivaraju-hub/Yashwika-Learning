# My Learning Adventure

A colourful, parent-moderated Streamlit learning companion for a young child (built for UKG / CBSE, adaptable to any grade).

## What's new in this version: resilience to Streamlit Cloud's OCR infra issue

Your last deployment failed with `ModuleNotFoundError: No module named 'pytesseract'`, caused by a **known, recurring Streamlit Community Cloud infrastructure bug** where the build server's Debian package mirror (`bullseye-security`) is occasionally stale, causing `packages.txt` (which installs the system-level Tesseract OCR engine) to fail. This is a Streamlit-side issue, not a mistake in your files — it's been reported since 2023 and reappears periodically.

**Fix in this version:** OCR is now fully optional. If the Tesseract system package fails to install for any reason, the app detects this automatically and:
- Still boots and works normally
- Shows a clear, honest message that automatic text-reading is temporarily unavailable
- Keeps Gemini-based generation, missions, scoring, and the Homework Helper working exactly as before
- Lets you type worksheet topics manually, or use Gemini's picture-description button instead

This means a future recurrence of that Streamlit Cloud infra issue will never again take your whole app down.

## Adaptive Gemini Engine (from the previous version, still included)
Each day, for each subject, the app builds a summary of:
- Approved worksheet uploads (OCR text + optional Gemini picture descriptions)
- Parent-typed "what she has learned so far" notes
- Recent completed missions with your star ratings and feedback

This is sent to Gemini, which invents a **brand-new**, non-repetitive exercise and recommends whether tomorrow's difficulty should increase, stay the same, or decrease — tracked as a 1–10 level per subject (visible on the Progress page). Hindi and Kannada exercises are generated in native script with an English translation alongside.

### Generation priority order (automatic fallback)
1. 🤖 **Gemini adaptive generation** (if API key configured)
2. 📚 **Approved uploads rotation** (if Gemini unavailable)
3. 🧩 **Built-in generic CBSE/UKG activity bank** (if neither available)

## Files to upload to GitHub
Upload **all of these**, at the same folder level (repo root, or one consistent subfolder):
```
app.py
gemini_helper.py
ocr_utils.py
requirements.txt
packages.txt
README.md
.gitignore
.streamlit/config.toml
```
Do **not** upload `data/` or any `.db` file — `.gitignore` already excludes them.

## Getting a free Gemini API key
1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey), sign in with a Google account, click **Create API key**. No credit card required.
2. In the app: **Parent Studio → AI Setup** → paste the key → **Test connection** → **Save**.
3. Already generated today's missions before adding the key? Click **"Regenerate today's remaining missions"** in the same tab.

**Model:** defaults to `gemini-2.5-flash` — stable and free as of September 2026. Editable in AI Setup if Google renames its free-tier lineup later.

**Free tier:** uses your own Google account's quota, no charges unless you separately enable billing. Typical free limits (~10 req/min, up to ~1,500 req/day for Flash models) comfortably cover normal daily home use.

## Run locally
```bash
pip install -r requirements.txt
# System dependency for OCR (optional, Debian/Ubuntu):
# sudo apt-get install tesseract-ocr tesseract-ocr-hin tesseract-ocr-kan
streamlit run app.py
```
Default parent PIN: `2468`. Change it immediately in Parent Studio.

## Deploy for free (Streamlit Community Cloud)
1. Push all files above to a **private** GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, deploy.
   - **Main file path:** `app.py` if files are at repo root, or `your-folder-name/app.py` if nested in a subfolder — check your repo's actual structure on GitHub.com first.
3. Streamlit reads `packages.txt` automatically for Tesseract + Hindi/Kannada language packs. If this step ever fails with a Debian "InRelease is expired" error, that's the known Streamlit Cloud infra issue described above — the app will still run, just without automatic OCR, until Streamlit's side resolves it.
4. For the Gemini key on cloud: add it as a **Secret** named `GEMINI_API_KEY` under **App settings → Secrets**, rather than typing it into the UI.

### If the app still fails to open
Click **"Manage app"** on Streamlit Cloud to see the exact error. Common causes:
- Wrong **Main file path**
- `requirements.txt`/`packages.txt` not at the same folder level as `app.py`
- Files uploaded inconsistently (some present, some missing) — redo as a single bulk upload rather than adding files one at a time

## Data & privacy
- SQLite (`data/learning.db`) and uploaded images (`data/uploads/`) stay local to wherever you run/host the app.
- Do not upload school IDs, addresses, phone numbers, medical information, or other children's faces.
- Adult supervision is recommended for all activities.
