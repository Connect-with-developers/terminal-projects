#!/usr/bin/env python3
"""
Telegram approval gate: agent NEVER posts/DMs without your /approve.

Setup (2 min):
 1. Chat with @BotFather -> /newbot -> copy token
 2. Chat with your bot -> send anything
 3. Get chat_id: https://api.telegram.org/bot<TOKEN>/getUpdates
 4. Put both in config.example.json (copy to config.json) OR env:
      export TELEGRAM_TOKEN=... TELEGRAM_CHAT_ID=...

Run:
  python telegram_approval.py listen     # polls for /approve <id> /reject <id> /pending
  python telegram_approval.py test       # sends test message
"""
import json, os, sys, time, sqlite3
import urllib.request, urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "memory.db")

def creds():
    tok = os.environ.get("TELEGRAM_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    cfgp = os.path.join(BASE, "config.json")
    if os.path.exists(cfgp):
        c = json.load(open(cfgp))
        tok = tok or c.get("telegram_bot_token", "")
        chat = chat or str(c.get("telegram_chat_id", ""))
    if tok.startswith("PUT_"): tok = ""
    return tok, chat

def send(text):
    tok, chat = creds()
    if not tok or not chat or tok.startswith("PUT"):
        print(f"[telegram simulate] no token configured. Would send:\n{text[:300]}")
        return False
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat, "text": text[:4000]}).encode()
    urllib.request.urlopen(url, data, timeout=15).read()
    print("[telegram] sent")
    return True

def notify(text):
    return send(text)

def set_status(i, ok, table="drafts"):
    d = sqlite3.connect(DB)
    tbl = "comment_queue" if table == "comment" else "drafts"
    d.execute(f"UPDATE {tbl} SET status=? WHERE id=?",
        ("approved" if ok else "rejected", i)); d.commit(); d.close()

def pending_text():
    import sqlite3
    d = sqlite3.connect(DB); d.row_factory = sqlite3.Row
    try:
        rows = d.execute("SELECT * FROM drafts WHERE status='pending' ORDER BY id DESC").fetchall()
    except Exception:
        return "db not init yet. Run linkedin_agent.py init"
    try:
        crows = d.execute("SELECT * FROM comment_queue WHERE status='pending' ORDER BY id DESC").fetchall()
    except Exception:
        crows = []
    finally:
        d.close()
    if not rows and not crows: return "No pending. 🎉 Run digest to generate work."
    out = []
    if rows:
        out.append("POSTS:")
        for r in rows:
            out.append(f"#{r['id']} s={r['score']} {r['topic']}\n{r['text'][:200]}...\n/approve {r['id']}  /reject {r['id']}\n")
    if crows:
        out.append("COMMENTS:")
        for r in crows:
            out.append(f"c#{r['id']} [{r['style']}] on {r['target_author']}\n{r['comment'][:200]}...\n/capprove {r['id']}  /creject {r['id']}\n")
    out.append("Cmds: /digest /feed /inbox /connects")
    return "\n".join(out)

def listen():
    tok, _ = creds()
    if not tok:
        print("[err] set TELEGRAM_TOKEN first. See docstring.")
        return
    off = 0
    print("[listen] polling... /pending /approve <id> /reject <id> /capprove <id> /digest")
    while True:
        try:
            url = f"https://api.telegram.org/bot{tok}/getUpdates?timeout=25&offset={off}"
            res = json.load(urllib.request.urlopen(url, timeout=30))
            for u in res.get("result", []):
                off = u["update_id"] + 1
                msg = u.get("message", {})
                txt = (msg.get("text") or "").strip()
                cid = msg.get("chat", {}).get("id", "")
                os.environ["TELEGRAM_CHAT_ID"] = str(cid)
                if txt.startswith("/pending"):
                    send(pending_text())
                elif txt.startswith("/capprove"):
                    try: i = int(txt.split()[1]); set_status(i, True, "comment"); send(f"Comment c#{i} approved ✅. Run comment-post --id {i} --real")
                    except Exception as e: send(f"usage: /capprove <id> ({e})")
                elif txt.startswith("/creject"):
                    try: i = int(txt.split()[1]); set_status(i, False, "comment"); send(f"Comment c#{i} rejected")
                    except Exception as e: send(f"usage: /creject <id> ({e})")
                elif txt.startswith("/approve"):
                    try: i = int(txt.split()[1]); set_status(i, True); send(f"Approved #{i} ✅. Run post --id {i} --real")
                    except Exception as e: send(f"usage: /approve <id> ({e})")
                elif txt.startswith("/reject"):
                    try: i = int(txt.split()[1]); set_status(i, False); send(f"Rejected #{i}")
                    except Exception as e: send(f"usage: /reject <id> ({e})")
                elif txt.startswith("/digest"):
                    send("Run on server: python linkedin_agent.py digest  (Telegram digest coming next)")
                elif txt.startswith("/start"):
                    send("LinkedIn agent gate.\n/pending = posts + comments\n/approve <id> /reject <id>\n/capprove <id> /creject <id>\n/digest")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("poll err", e); time.sleep(3)

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "test":
        send("LinkedIn agent connected ✅. You'll approve posts here.")
    elif sys.argv[1] == "listen":
        listen()
    elif sys.argv[1] == "pending":
        print(pending_text())
