import streamlit as st
import sqlite3, hashlib, random
from pathlib import Path
from datetime import date, datetime, timedelta
st.set_page_config(page_title="My Learning Adventure",page_icon="🌈",layout="wide")
D=Path("data"); U=D/"uploads"; D.mkdir(exist_ok=True); U.mkdir(exist_ok=True); DB=D/"learning.db"
DEFAULT=["Literacy (English)","Hindi","Kannada","Numeracy","Drawing"]
st.markdown("""<style>.stApp{background:linear-gradient(135deg,#fff5fb,#eef9ff,#fff8d8);color:#25324b}.block-container{max-width:1150px}.hero{background:linear-gradient(110deg,#7657ff,#ff6fae);padding:24px;border-radius:28px;color:white;box-shadow:0 8px 25px #7657ff33}.mission{background:white;border-left:9px solid #7657ff;border-radius:20px;padding:15px;margin:11px 0;box-shadow:0 5px 18px #0001}.stButton>button{border:0;border-radius:16px;background:#7657ff;color:white;font-weight:700}[data-testid='stSidebar']{background:#fff9fd}</style>""",unsafe_allow_html=True)
def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init():
 with db() as c:
  c.executescript("""CREATE TABLE IF NOT EXISTS profile(id INTEGER PRIMARY KEY,name TEXT,birthday TEXT,grade TEXT,interests TEXT,pin TEXT);CREATE TABLE IF NOT EXISTS sections(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE);CREATE TABLE IF NOT EXISTS resources(id INTEGER PRIMARY KEY AUTOINCREMENT,section TEXT,title TEXT,topic TEXT,path TEXT,added TEXT,approved INTEGER DEFAULT 0,note TEXT);CREATE TABLE IF NOT EXISTS missions(id INTEGER PRIMARY KEY AUTOINCREMENT,day TEXT,section TEXT,title TEXT,instructions TEXT,minutes INTEGER,points INTEGER,status TEXT DEFAULT 'open',rating INTEGER,feedback TEXT,UNIQUE(day,section,title));CREATE TABLE IF NOT EXISTS rewards(id INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT,points INTEGER,reason TEXT);""")
  if not c.execute("SELECT 1 FROM profile").fetchone(): c.execute("INSERT INTO profile VALUES(1,?,?,?,?,?)",("My Star","2020-01-01","UKG","animals, colours, stories",hashlib.sha256(b'2468').hexdigest()))
  for s in DEFAULT:c.execute("INSERT OR IGNORE INTO sections(name) VALUES(?)",(s,))
init()
def one(q,p=()):return db().execute(q,p).fetchone()
def rows(q,p=()):return db().execute(q,p).fetchall()
def prof():return dict(one("SELECT * FROM profile WHERE id=1"))
def secs():return [x['name'] for x in rows("SELECT name FROM sections ORDER BY id")]
def age(b):
 try:
  x=date.fromisoformat(b);t=date.today();return t.year-x.year-((t.month,t.day)<(x.month,x.day))
 except:return 6
def score():return one("SELECT COALESCE(SUM(points),0) s FROM rewards")['s']
def badge(n):return "🏆 Learning Legend" if n>=1000 else "🚀 Super Explorer" if n>=500 else "🌟 Rising Star" if n>=250 else "🦋 Brave Learner" if n>=100 else "🌱 Little Sprout"
def plan(day):
 approved=rows("SELECT * FROM resources WHERE approved=1"); by={s:[] for s in secs()}
 for r in approved:by.setdefault(r['section'],[]).append(r['topic'])
 pick=lambda s,f:random.choice(by.get(s) or [f]); lang="Hindi" if day.weekday()%2==0 else "Kannada"
 items=[("Literacy (English)","Story Detective: "+pick("Literacy (English)","sounds and sight words"),"Read with an adult. Find 3 words, say their first sounds, and use one in a sentence.",8,20),("Numeracy","Number Explorer: "+pick("Numeracy","counting, shapes and patterns"),"Use toys or pencils. Solve 3 small questions and explain your thinking.",8,20),(lang,"Language Time: "+pick(lang,"two familiar words"),f"Say 3 words in {lang}, repeat them, and speak one short sentence.",6,15),("Drawing","Create & Colour: "+pick("Drawing","a happy scene"),"Draw freely, add 3 colours, and describe your picture aloud.",5,15),("Speaking & Thinking","My Bright Thought","Say what you learned, what was easy, and what you want to try again.",3,10)]
 with db() as c:
  for x in items:c.execute("INSERT OR IGNORE INTO missions(day,section,title,instructions,minutes,points) VALUES(?,?,?,?,?,?)",(day.isoformat(),)+x)
p=prof(); total=score()
st.markdown(f"<div class='hero'><h1>🌈 {p['name']}'s Learning Adventure</h1><p>A playful 30-minute weekday journey</p></div>",unsafe_allow_html=True)
a,b,c=st.columns(3);a.metric("⭐ Points",total);b.metric("🎖️ Badge",badge(total));c.metric("📚 Level",f"{p['grade']} • Age {age(p['birthday'])}")
with st.sidebar:page=st.radio("🧭 Choose a space",["🏠 Today's Mission","📚 Learning Library","📈 Progress","🛡️ Parent Studio"]);st.caption("First-use parent PIN: 2468")
if page.startswith("🏠"):
 t=date.today(); target=t if t.weekday()<5 else t+timedelta(days=7-t.weekday())
 if t.weekday()>4:st.info("Weekend: enjoy outdoor play, family reading and rest. Monday's preview is below.")
 plan(target); ms=rows("SELECT * FROM missions WHERE day=? ORDER BY id",(target.isoformat(),)); done=sum(x['minutes'] for x in ms if x['status']=='done')
 st.subheader(target.strftime("✨ %A, %d %B • 30-minute plan"));st.progress(min(done/30,1),text=f"{done} of 30 minutes completed")
 for m in ms:
  st.markdown(f"<div class='mission'><b>{m['section']} • {m['minutes']} min • +{m['points']} points</b><h3>{m['title']}</h3><p>{m['instructions']}</p></div>",unsafe_allow_html=True)
  if m['status']=='done':st.success("Completed! Great effort 🎉")
  elif st.button("✅ I finished this",key=m['id']):
   with db() as con:con.execute("UPDATE missions SET status='done' WHERE id=?",(m['id'],));con.execute("INSERT INTO rewards(at,points,reason) VALUES(?,?,?)",(datetime.now().isoformat(),m['points'],m['title']))
   st.rerun()
 st.caption("Adult supervision recommended. Reward effort, speaking and curiosity, not speed.")
elif page.startswith("📚"):
 st.subheader("📚 School Book & Activity Library");st.write("Upload page pictures or PDFs, then approve them in Parent Studio.")
 sec=st.selectbox("Section",secs());title=st.text_input("Book / worksheet name");topic=st.text_input("What does it teach?",placeholder="Letter B, numbers 1–20, Hindi colours...");fs=st.file_uploader("Pictures or PDFs",type=['png','jpg','jpeg','webp','pdf'],accept_multiple_files=True)
 if st.button("📥 Save for parent review"):
  if not fs or not topic.strip():st.error("Add a file and a topic.")
  else:
   folder=U/sec.replace('/','_');folder.mkdir(parents=True,exist_ok=True)
   with db() as con:
    for f in fs:
     safe=''.join(ch for ch in f.name if ch.isalnum() or ch in '._-');path=folder/(datetime.now().strftime('%Y%m%d%H%M%S%f')+'_'+safe);path.write_bytes(f.getbuffer());con.execute("INSERT INTO resources(section,title,topic,path,added) VALUES(?,?,?,?,?)",(sec,title or f.name,topic,str(path),datetime.now().isoformat()))
   st.success("Saved for parent approval.")
 st.subheader("Approved topics");[st.write(f"✅ **{r['section']}** • {r['topic']}") for r in rows("SELECT * FROM resources WHERE approved=1 ORDER BY id DESC")]
elif page.startswith("📈"):
 st.subheader("📈 Progress & Encouragement");data=[dict(x) for x in rows("SELECT day,COUNT(*) tasks,SUM(status='done') completed,SUM(CASE WHEN status='done' THEN points ELSE 0 END) points FROM missions GROUP BY day ORDER BY day DESC LIMIT 30")]
 if data:st.dataframe(data,use_container_width=True,hide_index=True)
 else:st.info("Complete the first mission to begin.")
 st.markdown('### '+badge(total));st.progress(min(total/1000,1),text=f"{total}/1000 points")
else:
 st.subheader("🛡️ Parent Studio");pin=st.text_input("Parent PIN",type="password")
 if hashlib.sha256(pin.encode()).hexdigest()!=p['pin']:st.warning("Enter the PIN to moderate content and settings.")
 else:
  t1,t2,t3,t4=st.tabs(["Profile","Sections","Moderate uploads","Feedback"])
  with t1:
   with st.form("profile"):
    name=st.text_input("Display name",p['name']);birth=st.date_input("Birthday",date.fromisoformat(p['birthday']));grade=st.text_input("Grade",p['grade']);interests=st.text_input("Interests",p['interests']);newpin=st.text_input("New PIN",type='password')
    if st.form_submit_button("Save"):
     hp=p['pin'] if not newpin else hashlib.sha256(newpin.encode()).hexdigest()
     with db() as con:con.execute("UPDATE profile SET name=?,birthday=?,grade=?,interests=?,pin=? WHERE id=1",(name,birth.isoformat(),grade,interests,hp))
     st.rerun()
  with t2:
   new=st.text_input("New section",placeholder="EVS, Music, Phonics...")
   if st.button("➕ Add section") and new.strip():
    with db() as con:con.execute("INSERT OR IGNORE INTO sections(name) VALUES(?)",(new.strip(),))
    st.rerun()
   st.write(', '.join(secs()))
  with t3:
   pending=rows("SELECT * FROM resources WHERE approved=0 ORDER BY id DESC")
   if not pending:st.info("Nothing pending.")
   for r in pending:
    with st.expander(f"{r['section']} • {r['topic']}"):
     note=st.text_area("Moderation note",key='n'+str(r['id']));x,y=st.columns(2)
     if x.button("Approve",key='a'+str(r['id'])):
      with db() as con:con.execute("UPDATE resources SET approved=1,note=? WHERE id=?",(note,r['id']))
      st.rerun()
     if y.button("Reject",key='r'+str(r['id'])):
      Path(r['path']).unlink(missing_ok=True)
      with db() as con:con.execute("DELETE FROM resources WHERE id=?",(r['id'],))
      st.rerun()
  with t4:
   for m in rows("SELECT * FROM missions ORDER BY day DESC,id DESC LIMIT 30"):
    with st.expander(f"{m['day']} • {m['title']} • {m['status']}"):
     rating=st.slider("Parent rating",1,5,m['rating'] or 3,key='rt'+str(m['id']));feedback=st.text_area("Feedback",m['feedback'] or '',key='f'+str(m['id']),placeholder="Too easy, too hard, enjoyed it...")
     if st.button("Save feedback",key='s'+str(m['id'])):
      with db() as con:con.execute("UPDATE missions SET rating=?,feedback=? WHERE id=?",(rating,feedback,m['id']))
      st.success("Saved")
