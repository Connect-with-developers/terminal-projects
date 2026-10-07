"""Read-only IMAP fetch from YOUR OWN mailbox.

Usage:
  export IMAP_HOST=imap.gmail.com IMAP_USER=you@gmail.com IMAP_PASS='app-password'
  python fetch_own_inbox.py --limit 5 --sender noreply@devin.ai

Never put credentials in code. Uses app passwords, read-only (EXAMINE).
"""
import argparse
import email
import imaplib
import os
from email.header import decode_header

from extractor import best_code


def subj(h):
    parts = decode_header(h or "")
    out = ""
    for b, enc in parts:
        out += b.decode(enc or "utf-8", "ignore") if isinstance(b, bytes) else b
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--sender", default=None)
    p.add_argument("--folder", default="INBOX")
    a = p.parse_args()
    host, user, pw = os.environ.get("IMAP_HOST"), os.environ.get("IMAP_USER"), os.environ.get("IMAP_PASS")
    if not all([host, user, pw]):
        print("Set IMAP_HOST/IMAP_USER/IMAP_PASS env vars (app password, not main password).")
        raise SystemExit(2)
    m = imaplib.IMAP4_SSL(host)
    m.login(user, pw)
    m.select(a.folder, readonly=True)
    crit = f'(FROM "{a.sender}")' if a.sender else "ALL"
    _, ids = m.search(None, crit)
    ids = ids[0].split()[-a.limit:]
    for i in reversed(ids):
        _, data = m.fetch(i, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and not part.get_filename():
                    try:
                        body += part.get_payload(decode=True).decode("utf-8", "ignore")
                    except Exception:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode("utf-8", "ignore")
            except Exception:
                body = str(msg.get_payload())
        print(f"--- {subj(msg['Subject'])} | from={msg['From']} | date={msg['Date']}")
        print(f"    best_code={best_code(body)}")
    m.logout()


if __name__ == "__main__":
    main()
