# My Learning Adventure

A colourful, parent-moderated Streamlit learning companion for a young child (built for UKG / CBSE, adaptable to any grade).

## What's new in this version
- **Fixed:** "Today's Mission" now always shows 5 activities from day one, using a built-in generic activity bank, even with zero uploads.
- Uploaded worksheets are automatically read using OCR (Tesseract) — the app extracts printed text, detects English/Hindi/Kannada script, and suggests a topic for you to review before approving.
- **New: Gemini AI integration (optional, free).** Add a free Gemini API key in Parent Studio → AI Setup to unlock:
  - Real *picture* understanding in the Learning Library (describes illustrations, not just OCR text).
  - A brand-new **🧩 Homework Helper** tab: upload a photo of a homework question and get a step-by-step, age-appropriate explanation, a final answer to check against, a similar practice question, and an encouraging line — designed to help *you* teach the concept, not to hand your child a copy-paste answer.
- Parent Studio has a "How this works" tab explaining exactly what OCR and Gemini can and cannot do, and their limits.

## Setting up the free Gemini API key
1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey), sign in with a Google account, and click **Create API key**. No credit card is required for the free tier.
2. In the app, go to **Parent Studio → AI Setup**, paste the key, click **Test connection** to confirm it works, then **Save**.
3. That's it — the Learning Library and Homework Helper will now use Gemini.

**Model name:** defaults to `gemini-2.5-flash`, a stable free-tier vision model as of September 2026. Google renames/rotates its free model lineup every few months — if you ever see a "model not found" error, check [aistudio.google.com](https://aistudio.google.com) for the current free model name and update it in AI Setup (no code change needed).

**Free tier notes:**
- Uses your own Google account's free quota — nothing is billed unless you separately enable billing.
- Free tier limits are commonly in the range of several hundred requests per day for Flash models (Google adjusts these periodically) — normal daily home use stays well within this.
- Google's free tier may use inputs/outputs to improve their products. Avoid uploading your child's full name, school ID, address, or other children's faces.

## Run locally
```bash
pip install -r requirements.txt
# System dependency (Debian/Ubuntu): sudo apt-get install tesseract-ocr tesseract-ocr-hin tesseract-ocr-kan
streamlit run app.py
```
Default parent PIN: `2468`. Change it immediately in Parent Studio.

Note: Streamlit Community Cloud's default image already includes a Linux base;
add a `packages.txt` file with `tesseract-ocr`, `tesseract-ocr-hin`, `tesseract-ocr-kan`
so OCR works after cloud deployment (see `packages.txt` included here).

## Deploy for free
1. Push this folder to a **private** GitHub repository (data/ is git-ignored).
2. Go to share.streamlit.io, sign in with GitHub, deploy `app.py` from that repo.
3. Streamlit reads `packages.txt` automatically to install Tesseract on the cloud server.
4. For the Gemini key on cloud: instead of typing it into the app's UI (which stores it in the app's local, ephemeral database on shared hosting), add it as a **Streamlit secret** named `GEMINI_API_KEY` under App settings → Secrets. The app automatically prefers the secret over the locally stored key.

## How the "learning from worksheets" works (honest summary)
- OCR reads **printed text only** — it cannot understand illustrations, photos, or handwriting.
- It detects script/language and suggests a topic phrase from frequent words (or detected numbers for maths pages).
- You always review/edit the suggested topic before approving — nothing reaches your daughter's missions without your OK.
- If no approved uploads exist for a section, missions fall back to a built-in generic CBSE/UKG-style activity bank, so there is always something to do.

## Optional future upgrade: real picture understanding
To go beyond text extraction (e.g., understanding illustrations), connect a vision AI
model (Gemini/GPT-4o) with your own API key. This needs internet access from the
hosting environment and a small code addition — ask if you'd like this built next.

## Data & privacy
- SQLite (`data/learning.db`) and uploaded images (`data/uploads/`) stay local to wherever you run/host the app.
- Do not upload school IDs, addresses, phone numbers, medical information, or other children's faces.
- Adult supervision is recommended for all activities.
