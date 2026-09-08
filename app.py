"""
My Learning Adventure - a colourful, parent-moderated daily learning
companion for a young child (built for UKG / CBSE, but adaptable).

RESILIENCE DESIGN NOTE:
This app is built so that a failure in ANY optional piece (OCR/Tesseract
not installed, Gemini not configured or a Gemini call failing) never
prevents the app from loading or from generating today's missions. Each
optional feature is wrapped so it degrades gracefully to the next
fallback instead of raising an exception that would crash the whole app.
This matters in practice: Streamlit Cloud's own build infrastructure has
a known, recurring issue where packages.txt installs (like Tesseract)
can fail due to a stale upstream Debian mirror - completely outside this
app's control. Thanks to this design, that failure only disables the
OCR "read printed text automatically" feature; everything else
(Gemini-based generation, missions, scoring, homework helper) keeps
working normally.
"""

import hashlib
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st

import gemini_helper
import ocr_utils

# ----------------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------------
st.set_page_config(page_title="My Learning Adventure", page_icon="🌈", layout="wide")

DATA_DIR = Path("data")
UPLOAD_DIR = DATA_DIR / "uploads"
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "learning.db"

DEFAULT_SECTIONS = ["Literacy (English)", "Hindi", "Kannada", "Numeracy", "Drawing"]
LANGUAGE_DAY_ORDER = ["Hindi", "Kannada"]  # alternates by weekday
SECTION_TO_LANGUAGE = {
    "Literacy (English)": "English", "Hindi": "Hindi", "Kannada": "Kannada",
    "Numeracy": "English", "Drawing": "English", "Speaking & Thinking": "English",
}

NAV_TODAY = "🏠 Today's Mission"
NAV_LIBRARY = "📚 Learning Library"
NAV_HOMEWORK = "🧩 Homework Helper"
NAV_PROGRESS = "📈 Progress"
NAV_PARENT = "🛡️ Parent Studio"
NAV_OPTIONS = [NAV_TODAY, NAV_LIBRARY, NAV_HOMEWORK, NAV_PROGRESS, NAV_PARENT]

st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(135deg,#fff5fb 0%, #eef9ff 55%, #fff8d8 100%); color:#25324b; }
    .block-container { max-width: 1150px; padding-top: 1.1rem; }
    .hero { background: linear-gradient(110deg,#7657ff,#ff6fae); padding:24px; border-radius:28px;
            color:white; box-shadow:0 8px 25px rgba(118,87,255,.25); }
    .mission { background:white; border-left:9px solid #7657ff; border-radius:20px; padding:16px;
               margin:12px 0; box-shadow:0 5px 18px rgba(0,0,0,.06); }
    .source-tag { display:inline-block; background:#f0ebff; color:#5a3fd6; border-radius:999px;
                  padding:2px 10px; font-size:.78rem; font-weight:700; margin-bottom:6px; }
    .level-tag { display:inline-block; background:#eafff2; color:#1a9c5b; border-radius:999px;
                 padding:2px 10px; font-size:.78rem; font-weight:700; margin-left:6px; }
    .stButton>button { border:0; border-radius:16px; background:#7657ff; color:white; font-weight:700; }
    [data-testid='stSidebar'] { background:#fff9fd; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------------
# Generic exercise bank - the last-resort fallback, always available
# ----------------------------------------------------------------------------
GENERIC_BANK = {
    "Literacy (English)": [
        ("Phonics Hunt", "Find 3 objects at home that start with different letters. Say each letter sound out loud."),
        ("Rhyme Time", "Sing a favourite rhyme and clap along. Say 3 words that rhyme with each other."),
        ("Picture Talk", "Look at any picture book. Describe what you see in 3 full sentences."),
        ("Letter Trace", "Trace 5 letters of the alphabet in the air with your finger, then on paper."),
        ("Story Detective", "Listen to a short story. Find 3 words you know and use one in your own sentence."),
    ],
    "Numeracy": [
        ("Counting Walk", "Count 10 things you can see around the house and say the numbers out loud."),
        ("Shape Hunt", "Find something shaped like a circle, a square and a triangle at home."),
        ("Pattern Fun", "Make a repeating pattern with toys or blocks, like red-blue-red-blue."),
        ("Number Friends", "Show a number with your fingers, then show one more, then one less."),
        ("Big and Small", "Pick 5 objects and put them in order from the smallest to the biggest."),
    ],
    "Hindi": [
        ("शब्द खेल (Word Game)", "3 चीज़ों के नाम हिंदी में बोलिए और दोहराइए। (Say the names of 3 things in Hindi and repeat them.)"),
        ("रंगों की पहचान (Colours)", "घर की 3 चीज़ों के रंग हिंदी में बताइए। (Say the colour of 3 objects at home in Hindi.)"),
        ("गिनती (Counting)", "1 से 10 तक हिंदी में गिनिए। (Count from 1 to 10 in Hindi.)"),
        ("मेरा परिवार (My Family)", "अपने परिवार के 3 सदस्यों के नाम बताइए। (Say the names of 3 family members.)"),
        ("कहानी सुनो (Story Time)", "एक छोटी कहानी सुनिए और एक वाक्य दोहराइए। (Listen to a short story and repeat one sentence.)"),
    ],
    "Kannada": [
        ("ಪದ ಆಟ (Word Game)", "ಮನೆಯಲ್ಲಿರುವ 3 ವಸ್ತುಗಳ ಹೆಸರು ಕನ್ನಡದಲ್ಲಿ ಹೇಳಿ. (Say the names of 3 objects at home in Kannada.)"),
        ("ಬಣ್ಣಗಳು (Colours)", "3 ವಸ್ತುಗಳ ಬಣ್ಣ ಕನ್ನಡದಲ್ಲಿ ಹೇಳಿ. (Say the colour of 3 objects in Kannada.)"),
        ("ಎಣಿಕೆ (Counting)", "1 ರಿಂದ 10 ರವರೆಗೆ ಕನ್ನಡದಲ್ಲಿ ಎಣಿಸಿ. (Count from 1 to 10 in Kannada.)"),
        ("ನನ್ನ ಕುಟುಂಬ (My Family)", "ನಿಮ್ಮ ಕುಟುಂಬದ 3 ಸದಸ್ಯರ ಹೆಸರು ಹೇಳಿ. (Name 3 family members.)"),
        ("ಕಥೆ ಸಮಯ (Story Time)", "ಒಂದು ಸಣ್ಣ ಕಥೆ ಕೇಳಿ ಮತ್ತು ಒಂದು ವಾಕ್ಯ ಹೇಳಿ. (Listen to a short story, repeat one sentence.)"),
    ],
    "Drawing": [
        ("Free Draw", "Draw your favourite animal and give it a name."),
        ("Rainbow Colours", "Draw and colour a rainbow using at least 5 colours."),
        ("My Family", "Draw your family and say one nice thing about each person."),
        ("Weather Today", "Draw today's weather - sunny, rainy or cloudy."),
        ("Shape Picture", "Draw a picture using only circles, squares and triangles."),
    ],
    "Speaking & Thinking": [
        ("My Bright Thought", "Tell an adult what you learned today and what was easy or hard."),
        ("Favourite Things", "Say your favourite animal, food and colour, and explain why."),
        ("Odd One Out", "Adult names 3 things, 2 similar and 1 different. Child says which is different and why."),
        ("What Comes Next", "Adult starts a pattern (clap, clap, stomp...) and child continues it."),
        ("Big Imagination", "If you could fly anywhere for a day, where would you go and why?"),
    ],
}

MISSION_SLOTS = [
    ("Literacy (English)", 8, 20),
    ("Numeracy", 8, 20),
    ("__LANGUAGE__", 6, 15),
    ("Drawing", 5, 15),
    ("Speaking & Thinking", 3, 10),
]

CONTEXT_UPLOAD_LIMIT = 4
CONTEXT_MISSION_LIMIT = 8
RAW_TEXT_SNIPPET_LEN = 300


# ----------------------------------------------------------------------------
# Database helpers
# ----------------------------------------------------------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _add_column_if_missing(conn, table, column, ddl_type_and_default):
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type_and_default}")


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT, birthday TEXT, grade TEXT, interests TEXT, pin TEXT
            );
            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE
            );
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section TEXT, title TEXT, topic TEXT, raw_text TEXT,
                language_hint TEXT, path TEXT, added TEXT,
                approved INTEGER DEFAULT 0, note TEXT
            );
            CREATE TABLE IF NOT EXISTS missions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT, section TEXT, title TEXT, instructions TEXT,
                minutes INTEGER, points INTEGER, source TEXT,
                status TEXT DEFAULT 'open', rating INTEGER, feedback TEXT,
                UNIQUE(day, section, title)
            );
            CREATE TABLE IF NOT EXISTS rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                at TEXT, points INTEGER, reason TEXT
            );
            CREATE TABLE IF NOT EXISTS homework_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                at TEXT, section TEXT, path TEXT,
                question TEXT, steps TEXT, answer TEXT,
                try_next TEXT, encouragement TEXT,
                rating INTEGER, feedback TEXT
            );
            CREATE TABLE IF NOT EXISTS learning_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section TEXT, note TEXT, added_at TEXT
            );
            CREATE TABLE IF NOT EXISTS section_levels (
                section TEXT PRIMARY KEY,
                level INTEGER DEFAULT 1,
                last_topic TEXT,
                last_rationale TEXT,
                updated_at TEXT
            );
            """
        )
        if not conn.execute("SELECT 1 FROM profile WHERE id = 1").fetchone():
            conn.execute(
                "INSERT INTO profile (id, name, birthday, grade, interests, pin) "
                "VALUES (1, ?, ?, ?, ?, ?)",
                ("My Star", "2020-01-01", "UKG", "animals, colours, stories",
                 hashlib.sha256(b"2468").hexdigest()),
            )
        _add_column_if_missing(conn, "profile", "gemini_api_key", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "profile", "gemini_model",
                                f"TEXT DEFAULT '{gemini_helper.DEFAULT_MODEL}'")
        _add_column_if_missing(conn, "resources", "ai_description", "TEXT DEFAULT ''")

        for section in DEFAULT_SECTIONS:
            conn.execute("INSERT OR IGNORE INTO sections (name) VALUES (?)", (section,))


init_db()


def fetch_one(query, params=()):
    return get_conn().execute(query, params).fetchone()


def fetch_all(query, params=()):
    return get_conn().execute(query, params).fetchall()


def get_profile():
    return dict(fetch_one("SELECT * FROM profile WHERE id = 1"))


def get_sections():
    return [row["name"] for row in fetch_all("SELECT name FROM sections ORDER BY id")]


def age_years(birthday_str):
    try:
        born = date.fromisoformat(birthday_str)
        today = date.today()
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    except ValueError:
        return 6


def get_total_points():
    row = fetch_one("SELECT COALESCE(SUM(points), 0) AS total FROM rewards")
    return row["total"]


def get_badge(points):
    if points >= 1000:
        return "🏆 Learning Legend"
    if points >= 500:
        return "🚀 Super Explorer"
    if points >= 250:
        return "🌟 Rising Star"
    if points >= 100:
        return "🦋 Brave Learner"
    return "🌱 Little Sprout"


def get_ai_config():
    profile_row = get_profile()
    try:
        secret_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        secret_key = ""
    api_key = secret_key or profile_row.get("gemini_api_key") or ""
    model = profile_row.get("gemini_model") or gemini_helper.DEFAULT_MODEL
    return api_key, model


def get_section_level(section):
    row = fetch_one("SELECT * FROM section_levels WHERE section = ?", (section,))
    if row:
        return dict(row)
    return {"section": section, "level": 1, "last_topic": "", "last_rationale": "", "updated_at": ""}


def update_section_level(section, difficulty_next, topic_covered, rationale):
    current = get_section_level(section)
    level = current["level"]
    if difficulty_next == "increase":
        level = min(level + 1, 10)
    elif difficulty_next == "decrease":
        level = max(level - 1, 1)
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO section_levels (section, level, last_topic, last_rationale, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(section) DO UPDATE SET
                 level=excluded.level, last_topic=excluded.last_topic,
                 last_rationale=excluded.last_rationale, updated_at=excluded.updated_at""",
            (section, level, topic_covered, rationale, datetime.now().isoformat(timespec="seconds")),
        )


# ----------------------------------------------------------------------------
# Adaptive learning context builder
# ----------------------------------------------------------------------------
def build_learning_context(section):
    parts = []

    uploads = fetch_all(
        "SELECT * FROM resources WHERE section = ? AND approved = 1 ORDER BY id DESC LIMIT ?",
        (section, CONTEXT_UPLOAD_LIMIT),
    )
    if uploads:
        parts.append("Approved worksheets covered so far:")
        for u in uploads:
            snippet = (u["raw_text"] or "").strip().replace("\n", " ")[:RAW_TEXT_SNIPPET_LEN]
            line = f"- Topic: {u['topic']}"
            if u["ai_description"]:
                line += f" | Picture description: {u['ai_description']}"
            if snippet:
                line += f" | Text on page: {snippet}"
            parts.append(line)

    notes = fetch_all(
        "SELECT * FROM learning_notes WHERE section = ? ORDER BY id DESC LIMIT 10", (section,)
    )
    if notes:
        parts.append("\nParent notes on what she has learned / can already do:")
        for n in notes:
            parts.append(f"- ({n['added_at'][:10]}) {n['note']}")

    history = fetch_all(
        """SELECT * FROM missions WHERE section = ? AND status = 'done'
           ORDER BY id DESC LIMIT ?""",
        (section, CONTEXT_MISSION_LIMIT),
    )
    if history:
        parts.append("\nRecent completed activities in this subject:")
        for m in history:
            line = f"- {m['title']}"
            if m["rating"]:
                line += f" (parent rating: {m['rating']}/5)"
            if m["feedback"]:
                line += f" - parent feedback: {m['feedback']}"
            parts.append(line)

    return "\n".join(parts)


def try_generate_gemini_mission(section, minutes, points, day_seed):
    api_key, model = get_ai_config()
    if not api_key:
        return None

    language = SECTION_TO_LANGUAGE.get(section, "English")
    context = build_learning_context(section)
    level_info = get_section_level(section)

    result = gemini_helper.generate_exercise(
        api_key, model, section, language, context, minutes, points, level_info["level"]
    )
    if not result.get("ok"):
        return None

    title = result["title"]
    instructions = result["instructions"]
    if not title or not instructions:
        return None

    update_section_level(
        section, result.get("difficulty_next", "same"),
        result.get("topic_covered", ""), result.get("rationale", ""),
    )
    source = f"🤖 Gemini • tailored to level {get_section_level(section)['level']}/10"
    return title, instructions, source


def pick_from_generic(section, seed):
    bank = GENERIC_BANK.get(section, [])
    if not bank:
        return None
    title, instructions = bank[seed % len(bank)]
    return title, instructions, "Built-in activity bank"


def pick_from_uploads(section, seed):
    approved = fetch_all(
        "SELECT * FROM resources WHERE section = ? AND approved = 1 ORDER BY id", (section,)
    )
    if not approved:
        return None
    row = approved[seed % len(approved)]
    topic = row["topic"] or "your uploaded worksheet"
    title = f"Practice: {topic}"
    instructions = (
        f"Based on '{row['title']}'. Look at the page again with an adult, "
        f"talk about {topic}, and try 2-3 small questions or examples about it out loud."
    )
    return title, instructions, f"From your upload: {row['title']}"


def build_todays_missions(day):
    day_str = day.isoformat()
    seed = day.toordinal()
    language_for_day = LANGUAGE_DAY_ORDER[day.weekday() % 2]

    slots_needed = []
    for section_key, minutes, points in MISSION_SLOTS:
        section = language_for_day if section_key == "__LANGUAGE__" else section_key
        existing = fetch_one(
            "SELECT 1 FROM missions WHERE day = ? AND section = ?", (day_str, section)
        )
        if not existing:
            slots_needed.append((section, minutes, points))

    generated = []
    for section, minutes, points in slots_needed:
        result = (
            try_generate_gemini_mission(section, minutes, points, seed)
            or pick_from_uploads(section, seed)
            or pick_from_generic(section, seed)
        )
        if result is not None:
            generated.append((section, minutes, points, result))

    if generated:
        with get_conn() as conn:
            for section, minutes, points, (title, instructions, source) in generated:
                conn.execute(
                    """INSERT OR IGNORE INTO missions
                       (day, section, title, instructions, minutes, points, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (day_str, section, title, instructions, minutes, points, source),
                )


def regenerate_open_missions(day):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM missions WHERE day = ? AND status != 'done'", (day.isoformat(),)
        )


def complete_mission(mission_id, points, title):
    with get_conn() as conn:
        row = conn.execute("SELECT status FROM missions WHERE id = ?", (mission_id,)).fetchone()
        if row and row["status"] != "done":
            conn.execute("UPDATE missions SET status = 'done' WHERE id = ?", (mission_id,))
            conn.execute(
                "INSERT INTO rewards (at, points, reason) VALUES (?, ?, ?)",
                (datetime.now().isoformat(timespec="seconds"), points, title),
            )


# ----------------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------------
profile = get_profile()
total_points = get_total_points()

st.markdown(
    f"""<div class="hero"><h1>🌈 {profile['name']}'s Learning Adventure</h1>
    <p>A playful 30-minute weekday journey that grows with her.</p></div>""",
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
col1.metric("⭐ Total points", total_points)
col2.metric("🎖️ Badge", get_badge(total_points))
col3.metric("📚 Level", f"{profile['grade']} • Age {age_years(profile['birthday'])}")

with st.sidebar:
    page = st.radio("🧭 Choose a space", NAV_OPTIONS)
    st.caption("First-use parent PIN: 2468 (change it in Parent Studio).")
    ai_key_check, _ = get_ai_config()
    if ai_key_check:
        st.success("🤖 Gemini AI: connected")
    else:
        st.info("🤖 Gemini AI: not connected (Parent Studio → AI Setup)")
    if not ocr_utils.OCR_AVAILABLE:
        st.warning("🔎 OCR text-reading: unavailable on this deployment "
                   "(worksheet uploads and Gemini picture description still work)")


# ----------------------------------------------------------------------------
# Page: Today's Mission
# ----------------------------------------------------------------------------
if page == NAV_TODAY:
    today = date.today()
    if today.weekday() > 4:
        st.info("It's the weekend! Enjoy outdoor play, reading and rest. Here's a preview of Monday.")
        target_day = today + timedelta(days=7 - today.weekday())
    else:
        target_day = today

    build_todays_missions(target_day)
    missions = fetch_all(
        "SELECT * FROM missions WHERE day = ? ORDER BY id", (target_day.isoformat(),)
    )
    minutes_done = sum(m["minutes"] for m in missions if m["status"] == "done")

    st.subheader(target_day.strftime("✨ %A, %d %B") + " • 30-minute plan")
    st.progress(min(minutes_done / 30, 1.0), text=f"{minutes_done} of 30 minutes completed")

    if not missions:
        st.warning("No missions could be generated. Please check the Parent Studio settings.")

    for m in missions:
        level = get_section_level(m["section"])
        st.markdown(
            f"""<div class="mission">
            <span class="source-tag">{m['source']}</span>
            <span class="level-tag">Level {level['level']}/10</span><br/>
            <b>{m['section']} • {m['minutes']} min • +{m['points']} points</b>
            <h3>{m['title']}</h3><p>{m['instructions']}</p></div>""",
            unsafe_allow_html=True,
        )
        if m["status"] == "done":
            st.success("Completed! Great effort 🎉")
        else:
            if st.button("✅ I finished this", key=f"done_{m['id']}"):
                complete_mission(m["id"], m["points"], m["title"])
                st.rerun()

    st.caption("Adult supervision recommended. Reward effort, speaking and curiosity, not speed.")


# ----------------------------------------------------------------------------
# Page: Learning Library (upload + OCR + Gemini description + learning notes)
# ----------------------------------------------------------------------------
elif page == NAV_LIBRARY:
    st.subheader("📚 School Book & Activity Library")
    st.write(
        "Upload a photo or PDF of a worksheet. When available, the app reads "
        "printed text automatically (OCR) and, with Gemini connected, can also "
        "understand pictures. Everything approved here feeds the daily adaptive missions."
    )

    if not ocr_utils.OCR_AVAILABLE:
        st.warning(
            "🔎 Automatic text-reading (OCR) is currently unavailable on this "
            "deployment - likely a temporary system package issue on the hosting "
            "side, unrelated to your files. You can still upload worksheets and "
            "type the topic manually, or use the Gemini picture-description "
            "button below if a Gemini API key is configured."
        )

    section = st.selectbox("Section", get_sections())
    title = st.text_input("Book / worksheet name", placeholder="e.g. English Term 1, Unit 3")
    files = st.file_uploader(
        "Upload page picture(s) or a PDF",
        type=["png", "jpg", "jpeg", "webp", "pdf"],
        accept_multiple_files=True,
        key="uploader",
    )

    suggested_topic = ""
    combined_text = ""
    language_hint = ""
    ai_description = ""
    ai_key, ai_model = get_ai_config()

    if files:
        if ocr_utils.OCR_AVAILABLE:
            with st.spinner("Reading the worksheet..."):
                texts, langs = [], []
                for f in files:
                    try:
                        result = ocr_utils.analyse_upload(f.getvalue(), f.name, section)
                        texts.append(result["raw_text"])
                        langs.append(result["language_hint"])
                    except Exception as exc:
                        st.warning(f"Could not read text from {f.name} automatically ({exc}). "
                                   f"You can still type the topic manually below.")
                combined_text = "\n".join(t for t in texts if t)
                language_hint = langs[0] if langs else ""
                if combined_text:
                    suggested_topic = ocr_utils.suggest_topic(combined_text, section)

            if combined_text:
                with st.expander("🔎 What the app read from this page (tap to check accuracy)"):
                    st.text(combined_text[:1500])
                    st.caption(f"Detected language: {language_hint or 'unknown'}. "
                               "OCR reads printed text only - it cannot see pictures or handwriting.")
            else:
                st.info("No printed text was detected (normal for picture-only or handwritten "
                         "pages). Please type the topic manually below, or use Gemini below.")

        st.markdown("---")
        if not ai_key:
            st.caption("💡 Tip: add a free Gemini API key in Parent Studio → AI Setup "
                       "so the app can also understand **pictures and illustrations**, "
                       "not just printed text.")
        else:
            if st.button("🤖 Let Gemini describe this picture too", key="gemini_describe"):
                with st.spinner("Asking Gemini to look at the picture..."):
                    result = gemini_helper.describe_worksheet(
                        ai_key, ai_model, files[0].getvalue(),
                        files[0].type or "image/jpeg", section, profile["grade"]
                    )
                if result["ok"]:
                    ai_description = result.get("description", "")
                    st.success("Gemini's description:")
                    st.write(ai_description)
                    if result.get("questions"):
                        st.caption("Suggested questions to ask your child:")
                        for q in result["questions"]:
                            st.write(f"- {q}")
                    if result.get("topic"):
                        suggested_topic = result["topic"]
                        st.info(f"Suggested topic updated to: **{suggested_topic}**")
                else:
                    st.error(f"Gemini couldn't process this image: {result.get('error')}")

    topic = st.text_input(
        "Topic (auto-suggested from the worksheet - please review and edit)",
        value=suggested_topic,
        placeholder="e.g. letter B, numbers 1-20, colours in Hindi",
    )

    if st.button("📥 Save for parent review"):
        if not files or not topic.strip():
            st.error("Please add at least one file and confirm a topic before saving.")
        else:
            folder = UPLOAD_DIR / section.replace("/", "_")
            folder.mkdir(parents=True, exist_ok=True)
            with get_conn() as conn:
                for f in files:
                    safe_name = "".join(ch for ch in f.name if ch.isalnum() or ch in "._-")
                    stamped = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{safe_name}"
                    path = folder / stamped
                    path.write_bytes(f.getbuffer())
                    conn.execute(
                        """INSERT INTO resources
                           (section, title, topic, raw_text, language_hint, ai_description, path, added)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (section, title or f.name, topic, combined_text, language_hint,
                         ai_description, str(path), datetime.now().isoformat(timespec="seconds")),
                    )
            st.success("Saved! A parent must approve it in Parent Studio before it "
                       "shapes daily missions.")
            st.rerun()

    st.divider()
    st.subheader("📝 What has she learned so far?")
    st.write(
        "Type anything you know she can already do - this is used directly by Gemini "
        "to avoid repeating things and to pick the right difficulty. No file needed."
    )
    note_section = st.selectbox("Which section is this note about?", get_sections(), key="note_section")
    note_text = st.text_area(
        "Learning note", key="note_text",
        placeholder="e.g. She can count 1-20 confidently and knows 5 colours in Hindi, "
                    "but mixes up 'b' and 'd' sometimes.",
    )
    if st.button("💾 Save learning note"):
        if not note_text.strip():
            st.error("Please type a short note first.")
        else:
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO learning_notes (section, note, added_at) VALUES (?, ?, ?)",
                    (note_section, note_text.strip(), datetime.now().isoformat(timespec="seconds")),
                )
            st.success("Saved.")
            st.rerun()

    existing_notes = fetch_all(
        "SELECT * FROM learning_notes WHERE section = ? ORDER BY id DESC LIMIT 10", (note_section,)
    )
    if existing_notes:
        st.caption(f"Recent notes for {note_section}:")
        for n in existing_notes:
            note_col, del_col = st.columns([6, 1])
            note_col.write(f"• ({n['added_at'][:10]}) {n['note']}")
            if del_col.button("🗑️", key=f"delnote_{n['id']}"):
                with get_conn() as conn:
                    conn.execute("DELETE FROM learning_notes WHERE id = ?", (n["id"],))
                st.rerun()

    st.divider()
    st.subheader("Approved topics currently guiding missions")
    approved = fetch_all("SELECT * FROM resources WHERE approved = 1 ORDER BY id DESC")
    if not approved:
        st.caption("None yet - daily missions are using Gemini generation (if connected) "
                   "or the built-in generic activity bank.")
    for r in approved[:20]:
        st.write(f"✅ **{r['section']}** • {r['topic']}")


# ----------------------------------------------------------------------------
# Page: Homework Helper (Gemini vision -> step-by-step explanation)
# ----------------------------------------------------------------------------
elif page == NAV_HOMEWORK:
    st.subheader("🧩 Homework Helper")
    st.write(
        "Upload a photo of a homework question your child is stuck on. "
        "Gemini will explain **how to guide your child to the answer**, "
        "step by step - not just hand you the final answer."
    )

    ai_key, ai_model = get_ai_config()
    if not ai_key:
        st.warning(
            "No Gemini API key is configured yet. Go to **Parent Studio → AI Setup** "
            "to add a free key from Google AI Studio (no credit card needed), "
            "then come back here."
        )
    else:
        hw_section = st.selectbox(
            "Subject", get_sections(), key="hw_section",
            help="Choose the subject this homework question belongs to."
        )
        hw_notes = st.text_input(
            "Anything the app should know? (optional)",
            placeholder="e.g. she gets confused with 'borrowing' in subtraction",
        )
        hw_file = st.file_uploader(
            "Upload the homework question (photo)",
            type=["png", "jpg", "jpeg", "webp"], key="hw_uploader",
        )

        if hw_file and st.button("🤖 Explain this to me"):
            with st.spinner("Gemini is working through the question..."):
                result = gemini_helper.explain_homework(
                    ai_key, ai_model, hw_file.getvalue(),
                    hw_file.type or "image/jpeg", hw_section, hw_notes,
                )
            if not result.get("ok"):
                st.error(f"Gemini couldn't process this image: {result.get('error')}")
            else:
                folder = UPLOAD_DIR / "_homework"
                folder.mkdir(parents=True, exist_ok=True)
                safe_name = "".join(ch for ch in hw_file.name if ch.isalnum() or ch in "._-")
                stamped = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{safe_name}"
                saved_path = folder / stamped
                saved_path.write_bytes(hw_file.getbuffer())

                steps = result.get("steps") or []
                with get_conn() as conn:
                    conn.execute(
                        """INSERT INTO homework_log
                           (at, section, path, question, steps, answer, try_next, encouragement)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (datetime.now().isoformat(timespec="seconds"), hw_section, str(saved_path),
                         result.get("question", ""), "\n".join(steps), result.get("answer", ""),
                         result.get("try_next", ""), result.get("encouragement", "")),
                    )

                st.success("Here's how to guide her through it:")
                if result.get("question"):
                    st.markdown(f"**What it's asking:** {result['question']}")
                if steps:
                    st.markdown("**Steps to guide your child:**")
                    for i, step in enumerate(steps, 1):
                        st.markdown(f"{i}. {step}")
                if result.get("answer"):
                    st.markdown(f"**✅ Answer (for you to check):** {result['answer']}")
                if result.get("try_next"):
                    st.markdown(f"**🔁 Try next:** {result['try_next']}")
                if result.get("encouragement"):
                    st.info(f"💬 Say to her: \"{result['encouragement']}\"")

    st.divider()
    st.subheader("Recent homework explanations")
    history = fetch_all("SELECT * FROM homework_log ORDER BY id DESC LIMIT 10")
    if not history:
        st.caption("No homework explained yet.")
    for h in history:
        with st.expander(f"{h['at'][:16]} • {h['section']} • {(h['question'] or '')[:60]}"):
            if h["steps"]:
                st.markdown("**Steps:**")
                for line in h["steps"].split("\n"):
                    st.write(f"- {line}")
            if h["answer"]:
                st.markdown(f"**Answer:** {h['answer']}")
            if h["try_next"]:
                st.markdown(f"**Try next:** {h['try_next']}")

    st.caption(
        "This tool explains method and reasoning so you can teach the concept. "
        "It works best as a guide for the parent, read aloud or paraphrased for the child, "
        "rather than letting the child submit AI-written answers as their own homework."
    )


# ----------------------------------------------------------------------------
# Page: Progress
# ----------------------------------------------------------------------------
elif page == NAV_PROGRESS:
    st.subheader("📈 Progress & Encouragement")
    history = fetch_all(
        """SELECT day, COUNT(*) AS tasks, SUM(status = 'done') AS completed,
                  SUM(CASE WHEN status = 'done' THEN points ELSE 0 END) AS points
           FROM missions GROUP BY day ORDER BY day DESC LIMIT 30"""
    )
    if history:
        st.dataframe([dict(r) for r in history], width="stretch", hide_index=True)
    else:
        st.info("Complete the first mission to begin tracking progress.")

    st.markdown(f"### {get_badge(total_points)}")
    st.progress(min(total_points / 1000, 1.0), text=f"{total_points}/1000 points toward Learning Legend")

    st.divider()
    st.subheader("🎚️ Current adaptive difficulty by subject")
    levels = fetch_all("SELECT * FROM section_levels ORDER BY section")
    if not levels:
        st.caption("No adaptive levels yet - complete a few Gemini-generated missions first.")
    for lv in levels:
        st.write(f"**{lv['section']}** — Level {lv['level']}/10")
        if lv["last_rationale"]:
            st.caption(f"Gemini's note: {lv['last_rationale']}")


# ----------------------------------------------------------------------------
# Page: Parent Studio
# ----------------------------------------------------------------------------
else:
    st.subheader("🛡️ Parent Studio")
    pin_input = st.text_input("Parent PIN", type="password")

    if hashlib.sha256(pin_input.encode()).hexdigest() != profile["pin"]:
        st.warning("Enter the parent PIN to manage profile, sections, uploads and feedback.")
    else:
        tab_profile, tab_sections, tab_moderate, tab_feedback, tab_ai, tab_how = st.tabs(
            ["Profile", "Sections", "Moderate uploads", "Feedback", "AI Setup", "How this works"]
        )

        with tab_profile:
            with st.form("profile_form"):
                name = st.text_input("Display name", profile["name"])
                birthday = st.date_input("Birthday", date.fromisoformat(profile["birthday"]))
                grade = st.text_input("Grade", profile["grade"])
                interests = st.text_input("Interests", profile["interests"])
                new_pin = st.text_input("New PIN (leave blank to keep current)", type="password")
                if st.form_submit_button("Save"):
                    hashed_pin = profile["pin"] if not new_pin else hashlib.sha256(new_pin.encode()).hexdigest()
                    with get_conn() as conn:
                        conn.execute(
                            "UPDATE profile SET name=?, birthday=?, grade=?, interests=?, pin=? WHERE id=1",
                            (name, birthday.isoformat(), grade, interests, hashed_pin),
                        )
                    st.success("Profile updated.")
                    st.rerun()

        with tab_sections:
            new_section = st.text_input("New section name", placeholder="EVS, Music, Phonics...")
            if st.button("➕ Add section") and new_section.strip():
                with get_conn() as conn:
                    conn.execute("INSERT OR IGNORE INTO sections (name) VALUES (?)", (new_section.strip(),))
                st.rerun()
            st.write("Current sections:", ", ".join(get_sections()))

        with tab_moderate:
            pending = fetch_all("SELECT * FROM resources WHERE approved = 0 ORDER BY id DESC")
            if not pending:
                st.info("Nothing waiting for review.")
            for r in pending:
                with st.expander(f"{r['section']} • {r['topic']}"):
                    st.write(f"**{r['title']}**")
                    if r["raw_text"]:
                        st.caption("Text the app read from this page:")
                        st.text(r["raw_text"][:800])
                    if r["ai_description"]:
                        st.caption("Gemini's picture description:")
                        st.write(r["ai_description"])
                    note = st.text_area("Moderation note", key=f"note_{r['id']}")
                    approve_col, reject_col = st.columns(2)
                    if approve_col.button("Approve", key=f"approve_{r['id']}"):
                        with get_conn() as conn:
                            conn.execute(
                                "UPDATE resources SET approved=1, note=? WHERE id=?", (note, r["id"])
                            )
                        st.rerun()
                    if reject_col.button("Reject & remove", key=f"reject_{r['id']}"):
                        Path(r["path"]).unlink(missing_ok=True)
                        with get_conn() as conn:
                            conn.execute("DELETE FROM resources WHERE id=?", (r["id"],))
                        st.rerun()

        with tab_feedback:
            recent = fetch_all("SELECT * FROM missions ORDER BY day DESC, id DESC LIMIT 30")
            for m in recent:
                with st.expander(f"{m['day']} • {m['title']} • {m['status']}"):
                    rating = st.slider("Parent rating", 1, 5, m["rating"] or 3, key=f"rating_{m['id']}")
                    feedback = st.text_area(
                        "Feedback", value=m["feedback"] or "", key=f"feedback_{m['id']}",
                        placeholder="Too easy, too hard, she enjoyed this, needs more speaking practice...",
                    )
                    if st.button("Save feedback", key=f"save_feedback_{m['id']}"):
                        with get_conn() as conn:
                            conn.execute(
                                "UPDATE missions SET rating=?, feedback=? WHERE id=?",
                                (rating, feedback, m["id"]),
                            )
                        st.success("Saved. This feeds directly into tomorrow's Gemini-generated exercise.")

        with tab_ai:
            st.markdown(
                "Add a **free** Gemini API key to unlock:\n"
                "- Adaptive, freshly-generated daily exercises (not repeats)\n"
                "- Real picture understanding in the Learning Library\n"
                "- The Homework Helper, step-by-step explanations\n"
                "- Hindi and Kannada exercise generation in native script\n\n"
                "Get a free key (no credit card) at "
                "[aistudio.google.com/apikey](https://aistudio.google.com/apikey)."
            )
            current_key = profile.get("gemini_api_key") or ""
            masked = f"{'•' * max(len(current_key) - 4, 0)}{current_key[-4:]}" if current_key else "(not set)"
            st.caption(f"Current stored key: {masked}")

            with st.form("ai_setup_form"):
                new_key = st.text_input(
                    "Gemini API key", type="password",
                    placeholder="Paste your key here (starts with AIza...)",
                )
                new_model = st.text_input(
                    "Model name", value=profile.get("gemini_model") or gemini_helper.DEFAULT_MODEL,
                    help="Google renames free-tier models periodically. 'gemini-2.5-flash' is "
                         "a stable free choice as of Sept 2026. If you get a 'model not found' "
                         "error, check aistudio.google.com for the current free model name.",
                )
                save_col, test_col = st.columns(2)
                saved = save_col.form_submit_button("💾 Save")
                tested = test_col.form_submit_button("🔎 Test connection")

                if saved:
                    with get_conn() as conn:
                        conn.execute(
                            "UPDATE profile SET gemini_api_key=?, gemini_model=? WHERE id=1",
                            (new_key or current_key, new_model or gemini_helper.DEFAULT_MODEL),
                        )
                    st.success("Saved. Reloading...")
                    st.rerun()

                if tested:
                    key_to_test = new_key or current_key
                    if not key_to_test:
                        st.error("Enter a key first.")
                    else:
                        with st.spinner("Contacting Gemini..."):
                            result = gemini_helper.test_connection(
                                key_to_test, new_model or gemini_helper.DEFAULT_MODEL
                            )
                        if result["ok"]:
                            st.success(f"It works! Gemini replied: {result['reply']}")
                        else:
                            st.error(f"Connection failed: {result['error']}")

            st.markdown("---")
            st.caption(
                "**Already generated today's missions before adding this key?** "
                "Today's Mission only generates each slot once per day. Use the "
                "button below to clear any not-yet-completed missions for today "
                "so they regenerate using Gemini right away. Completed missions "
                "and points already earned are kept safe."
            )
            if st.button("🔄 Regenerate today's remaining missions"):
                regenerate_open_missions(date.today())
                st.success("Done. Open 'Today's Mission' to see the refreshed activities.")

            st.caption(
                "The key is stored only in this app's local database "
                "(data/learning.db), which is excluded from Git via .gitignore. "
                "On Streamlit Community Cloud, prefer adding it as a Secret named "
                "GEMINI_API_KEY instead (App settings → Secrets) - secrets take "
                "priority over the locally stored key automatically."
            )

        with tab_how:
            ocr_status = "✅ available" if ocr_utils.OCR_AVAILABLE else f"⚠️ unavailable ({ocr_utils.OCR_UNAVAILABLE_REASON})"
            st.markdown(
                f"""
### How "Today's Mission" is generated (in priority order)
For each of the 5 daily slots, the app tries:
1. **Gemini adaptive generation** (if an API key is configured) - see below.
2. **Approved uploads rotation** - if Gemini is unavailable, cycles through
   your approved worksheets for that subject.
3. **Built-in generic activity bank** - if neither of the above is
   available, uses a small set of generic CBSE/UKG-style activities so
   there is always something to do.

### How the adaptive Gemini engine actually works
Every time a mission is generated, the app builds a plain-text summary
of everything it knows about your child's progress **in that specific
subject**: approved worksheet topics (with OCR text and/or Gemini
picture descriptions), your typed learning notes, and her recent
completed missions with your star ratings and feedback. This is sent to
Gemini along with a **level (1-10)** tracked per subject. Gemini invents
a brand-new activity for that level and recommends whether tomorrow's
level should go up, stay the same, or go down - stored and reused the
next time. Your ratings and notes genuinely change what she gets
tomorrow.

**Honesty note:** the "level" is a lightweight heuristic, not a
scientifically validated learning-progression model. It works best when
you regularly rate completed missions and add learning notes.

### Hindi and Kannada
Gemini has strong multilingual support for Indian languages. Hindi and
Kannada activities are generated in native script (Devanagari / Kannada)
with an English translation for the parent. Please review AI-generated
language content - a parent's judgement is the final check.

### OCR (automatic text-reading) status on this deployment: {ocr_status}
OCR (Tesseract) reads **printed text only** - never illustrations,
photos, or handwriting - and requires a system-level package that
Streamlit Cloud installs via `packages.txt`. If that system package
fails to install (a known, occasionally recurring Streamlit Cloud
infrastructure issue unrelated to this app's code), OCR is simply
skipped - everything else, including Gemini picture description and
adaptive generation, keeps working normally.

### Free tier reality check
Gemini's free tier (via your own API key) has daily/per-minute limits
that Google adjusts periodically. Normal home use - a handful of calls
per day - comfortably fits within free limits as of September 2026. A
"quota" or "429" error means you've briefly hit a rate limit - wait a
few minutes and try again.
                """
            )
