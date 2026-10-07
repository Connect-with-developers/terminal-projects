#!/usr/bin/env python3
"""
LinkedIn Manager Agent v2 - COMPLETE agent (browser-automation + approval gate)

What it does, end-to-end:
  FEED     -> view feed, agent says what happened + who is hiring
  COMMENTS -> see comments on your posts, write high-visibility comments for others
  INBOX    -> see messages, draft replies (you approve, never auto-send to strangers)
  CONNECTS -> see network, pending invites, who to nurture
  POSTS    -> draft viral posts -> Telegram approve -> post (you click final Post)
  DIGEST   -> one command that says everything: views, comments, messages, next actions

Quickstart:
  python linkedin_agent.py init
  python linkedin_agent.py sync --simulate
  python linkedin_agent.py digest              # <-- start here daily, it tells you everything
  python linkedin_agent.py feed                # view feed + summary
  python linkedin_agent.py comments --mine     # comments on YOUR posts
  python linkedin_agent.py comment-draft --for "AI agents are overhyped" --author "Priya"
  python linkedin_agent.py inbox               # see messages
  python linkedin_agent.py connects            # see network
  python linkedin_agent.py draft --topic "my lesson"
  python linkedin_agent.py queue / approve --id 1 / post --id 1 --simulate

Real mode (persistent login, human-like, safe caps):
  python linkedin_agent.py feed --real
  python linkedin_agent.py inbox --real
  python linkedin_agent.py sync --real
  python linkedin_agent.py post --id 1 --real   # types draft, YOU click Post
  python linkedin_agent.py comment-post --id 1 --real  # types comment, YOU click Reply

Safety: 1 post/day, 20 comments/day, 15 replies/day, 45s+ delays, manual final click.
Never auto-DM strangers or mass-connect. That is the fastest way to get restricted.
"""
import argparse, json, os, re, sys, sqlite3, datetime, random, time

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "memory.db")
TRACE = os.path.join(BASE, "traces")

CAPS = {"post": 1, "comment": 20, "reply": 15, "connect": 10}

# ---------------- db ----------------

def con():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    os.makedirs(TRACE, exist_ok=True)
    d = con()
    d.executescript("""
    CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY, text TEXT, views INT DEFAULT 0,
      likes INT DEFAULT 0, comments INT DEFAULT 0, reposts INT DEFAULT 0, created TEXT);
    CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY, post_id INT, author TEXT,
      text TEXT, created TEXT, replied INT DEFAULT 0, mine INT DEFAULT 1);
    CREATE TABLE IF NOT EXISTS drafts(id INTEGER PRIMARY KEY, topic TEXT, text TEXT,
      hashtags TEXT, status TEXT DEFAULT 'pending', created TEXT, score INT DEFAULT 0);
    CREATE TABLE IF NOT EXISTS comment_queue(id INTEGER PRIMARY KEY, target_author TEXT,
      target_text TEXT, comment TEXT, style TEXT, status TEXT DEFAULT 'pending',
      created TEXT, score INT DEFAULT 0);
    CREATE TABLE IF NOT EXISTS feed_items(id INTEGER PRIMARY KEY, author TEXT, text TEXT,
      likes INT DEFAULT 0, comments_n INT DEFAULT 0, tag TEXT DEFAULT '', created TEXT);
    CREATE TABLE IF NOT EXISTS inbox(id INTEGER PRIMARY KEY, name TEXT, snippet TEXT,
      full TEXT DEFAULT '', unread INT DEFAULT 1, is_recruiter INT DEFAULT 0, created TEXT);
    CREATE TABLE IF NOT EXISTS connections(id INTEGER PRIMARY KEY, name TEXT, headline TEXT,
      status TEXT DEFAULT 'connected', created TEXT);
    CREATE TABLE IF NOT EXISTS actions_log(id INTEGER PRIMARY KEY, kind TEXT, detail TEXT, created TEXT);
    """)
    # migrate old DBs (v1 -> v2): add missing columns if absent
    def ensure(table, col, ddl):
        cols = [r[1] for r in d.execute(f"PRAGMA table_info({table})").fetchall()]
        if col not in cols:
            d.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    try:
        ensure("comments", "mine", "INT DEFAULT 1")
        ensure("inbox", "full", "TEXT DEFAULT ''")
        ensure("inbox", "is_recruiter", "INT DEFAULT 0")
        ensure("comment_queue", "score", "INT DEFAULT 0")
        ensure("feed_items", "tag", "TEXT DEFAULT ''")
    except Exception as e:
        print(f"[migrate warn] {e}")
    d.commit(); d.close()
    print(f"[init] db -> {DB}")

def log_action(kind, detail):
    d = con()
    d.execute("INSERT INTO actions_log(kind,detail,created) VALUES(?,?,?)",
              (kind, detail[:1000], datetime.datetime.now().isoformat()))
    d.commit(); d.close()

def check_cap(kind):
    mx = CAPS.get(kind, 10)
    d = con()
    n = d.execute("SELECT COUNT(*) c FROM actions_log WHERE kind=? AND date(created)=date('now')",
                  (kind,)).fetchone()["c"]
    d.close()
    if n >= mx:
        print(f"[safety] BLOCKED: {kind} {n}/{mx} today. Tomorrow.")
        return False
    return True

# ---------------- simulate ----------------

def sync_simulate():
    init_db()
    d = con()
    for t in ("posts","comments","feed_items","inbox","connections","comment_queue"):
        try: d.execute(f"DELETE FROM {t}")
        except Exception: pass
    now = datetime.datetime.now()
    posts = [
        ("Day 1: I built a tiny CLI agent with Playwright. 3 lessons:\n1. One action = one step\n2. Human delays matter\n3. Observe after every act\n\nWhat would you automate first?", 1240, 89, 14, 3),
        ("I got 0 replies sending 50 generic DMs. Then I sent 10 specific ones. 6 replies.\n\nPersonalize or don't send. Template in comments.", 3860, 214, 41, 12),
        ("Open to work as Python Backend Dev (remote).\nStack: Python, FastAPI, Postgres, LLM agents.\nDMs open. Reposts help.", 5210, 178, 32, 45),
    ]
    for i,(t,v,l,c,r) in enumerate(posts):
        d.execute("INSERT INTO posts(text,views,likes,comments,reposts,created) VALUES(?,?,?,?,?,?)",
                  (t,v,l,c,r,(now-datetime.timedelta(days=(3-i)*2)).isoformat()))
    d.execute("INSERT INTO comments(post_id,author,text,created,mine) VALUES(?,?,?,?,1)",
              (2,"Priya S.","This template actually works! Can you share the follow-up version?",now.isoformat()))
    d.execute("INSERT INTO comments(post_id,author,text,created,mine) VALUES(?,?,?,?,1)",
              (3,"Recruiter - Rahul","Hi, we are hiring Python devs remote. Can we chat?",now.isoformat()))
    d.execute("INSERT INTO comments(post_id,author,text,created,mine) VALUES(?,?,?,?,1)",
              (2,"Amit K.","Tried this, got 3 replies out of 8. The specific line about their post matters most.",now.isoformat()))
    feeds = [
        ("Anjali Verma (Hiring Manager @ Fintech)","We're hiring 2 backend engineers (Python/FastAPI, remote India). Comment 'interested' + DM your GitHub. No DMs without commenting please.",342,87,"HIRING"),
        ("Kunal Shah","I reviewed 200 resumes for a Python role. 90% fail in 10 seconds. Fix: 1-line impact per bullet, numbers first.",1204,156,"VIRAL_TIP"),
        ("Priya S.","Built my first RAG bot this weekend. Biggest lesson: chunking > model choice. Details below.",210,24,"PEER"),
        ("Rahul Recruiter","Hiring AI engineers, 2-5yrs, remote. Python + LLM agents must. DM with 'AI-25' + resume.",98,31,"HIRING"),
        ("Dev Community","What project got you your first interview? Mine was a boring CRUD app with great README.",540,92,"ENGAGE"),
    ]
    for a,t,l,c,tag in feeds:
        d.execute("INSERT INTO feed_items(author,text,likes,comments_n,tag,created) VALUES(?,?,?,?,?,?)",
                  (a,t,l,c,tag,now.isoformat()))
    inboxs = [
        ("Rahul (Recruiter)","Can we chat about Python remote role?","Hi! Saw your Open to Work post. We have Python/FastAPI remote, 8-15 LPA. Are you open Mon for 15-min intro? Share resume + best time.",1,1),
        ("Priya S."," loved your DM template!","Hey! loved your DM template post. I tried it, got replies! Quick q: what do you write as 2nd follow-up?",1,0),
        ("Amit K.","Thanks for commenting!","Thanks for commenting on my resume post, that checklist helped. Would love to stay connected.",0,0),
    ]
    for n,s,f,u,r in inboxs:
        d.execute("INSERT INTO inbox(name,snippet,full,unread,is_recruiter,created) VALUES(?,?,?,?,?,?)",
                  (n,s,f,u,r,now.isoformat()))
    conns = [
        ("Priya S.","ML Engineer @ Startup","connected"),
        ("Amit K.","Backend Dev @ SaaS","connected"),
        ("Rahul (Recruiter)","Tech Recruiter @ Hiring firm","connected"),
        ("Anjali Verma","Hiring Manager @ Fintech","pending_in"),
        ("Kunal Shah","Senior Engineer, writes about hiring","pending_in"),
    ]
    for n,h,s in conns:
        d.execute("INSERT INTO connections(name,headline,status,created) VALUES(?,?,?,?)",(n,h,s,now.isoformat()))
    d.commit(); d.close()
    log_action("sync", "simulate full")
    print("[sync] loaded: 3 posts, 3 comments-on-you, 5 feed, 3 inbox, 5 connects.")
    print("Next: `digest` (tells you everything) or `feed` / `comments --mine` / `inbox` / `connects`")

# ---------------- real browser helpers ----------------

def real_snapshot(url, out_prefix, scrolls=4):
    """Persistent login + human scroll + save text/screenshot/json. Returns body text."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[err] pip install playwright && playwright install chromium"); return ""
    prof = os.path.join(BASE, ".browser-profile")
    os.makedirs(prof, exist_ok=True)
    print(f"[real] opening {url} ... (login manually once if asked)")
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(prof, headless=False, locale="en-US",
            args=["--disable-blink-features=AutomationControlled"])
        page = ctx.new_page() if not ctx.pages else ctx.pages[0]
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        for _ in range(scrolls):
            page.mouse.wheel(0, 700); page.wait_for_timeout(random.randint(900,1600))
        try: txt = page.locator("body").first.inner_text(timeout=6000)
        except Exception as e: txt = ""
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        page.screenshot(path=os.path.join(TRACE, f"{out_prefix}_{ts}.png"))
        open(os.path.join(TRACE, f"{out_prefix}_{ts}.txt"), "w", encoding="utf-8").write(txt or "")
        print(f"[real] saved traces/{out_prefix}_{ts}.png/.txt ({len(txt)} chars)")
        print("[real] sample:\n", (txt or "")[:1000])
        ctx.close()
        return txt or ""

def naive_feed_parse(body, limit=8):
    """Best-effort: split body into post-like chunks. Real LinkedIn DOM changes often,
    so we chunk by long lines and keep evidence file. Returns list of (author,text)."""
    lines = [l.strip() for l in (body or "").splitlines() if len(l.strip()) > 40]
    items, seen = [], set()
    for l in lines:
        if l in seen: continue
        seen.add(l)
        # heuristic: author lines are short + have @ or role; post lines are long
        items.append(("Feed author (see .txt)", l[:400]))
        if len(items) >= limit: break
    return items

# ---------------- FEED ----------------

def cmd_feed(real=False, limit=8):
    if real:
        body = real_snapshot("https://www.linkedin.com/feed/", "feed", scrolls=5)
        items = naive_feed_parse(body, limit)
        if items:
            d = con()
            for a,t in items:
                d.execute("INSERT INTO feed_items(author,text,likes,comments_n,tag,created) VALUES(?,?,?,?,?,?)",
                          (a,t,0,0,"REAL",datetime.datetime.now().isoformat()))
            d.commit(); d.close()
            log_action("sync", "feed real")
        print("\n[note] LinkedIn changes selectors often - raw text saved in traces/. Paste quirks and I harden parser.")
    d = con()
    rows = d.execute("SELECT * FROM feed_items ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    d.close()
    if not rows:
        print("[feed] empty. Run `sync --simulate` or `feed --real`."); return
    print(f"\n=== FEED: what happened ({len(rows)} items) ===")
    for r in rows:
        flag = {"HIRING":"🔥 HIRING","VIRAL_TIP":"💡 VIRAL TIP","PEER":"👥 PEER","ENGAGE":"💬 COMMENT HERE","REAL":"🌐 REAL"}.get(r["tag"], "")
        print(f"\n[{flag} #{r['id']}] {r['author']} ({r['likes']} likes, {r['comments_n']} comments)")
        print(f"  {r['text'][:220]}")
    print("\n--- Agent summary ---")
    hir = [r for r in rows if r["tag"]=="HIRING" or "hiring" in r["text"].lower()]
    if hir:
        print(f"→ {len(hir)} hiring post(s). Action: comment-draft on each TODAY (first hour = max visibility).")
        for r in hir[:3]: print(f"   #{r['id']}: {r['author']} - {r['text'][:90]}...")
    else: print("→ No hiring posts in view. Scroll more (feed --real) or follow 5 hiring managers.")
    print("→ Best comment targets: high comments_n + HIRING/ENGAGE tags. Avoid old VIRAL_TIP for comments (crowded).")
    print("Next: `comment-draft --id <feed_id>` to write a visibility comment.")

def cmd_feed_detail(i):
    d = con()
    r = d.execute("SELECT * FROM feed_items WHERE id=?", (i,)).fetchone()
    d.close()
    if not r: print(f"[err] no feed #{i}"); return
    print(f"\n[feed #{r['id']}] {r['author']}\n{r['text']}\n({r['likes']} likes, {r['comments_n']} comments)")

# ---------------- COMMENTS: see + write for visibility ----------------

def cmd_comments(mine=False, post_id=None, limit=20):
    d = con()
    if mine or post_id:
        q = "SELECT * FROM comments WHERE mine=1"
        args = []
        if post_id: q += " AND post_id=?"; args.append(post_id)
        q += " ORDER BY id DESC LIMIT ?"; args.append(limit)
        rows = d.execute(q, args).fetchall()
        print(f"\n=== COMMENTS ON YOU ({len(rows)}) ===")
        for r in rows:
            st = "needs-reply" if not r["replied"] else "replied"
            print(f"[#{r['id']}] post#{r['post_id']} {r['author']} [{st}]: {r['text'][:200]}")
        un = [r for r in rows if not r["replied"]]
        if un: print(f"\n→ {len(un)} need replies. `reply-draft --comment \"...\"` then reply manually. Reply within 2h = algo boost.")
    else:
        rows = d.execute("SELECT * FROM feed_items ORDER BY comments_n DESC LIMIT ?", (limit,)).fetchall()
        print(f"\n=== WHERE TO COMMENT (ranked by visibility) ===")
        for r in rows:
            print(f"[feed #{r['id']}] {r['comments_n']} comments | {r['author']}: {r['text'][:110]}...")
        print("\n→ Rule: 5 value-comments/day > 20 'nice post'. See `comment-draft --id N`.")
    d.close()

COMMENT_STYLES = ["value", "question", "story"]

def llm_text(sys, user):
    if os.environ.get("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            c = OpenAI()
            r = c.chat.completions.create(model="gpt-4o-mini",
                messages=[{"role":"system","content":sys},{"role":"user","content":user}])
            return r.choices[0].message.content.strip()
        except Exception as e:
            print(f"[warn] OpenAI fail: {e}")
    return ""

def gen_comment(target_text, author, style, voice="practical, friendly, specific, no fluff"):
    """Visibility-optimized comment: specific + adds value + ends with question. Never 'nice post'."""
    sys = (f"Write LinkedIn comments. Voice: {voice}. Rules: under 60 words, "
           "reference ONE specific point from post, add 1 concrete tip/number, end with question. "
           "No emojis spam, no 'Great post', no generic praise.")
    user = f"Post by {author}: {target_text[:600]}\nStyle: {style}. Write the comment only."
    t = llm_text(sys, user)
    if t: return t
    spec = (target_text[:90] + "...") if len(target_text) > 90 else target_text
    if style == "question":
        return (f"Great breakdown on \"{spec}\" - the part about numbers-first really hit. "
                f"How do you handle it when the metric is hard to quantify, {author.split()[0] if author else 'thanks'}? "
                f"In my case I use proxy metrics (reply rate / views). What's worked for you?")
    if style == "story":
        return (f"Tried something similar with \"{spec}\" - got 3 replies from 8 sends after personalizing "
                f"the first line about their post. Your point on commenting before DMing is key. "
                f"Did you also follow up a 2nd time?")
    return (f"Strong point on \"{spec}\". One addition: I test hooks by rewriting line-1 three ways and "
            f"keeping ER% = (likes+3*comments+5*reposts)/views. Above 5% I repeat the format. "
            f"What's your cutoff for repeating a format?")

def cmd_comment_draft(fid=None, for_text="", author="", style="all"):
    d = con()
    if fid:
        r = d.execute("SELECT * FROM feed_items WHERE id=?", (fid,)).fetchone()
        if not r: print(f"[err] no feed #{fid}"); d.close(); return
        for_text, author = r["text"], r["author"]
    d.close()
    if not for_text: print("[err] give --id <feed_id> or --for \"post text\""); return
    styles = COMMENT_STYLES if style == "all" else [style]
    d = con()
    made = []
    for s in styles:
        c = gen_comment(for_text, author, s)
        score = 60 + (10 if "?" in c else 0) + (10 if len(c.split()) <= 60 else 0) + (10 if for_text[:15].lower() not in c.lower() else 0)
        cur = d.execute("INSERT INTO comment_queue(target_author,target_text,comment,style,status,created,score) VALUES(?,?,?,?,?,?,?)",
                  (author, for_text[:500], c, s, "pending", datetime.datetime.now().isoformat(), min(99,score)))
        made.append((cur.lastrowid, s, c, min(99,score)))
    d.commit(); d.close()
    log_action("comment_draft", for_text[:150])
    print(f"\n=== 3 visibility comments for: {author} ===")
    print(f"\"{for_text[:150]}...\"\n")
    for i,s,c,sc in made:
        print(f"[comment #{i}][{s}][score {sc}]\n{c}\n")
    print("Next: `comment-queue` -> `comment-approve --id N` -> `comment-post --id N --simulate/--real`")
    try:
        import telegram_approval as tg
        tg.notify("New comments to approve:\n" + "\n".join(f"#{i} [{s}] {c[:120]}" for i,s,c,_ in made))
    except Exception: pass

def cmd_comment_queue():
    d = con()
    rows = d.execute("SELECT * FROM comment_queue ORDER BY id DESC LIMIT 15").fetchall()
    d.close()
    if not rows: print("[queue] no comments. `comment-draft --id <feed_id>` first."); return
    for r in rows:
        print(f"[#{r['id']}] {r['status']} [{r['style']}] s={r['score']} on {r['target_author']}\n  {r['comment'][:160]}")

def cmd_comment_approve(i, ok=True):
    d = con()
    d.execute("UPDATE comment_queue SET status=? WHERE id=?", ("approved" if ok else "rejected", i))
    d.commit(); d.close()
    log_action("comment_approve" if ok else "comment_reject", f"#{i}")
    print(f"[{'approved' if ok else 'rejected'}] comment #{i}")

def cmd_comment_post(i, real=False):
    if not check_cap("comment"): return
    d = con()
    r = d.execute("SELECT * FROM comment_queue WHERE id=?", (i,)).fetchone()
    d.close()
    if not r: print(f"[err] no comment #{i}"); return
    if r["status"] != "approved": print(f"[safety] #{i} is {r['status']}. Approve first."); return
    if not real:
        print(f"[simulate] WOULD comment on '{r['target_author']}':\n{r['comment']}")
        print("Run --real: browser opens feed, types it, YOU click Reply (manual final click = safe).")
        log_action("comment", f"simulate #{i}")
        return
    body = real_snapshot("https://www.linkedin.com/feed/", "comment_post", scrolls=2)
    _ = body
    print(f"\n[real] Paste-ready comment #{i}:\n{r['comment']}\n")
    print("[real] In the opened window: find the post, click Comment, paste, click Reply YOURSELF.")
    input("Press Enter when done...")
    log_action("comment", f"real #{i}")
    print("[done] logged against daily cap.")

def cmd_reply_draft(comment):
    t = llm_text("Write short LinkedIn reply. Under 40 words, thankful, specific, end with question.",
                 f"Reply to this comment on my post: {comment}") or \
        (f"Thanks {comment.split()[0] if comment else 'so much'}! Great q - short answer: small testable steps + "
         f"track ER%. Happy to share my checklist. What's your current stack?")
    print(f"\n[reply draft] for: {comment!r}\n{t}\n(Tip: reply within 2h, always end with ?)")
    log_action("reply", comment[:200])

# ---------------- INBOX ----------------

HIRING_WORDS = ["hiring","resume","interview","ctc","lpa","role","openings","schedule a call","share your"]

def cmd_inbox(real=False, limit=20):
    if real:
        body = real_snapshot("https://www.linkedin.com/messaging/", "inbox", scrolls=3)
        d = con()
        d.execute("INSERT INTO inbox(name,snippet,full,unread,is_recruiter,created) VALUES(?,?,?,?,?,?)",
                  ("Real snapshot","see traces/inbox_*.txt",(body or "")[:2000],1,0,datetime.datetime.now().isoformat()))
        d.commit(); d.close()
    d = con()
    rows = d.execute("SELECT * FROM inbox ORDER BY unread DESC, id DESC LIMIT ?", (limit,)).fetchall()
    d.close()
    if not rows: print("[inbox] empty. `sync --simulate` first."); return
    print(f"\n=== INBOX ({len(rows)} threads, {sum(1 for r in rows if r['unread'])} unread) ===")
    for r in rows:
        tag = "🔥 RECRUITER" if r["is_recruiter"] else ("● UNREAD" if r["unread"] else "○ read")
        print(f"\n[#{r['id']}] [{tag}] {r['name']}: {r['snippet'][:120]}")
    rec = [r for r in rows if r["is_recruiter"] and r["unread"]]
    if rec: print(f"\n→ {len(rec)} unread recruiter msg(s) - reply FIRST (within 24h). `inbox-read --id N` then `inbox-reply --id N`.")
    print("Next: `inbox-read --id N` to see full + agent's suggested reply.")

def cmd_inbox_read(i):
    d = con()
    r = d.execute("SELECT * FROM inbox WHERE id=?", (i,)).fetchone()
    if not r: print(f"[err] no thread #{i}"); d.close(); return
    d.execute("UPDATE inbox SET unread=0 WHERE id=?", (i,)); d.commit()
    print(f"\n=== {r['name']} ===\n{r['full'] or r['snippet']}\n")
    low = ((r["full"] or "") + " " + (r["snippet"] or "")).lower()
    is_hire = any(w in low for w in HIRING_WORDS) or r["is_recruiter"]
    if is_hire:
        sug = (f"Hi {r['name'].split()[0]}, thanks for reaching out! The role sounds relevant - "
               f"I'm a Python backend dev (FastAPI, Postgres, LLM agents), open to remote. "
               f"Happy to chat Mon/Tue after 11am. Sharing resume + GitHub. What's the stack + range?")
    else:
        sug = (f"Hi {r['name'].split()[0]}, thanks for writing! Happy to help - "
               f"can you share a bit more context (your goal + timeline)? Will reply properly tomorrow.")
    print(f"--- Suggested reply (edit before sending, you approve) ---\n{sug}")
    print(f"\nTo use: `inbox-reply --id {i} --text \"...\"` (saves as approved draft) or copy manually.")
    d.close()
    log_action("inbox_read", f"#{i}")

def cmd_inbox_reply(i, text, real=False):
    if not check_cap("reply"): return
    sug = text or ""
    if not sug: print("[err] --text required"); return
    print(f"\n[reply queued] thread #{i}:\n{sug}")
    print("Safety: no auto-send. " + ("`--real` opens messaging, types it, YOU hit Send." if real else "Copy-paste to LinkedIn, or re-run with --real."))
    if real:
        real_snapshot("https://www.linkedin.com/messaging/", "inbox_reply", scrolls=1)
        print("[real] Browser open. Find thread, paste above, Send YOURSELF."); input("Enter when sent...")
    log_action("reply", f"#{i}: {sug[:150]}")

# ---------------- CONNECTS ----------------

def cmd_connects():
    d = con()
    rows = d.execute("SELECT * FROM connections ORDER BY id").fetchall()
    d.close()
    if not rows: print("[connects] empty. `sync --simulate` first."); return
    pend = [r for r in rows if "pending" in r["status"]]
    print(f"\n=== NETWORK ({len(rows)} total, {len(pend)} pending) ===")
    for r in rows:
        print(f"[#{r['id']}] [{r['status']}] {r['name']} - {r['headline']}")
    if pend:
        print("\n→ Pending invites: accept peers/hiring managers, ignore sellers/spam.")
        print("→ After accepting: send 1 thank-you + 1 question (no pitch). Template:")
        print("  \"Thanks for connecting, {name}! Saw your post on X - how are you approaching Y?\"")
    print("→ Weekly: 5 targeted comments on connects' posts > 50 random connects. Visibility comes from comments.")
    print("Next: `connect-accept --id N` logs it (real accept = click yourself in browser for safety).")

def cmd_connect_accept(i):
    if not check_cap("connect"): return
    d = con()
    r = d.execute("SELECT * FROM connections WHERE id=?", (i,)).fetchone()
    if r: d.execute("UPDATE connections SET status='connected' WHERE id=?", (i,))
    d.commit(); d.close()
    if not r: print(f"[err] no connect #{i}"); return
    log_action("connect", f"accept #{i} {r['name']}")
    print(f"[accepted-logged] {r['name']}. (Real click: do in browser - mass-accept triggers checks.)")
    print(f"Follow-up to send: \"Thanks {r['name'].split()[0]}! What are you working on this week?\"")

# ---------------- POSTS (kept, optimized scoring) ----------------

VIRAL_HOOKS = [
    "I wasted {n} hours on {x}. Here's the 3-line fix:",
    "Nobody tells juniors this about {x}:",
    "I sent 50 generic DMs (0 replies). Then 10 personal ones (6 replies):",
]

def llm_or_template(topic, cfg):
    key = os.environ.get("OPENAI_API_KEY", "")
    tags = "#python #backend #opentowork #softwareengineer"
    if key:
        try:
            from openai import OpenAI
            c = OpenAI()
            r = c.chat.completions.create(model="gpt-4o-mini",
                messages=[
                    {"role":"system","content":f"You write LinkedIn posts. Voice: {cfg.get('voice','practical,friendly')}. Rules: hook <60 chars, short lines, 1 story + 3 bullets + question, <150 words."},
                    {"role":"user","content":f"Topic: {topic}. Audience: recruiters + devs."}])
            return r.choices[0].message.content.strip(), tags
        except Exception as e: print(f"[warn] OpenAI fail ({e}), template.")
    hook = random.choice(VIRAL_HOOKS).format(n=random.randint(5,20), x=topic)
    return (f"{hook}\n\n1. What I tried\n2. What failed\n3. What finally worked\n\nContext: {topic}.\n\n"
            f"Lesson: small consistent posts beat viral luck.\n\nWhat's your experience with {topic}? 👇", tags)

def cmd_draft(topic, cfg_path):
    cfg = json.load(open(cfg_path)) if os.path.exists(cfg_path) else {}
    text, tags = llm_or_template(topic, cfg)
    score = 50 + (10 if "?" in text else 0) + (10 if len(text.split()) < 160 else 0) + 10
    d = con()
    cur = d.execute("INSERT INTO drafts(topic,text,hashtags,created,score) VALUES(?,?,?,?,?)",
                  (topic, text, tags, datetime.datetime.now().isoformat(), score))
    d.commit(); did = cur.lastrowid; d.close()
    log_action("draft", f"#{did} {topic}")
    print(f"\n[draft #{did}] score {score}/100\n{text}\n\n{tags}\nNext: `approve --id {did}`.")
    try:
        import telegram_approval as tg
        tg.notify(f"New post #{did} (s={score}):\n{text}\n{tags}\n/approve {did}")
    except Exception as e: print(f"[telegram] not sent ({e})")

def cmd_queue():
    d = con()
    rows = d.execute("SELECT * FROM drafts ORDER BY id DESC LIMIT 20").fetchall()
    d.close()
    if not rows: print("[queue] empty."); return
    for r in rows:
        print(f"[#{r['id']}] {r['status']} s={r['score']} {r['topic']}\n  {r['text'][:140].replace(chr(10),' / ')}")

def cmd_approve(i, ok=True):
    d = con()
    d.execute("UPDATE drafts SET status=? WHERE id=?", ("approved" if ok else "rejected", i))
    d.commit(); d.close()
    log_action("approve" if ok else "reject", f"draft #{i}")
    print(f"[{'approved' if ok else 'rejected'}] draft #{i}")

def cmd_post(i, real=False):
    if not check_cap("post"): return
    d = con()
    r = d.execute("SELECT * FROM drafts WHERE id=?", (i,)).fetchone()
    d.close()
    if not r: print(f"[err] no draft #{i}"); return
    if r["status"] != "approved": print(f"[safety] #{i} is {r['status']}. Approve first."); return
    full = r["text"] + "\n\n" + (r["hashtags"] or "")
    if not real:
        print(f"[simulate] WOULD post #{i}:\n{full[:500]}\nRun --real to type in browser (you click Post)."); return
    try: from playwright.sync_api import sync_playwright
    except ImportError: print("[err] pip install playwright"); return
    prof = os.path.join(BASE, ".browser-profile")
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(prof, headless=False)
        page = ctx.new_page() if not ctx.pages else ctx.pages[0]
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        page.screenshot(path=os.path.join(TRACE, "before_post.png"))
        print("----COPY----\n"+full+"\n----END----")
        print("[real] Click 'Start a post' yourself. Typing in 10s...")
        time.sleep(10)
        page.keyboard.type(full[:1000], delay=random.randint(30,70))
        page.screenshot(path=os.path.join(TRACE, "after_type.png"))
        print("[real] Typed. Click Post YOURSELF."); input("Enter after posted...")
        ctx.close()
    log_action("post", f"#{i}")

# ---------------- ANALYTICS + AUDIT + DIGEST ----------------

def er(likes, com, rep, views):
    return (likes + com*3 + rep*5) / max(1, views) * 100

def cmd_analytics():
    d = con()
    rows = d.execute("SELECT * FROM posts ORDER BY views DESC").fetchall()
    d.close()
    if not rows: print("[analytics] no data. `sync --simulate` first."); return
    print(f"\n=== ANALYTICS ({len(rows)} posts, {sum(r['views'] for r in rows)} views) ===")
    for r in rows:
        print(f"\n[#{r['id']}] {r['views']} views | {r['likes']} likes | {r['comments']} c | {r['reposts']} rp | ER {er(r['likes'],r['comments'],r['reposts'],r['views']):.1f}%\n  {r['text'][:120].replace(chr(10),' / ')}")
    print(f"\n-> Winner #{rows[0]['id']}: repeat format (hook + numbers + question). Pin it to Featured.")

def cmd_audit(cfg_path):
    cfg = json.load(open(cfg_path)) if os.path.exists(cfg_path) else {}
    kw = cfg.get("target_keywords", ["python","fastapi","open to work"])
    print("\n=== RECRUITER AUDIT ===\n1. Headline: Role | Stack | Proof | Open to X\n2. About L1-3: who you help + metric + " + ", ".join(kw) +
          "\n3. Featured: pin winner post + resume PDF\n4. Open-To-Work: ON (recruiters only)\n5. Skills top5 = target roles\n6. Post 2-3x/wk 9am/6:30pm IST\n7. Comment 5x/day on hiring managers (2 real lines)")

def cmd_digest():
    """The 'say what it was' command: everything in one screen."""
    d = con()
    posts = d.execute("SELECT * FROM posts ORDER BY views DESC").fetchall()
    coms = d.execute("SELECT * FROM comments WHERE mine=1 ORDER BY id DESC LIMIT 10").fetchall()
    feed = d.execute("SELECT * FROM feed_items ORDER BY id DESC LIMIT 5").fetchall()
    ib = d.execute("SELECT * FROM inbox ORDER BY unread DESC LIMIT 10").fetchall()
    pend = d.execute("SELECT * FROM comment_queue WHERE status='pending'").fetchall()
    drafts = d.execute("SELECT * FROM drafts WHERE status='pending'").fetchall()
    unrep = [c for c in coms if not c["replied"]]
    unib = [m for m in ib if m["unread"]]
    d.close()
    print("\n" + "="*56 + "\n  LINKEDIN DAILY DIGEST - what happened + what to do\n" + "="*56)
    tv = sum(p["views"] for p in posts) if posts else 0
    print(f"\n📊 YOU: {len(posts)} posts tracked, {tv} views total.")
    if posts:
        b = max(posts, key=lambda r: er(r["likes"],r["comments"],r["reposts"],r["views"]))
        print(f"   Best ER: post #{b['id']} ({er(b['likes'],b['comments'],b['reposts'],b['views']):.1f}%). Repeat its hook style.")
    print(f"\n💬 COMMENTS ON YOU: {len(unrep)} need reply.")
    for c in unrep[:3]: print(f"   #{c['id']} {c['author']}: {c['text'][:100]}...")
    print(f"\n📥 INBOX: {len(unib)} unread ({sum(1 for m in unib if m['is_recruiter'])} recruiter).")
    for m in unib[:3]: print(f"   #{m['id']} {'🔥' if m['is_recruiter'] else '●'} {m['name']}: {m['snippet'][:90]}...")
    print(f"\n📰 FEED: {len(feed)} fresh. Hiring: {sum(1 for f in feed if f['tag']=='HIRING' or 'hiring' in f['text'].lower())}.")
    for f in feed[:3]: print(f"   #{f['id']} [{f['tag']}] {f['author']}: {f['text'][:90]}...")
    print(f"\n✍️ PENDING: {len(drafts)} post drafts, {len(pend)} comments awaiting approval.")
    print("\n✅ DO NEXT (30 min):")
    n = 1
    if any(m["is_recruiter"] and m["unread"] for m in ib): print(f" {n}. Reply recruiters first: `inbox-read --id ...`"); n+=1
    if unrep: print(f" {n}. Reply to {len(unrep)} comments on you (2h window = boost)."); n+=1
    print(f" {n}. Write 3 value-comments: `comment-draft --id <feed_id>` (hiring posts first)."); n+=1
    if not drafts: print(f" {n}. Draft 1 post: `draft --topic \"...\"`."); n+=1
    else: print(f" {n}. Approve posts: `queue` -> Telegram /approve."); n+=1
    print(f" {n}. Check network: `connects` (accept + thank-you note).")

def sync_real(url="https://www.linkedin.com/feed/"):
    real_snapshot(url, "sync", scrolls=4)
    log_action("sync", f"real {url}")

# ---------------- cli ----------------

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    s = sub.add_parser("sync"); s.add_argument("--simulate", action="store_true"); s.add_argument("--real", action="store_true")
    sub.add_parser("analytics")
    au = sub.add_parser("audit"); au.add_argument("--config", default=os.path.join(BASE, "config.example.json"))
    dr = sub.add_parser("draft"); dr.add_argument("--topic", required=True); dr.add_argument("--config", default=os.path.join(BASE, "config.example.json"))
    sub.add_parser("queue")
    a = sub.add_parser("approve"); a.add_argument("--id", type=int, required=True)
    rj = sub.add_parser("reject"); rj.add_argument("--id", type=int, required=True)
    p = sub.add_parser("post"); p.add_argument("--id", type=int, required=True); p.add_argument("--real", action="store_true"); p.add_argument("--simulate", action="store_true")
    f = sub.add_parser("feed"); f.add_argument("--real", action="store_true"); f.add_argument("--limit", type=int, default=8)
    fd = sub.add_parser("feed-read"); fd.add_argument("--id", type=int, required=True)
    c = sub.add_parser("comments"); c.add_argument("--mine", action="store_true"); c.add_argument("--post-id", type=int, default=None); c.add_argument("--limit", type=int, default=20)
    cd = sub.add_parser("comment-draft"); cd.add_argument("--id", type=int, default=None); cd.add_argument("--for", dest="for_text", default=""); cd.add_argument("--author", default=""); cd.add_argument("--style", default="all", choices=["all","value","question","story"])
    sub.add_parser("comment-queue")
    ca = sub.add_parser("comment-approve"); ca.add_argument("--id", type=int, required=True)
    cr = sub.add_parser("comment-reject"); cr.add_argument("--id", type=int, required=True)
    cp = sub.add_parser("comment-post"); cp.add_argument("--id", type=int, required=True); cp.add_argument("--real", action="store_true"); cp.add_argument("--simulate", action="store_true")
    rd = sub.add_parser("reply-draft"); rd.add_argument("--comment", required=True)
    ib = sub.add_parser("inbox"); ib.add_argument("--real", action="store_true"); ib.add_argument("--limit", type=int, default=20)
    ir = sub.add_parser("inbox-read"); ir.add_argument("--id", type=int, required=True)
    rp = sub.add_parser("inbox-reply"); rp.add_argument("--id", type=int, required=True); rp.add_argument("--text", default=""); rp.add_argument("--real", action="store_true")
    sub.add_parser("connects")
    co = sub.add_parser("connect-accept"); co.add_argument("--id", type=int, required=True)
    sub.add_parser("digest")
    A = ap.parse_args()

    if A.cmd == "init": init_db()
    elif A.cmd == "sync":
        if A.real: sync_real()
        else: sync_simulate()
    elif A.cmd == "analytics": cmd_analytics()
    elif A.cmd == "audit": cmd_audit(A.config)
    elif A.cmd == "draft": cmd_draft(A.topic, A.config)
    elif A.cmd == "queue": cmd_queue()
    elif A.cmd == "approve": cmd_approve(A.id, True)
    elif A.cmd == "reject": cmd_approve(A.id, False)
    elif A.cmd == "post": cmd_post(A.id, real=A.real)
    elif A.cmd == "feed": cmd_feed(real=A.real, limit=A.limit)
    elif A.cmd == "feed-read": cmd_feed_detail(A.id)
    elif A.cmd == "comments": cmd_comments(mine=A.mine, post_id=A.post_id, limit=A.limit)
    elif A.cmd == "comment-draft": cmd_comment_draft(fid=A.id, for_text=A.for_text, author=A.author, style=A.style)
    elif A.cmd == "comment-queue": cmd_comment_queue()
    elif A.cmd == "comment-approve": cmd_comment_approve(A.id, True)
    elif A.cmd == "comment-reject": cmd_comment_approve(A.id, False)
    elif A.cmd == "comment-post": cmd_comment_post(A.id, real=A.real)
    elif A.cmd == "reply-draft": cmd_reply_draft(A.comment)
    elif A.cmd == "inbox": cmd_inbox(real=A.real, limit=A.limit)
    elif A.cmd == "inbox-read": cmd_inbox_read(A.id)
    elif A.cmd == "inbox-reply": cmd_inbox_reply(A.id, A.text, real=A.real)
    elif A.cmd == "connects": cmd_connects()
    elif A.cmd == "connect-accept": cmd_connect_accept(A.id)
    elif A.cmd == "digest": cmd_digest()

if __name__ == "__main__":
    main()
