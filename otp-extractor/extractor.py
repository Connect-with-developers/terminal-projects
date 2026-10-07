"""OTP/code extractor for YOUR OWN inbox only.

Lawful use: parse messages you have legal access to (your email, app password).
Not for temp-mail signup bypass / third-party inboxes.
Rule-based (regex + keyword scoring) = fast, no ML deps, testable.
"""
import re

KEYWORDS = ["otp", "verification", "verify", "code", "2fa", "two-factor",
            "passcode", "one-time", "login code", "confirm"]

# 4-8 digit numeric, 6-char alnum (ABC-123), 8-char backup codes
PATTERNS = [
    re.compile(r"\b(\d{4,8})\b"),
    re.compile(r"\b([A-Z0-9]{3}-[A-Z0-9]{3,4})\b", re.I),
    re.compile(r"\b([A-Z]{2,4}\d{2,6})\b"),
]


def score_candidate(text, m):
    low = text.lower()
    s = 0
    for kw in KEYWORDS:
        if kw in low:
            s += 2
    # proximity bonus: keyword within 40 chars of match
    start = max(0, m.start() - 40)
    window = low[start:m.end() + 40]
    for kw in KEYWORDS:
        if kw in window:
            s += 3
            break
    # prefer 6-digit
    if re.fullmatch(r"\d{6}", m.group(1)):
        s += 2
    # penalize years / long numbers that look like dates/prices
    if re.fullmatch(r"(19|20)\d{2}", m.group(1)):
        s -= 5
    return s


def extract_otp(text, top_k=3):
    """Return [{'code': str, 'score': int}] sorted best-first."""
    text = text or ""
    found = {}
    for pat in PATTERNS:
        for m in pat.finditer(text):
            code = m.group(1).strip().upper()
            if code in found:
                continue
            found[code] = score_candidate(text, m)
    ranked = sorted(found.items(), key=lambda kv: kv[1], reverse=True)
    return [{"code": c, "score": s} for c, s in ranked[:top_k]]


def best_code(text):
    r = extract_otp(text, top_k=1)
    return r[0]["code"] if r and r[0]["score"] > 0 else None


if __name__ == "__main__":
    import sys
    data = sys.stdin.read()
    print(best_code(data) or "NO-CODE-FOUND")
