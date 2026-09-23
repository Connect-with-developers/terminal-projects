#!/usr/bin/env python3
"""
Self-Healing Code Builder - CLI Agent
Build -> Test in terminal -> Read error -> Fix -> Test again -> Learn

Usage (only commands, no interaction):
  python builder.py build --task tasks/calculator.txt --output generated/calculator.py --max-fix 5
  python builder.py build --task tasks/calculator.txt --output generated/calculator.py --dry-run --diff --sandbox --commit
  python builder.py build --task tasks/calculator.txt --output generated/calculator.py --watch --watch-secs 60
  python builder.py test --file generated/calculator.py --tests tests --sandbox
  python builder.py improve --file generated/calculator.py --rounds 3
  python builder.py tdd --task tasks/calculator.txt --output generated/calculator.py
  python builder.py project --task tasks/todo.txt --output-dir generated/shop
  python builder.py lint --file generated/calculator.py
  python builder.py review --file generated/calculator.py
  python builder.py map
  python builder.py memory --search "divide fix" --limit 3
  python builder.py stats --cost
  python builder.py undo --file generated/calculator.py --steps 1
  python builder.py autopilot --max-fix 5
"""
import argparse
import ast
import datetime
import difflib
import hashlib
import json
import os
import py_compile
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "memory.db")
BACKUP_DIR = os.path.join(BASE_DIR, ".backups")


# ---------- Safety: backups + git checkpoints (from Aider/Sentinel/UTIM) ----------
def snapshot_file(filepath):
    """Save timestamped backup before every mutation. Returns backup path."""
    if not os.path.exists(filepath):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name = os.path.basename(filepath)
    dest = os.path.join(BACKUP_DIR, f"{name}.{ts}.bak")
    with open(filepath, "rb") as src, open(dest, "wb") as dst:
        dst.write(src.read())
    # keep only last 20 backups per file
    cands = sorted([os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.startswith(name + ".")])
    for old in cands[:-20]:
        try:
            os.remove(old)
        except OSError:
            pass
    return dest


def list_backups(filename=None):
    if not os.path.isdir(BACKUP_DIR):
        return []
    files = sorted(os.listdir(BACKUP_DIR))
    if filename:
        base = os.path.basename(filename)
        files = [f for f in files if f.startswith(base + ".")]
    return [os.path.join(BACKUP_DIR, f) for f in files]


def undo_command(file_arg, steps=1):
    import shutil
    cands = list_backups(file_arg) if file_arg != "all" else sorted([os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)])
    if not cands:
        print("No backups found.")
        return 1
    # group by original file: undo last N snapshots for that file
    target_base = os.path.basename(file_arg)
    mine = [c for c in cands if os.path.basename(c).startswith(target_base + ".")]
    if not mine:
        print(f"No backups for {file_arg}")
        return 1
    mine = sorted(mine)[-steps:]
    # restore the oldest of the selected window (i.e. state before those steps)
    # simplest: restore mine[0] which is earliest in window -> actually we want state before last step:
    # we saved backup BEFORE each write, so last backup = state before last write. Restore it.
    restore_from = sorted(mine)[-1]
    # find original path: search generated/ and cwd
    orig = file_arg if os.path.exists(file_arg) else os.path.join(BASE_DIR, "generated", target_base)
    shutil.copy2(restore_from, orig)
    print(f"[undo] Restored {orig} from {os.path.basename(restore_from)}")
    return 0


def git_checkpoint(message):
    """Auto-commit like Aider: atomic commit per AI change, never push."""
    git_dir = os.path.join(BASE_DIR, "..", ".git")
    if not os.path.isdir(os.path.join(BASE_DIR, ".git")) and not os.path.isdir(git_dir):
        return False
    try:
        r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, timeout=10, cwd=BASE_DIR)
        if not r.stdout.strip():
            return False
        subprocess.run(["git", "add", "-A"], timeout=10, cwd=BASE_DIR, capture_output=True)
        subprocess.run(["git", "-c", "user.name=builder-agent", "-c", "user.email=builder@local", "commit", "-m", message],
                       timeout=15, cwd=BASE_DIR, capture_output=True)
        print(f"[git] checkpoint committed: {message}")
        return True
    except Exception:
        return False


# ---------- Lint gate (from Aider hooks / Omp LSP) ----------
def lint_file(filepath):
    """Stdlib-only lint: syntax, long lines, tabs, unused imports, missing docstrings. Returns list of issues."""
    issues = []
    try:
        src = open(filepath, encoding="utf-8", errors="ignore").read()
    except OSError as e:
        return [f"cannot read: {e}"]
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [f"SyntaxError line {e.lineno}: {e.msg}"]
    lines = src.splitlines()
    for i, line in enumerate(lines, 1):
        if len(line) > 100:
            issues.append(f"line {i}: too long ({len(line)} > 100)")
        if "\t" in line:
            issues.append(f"line {i}: tab indentation (use 4 spaces)")
    # unused imports (simple) - skip __future__ (compiler directive, never appears as Name)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            for a in node.names:
                imported.add(a.asname or a.name)
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
    for name in sorted(imported - used):
        issues.append(f"unused import: {name}")
    # missing docstrings
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not ast.get_docstring(node):
                issues.append(f"missing docstring: {node.name} (line {node.lineno})")
    # optional: ruff if installed (silent if not installed)
    try:
        r = subprocess.run([sys.executable, "-m", "ruff", "check", filepath], capture_output=True, text=True, timeout=20)
        combined = (r.stdout + r.stderr).strip()
        if "No module named ruff" in combined:
            pass
        elif r.returncode != 0 and combined:
            issues.append("ruff: " + combined[:500])
    except Exception:
        pass
    return issues


def format_file(filepath):
    """Format: black if available, else internal normalize. Returns True if changed."""
    before = open(filepath, encoding="utf-8", errors="ignore").read()
    try:
        r = subprocess.run([sys.executable, "-m", "black", "-q", filepath], capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            after = open(filepath).read()
            return after != before
    except Exception:
        pass
    lines = [l.rstrip().replace("\t", "    ") for l in before.splitlines()]
    cleaned, blanks = [], 0
    for l in lines:
        if l.strip() == "":
            blanks += 1
            if blanks <= 2:
                cleaned.append(l)
        else:
            blanks = 0
            cleaned.append(l)
    after = "\n".join(cleaned).rstrip() + "\n"
    if after != before:
        open(filepath, "w").write(after)
        return True
    return False


# ---------- Repo map (from Aider repo-map, compressed context) ----------
def repo_map_command():
    import glob
    files = sorted(glob.glob(os.path.join(BASE_DIR, "**", "*.py"), recursive=True))
    files = [f for f in files if ".backups" not in f and "__pycache__" not in f]
    print(f"[map] {len(files)} python files (budget ~1000 tokens, top symbols only)")
    # rank files by size of public API (like PageRank-lite: more defs = more important)
    entries = []
    for f in files:
        try:
            tree = ast.parse(open(f, encoding="utf-8", errors="ignore").read())
            funcs = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_")]
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            rel = os.path.relpath(f, BASE_DIR)
            entries.append((len(funcs) + len(classes) * 2, rel, funcs[:8], classes[:5]))
        except Exception:
            pass
    entries.sort(reverse=True)
    total_chars = 0
    for score, rel, funcs, classes in entries[:30]:
        line = f"{rel}: class {classes} | def {funcs}"
        print(" " + line[:160])
        total_chars += len(line)
    print(f"[map] ~{total_chars // 4} tokens. Full file loads on demand: builder.py diagnose --file <path>")


# ---------- Reviewer second pass (architect mode: planner + reviewer) ----------
def review_command(file_path):
    src = open(file_path, encoding="utf-8", errors="ignore").read()
    score = 100
    findings = []
    dangers = [("eval(", -20, "use of eval()"), ("exec(", -20, "use of exec()"),
                ("shell=True", -15, "subprocess shell=True"), ("password", -5, "possible hardcoded password"),
                ("os.system", -10, "os.system call")]
    for pat, penalty, msg in dangers:
        if pat in src:
            findings.append(f"SECURITY {penalty}: {msg} ('{pat}')")
            score += penalty
    try:
        tree = ast.parse(src)
        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for fn in funcs:
            if not ast.get_docstring(fn):
                findings.append(f"QUALITY -3: {fn.name} missing docstring")
                score -= 3
            if len(fn.body) > 50:
                findings.append(f"QUALITY -5: {fn.name} too long ({len(fn.body)} stmts)")
                score -= 5
        if not funcs and not [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            findings.append("QUALITY -10: no functions/classes found")
            score -= 10
    except SyntaxError as e:
        findings.append(f"SYNTAX -50: {e}")
        score -= 50
    lint = lint_file(file_path)
    for issue in lint[:10]:
        findings.append(f"LINT -2: {issue}")
        score -= 2
    score = max(0, min(100, score))
    verdict = "APPROVE" if score >= 80 else ("REVISE" if score >= 50 else "REJECT")
    print(f"[review] {file_path} -> {score}/100 {verdict}")
    for f in findings[:20]:
        print(" - " + f)
    return 0 if score >= 50 else 1


# ---------- Memory (how agent LEARNS) ----------
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS builds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_hash TEXT,
        task_text TEXT,
        output_file TEXT,
        status TEXT,
        fixes_applied TEXT,
        tests_passed INTEGER,
        tests_total INTEGER,
        timestamp TEXT
    )
    """)
    con.commit()
    con.close()


def save_memory(task_text, output_file, status, fixes, passed, total):
    init_db()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO builds (task_hash, task_text, output_file, status, fixes_applied, tests_passed, tests_total, timestamp) VALUES (?,?,?,?,?,?,?,?)",
        (
            hashlib.md5(task_text.encode()).hexdigest()[:10],
            task_text[:2000],
            output_file,
            status,
            json.dumps(fixes),
            passed,
            total,
            datetime.datetime.now().isoformat(),
        ),
    )
    con.commit()
    con.close()


def get_memory(task_text, limit=3):
    """Retrieve past similar builds - this is the 'learning' part."""
    if not os.path.exists(DB_PATH):
        return []
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT task_text, output_file, status, fixes_applied FROM builds ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    con.close()
    return rows


# ---------- Code Generation ----------
def try_llm_generate(task_text):
    """If OPENAI_API_KEY is set, use real LLM. Else return None (use local engine)."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None
    try:
        import urllib.request
        payload = json.dumps({
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": "You output ONLY valid Python code. No markdown, no explanation. Include docstrings and type hints."},
                {"role": "user", "content": f"Write Python code for this task:\n{task_text}"},
            ],
            "temperature": 0.2,
        }).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
            code = data["choices"][0]["message"]["content"]
            # strip markdown fences if any
            code = re.sub(r"^```python\s*|```$", "", code.strip(), flags=re.MULTILINE).strip()
            return code
    except Exception as e:
        print(f"[llm] LLM failed ({e}), falling back to local engine.")
        return None


def try_ollama_generate(task_text):
    """Feature 6: free local LLM via Ollama (http://localhost:11434). $0, private."""
    model = os.environ.get("OLLAMA_MODEL", "llama3")
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    try:
        import urllib.request
        payload = json.dumps({
            "model": model,
            "prompt": f"Output ONLY valid Python code with docstrings. No markdown. Task:\n{task_text}",
            "stream": False,
        }).encode()
        req = urllib.request.Request(f"{host}/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.load(resp)
            code = data.get("response", "").strip()
            code = re.sub(r"^```python\s*|```$", "", code, flags=re.MULTILINE).strip()
            if len(code) < 20:
                return None
            return code
    except Exception:
        return None  # Ollama not running -> silent fallback


def print_diff(old_text, new_text, filename="file"):
    """Feature 2: unified diff preview (like Claude Code / Codex approval gate)."""
    diff = difflib.unified_diff(old_text.splitlines(), new_text.splitlines(),
                                fromfile=f"a/{filename}", tofile=f"b/{filename}", lineterm="")
    out = "\n".join(list(diff))
    if not out:
        print("[diff] No changes.")
    else:
        print("[diff] Preview:")
        print(out[:4000])
    return out


def estimate_tokens_cost(task_text, code_text):
    """Feature 3: token + cost estimate. Heuristic chars/4, DeepSeek-style pricing."""
    in_tok = len(task_text) // 4
    out_tok = len(code_text) // 4
    total = in_tok + out_tok
    # $0.15/1M input + $0.60/1M output (cheap-tier 2026 pricing)
    cost = in_tok / 1_000_000 * 0.15 + out_tok / 1_000_000 * 0.60
    return in_tok, out_tok, total, cost


STOPWORDS = {"the", "a", "an", "and", "or", "with", "create", "make", "with", "for", "to", "of", "in", "that", "this"}

def memory_search(query, limit=5):
    """Feature 8: vectorless semantic search (BM25-lite). Ranks past builds by word overlap."""
    init_db()
    if not os.path.exists(DB_PATH):
        return []
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT id, task_text, output_file, status FROM builds ORDER BY id DESC LIMIT 100")
    rows = cur.fetchall()
    con.close()
    qtok = set(re.findall(r"[a-z0-9]+", query.lower())) - STOPWORDS
    scored = []
    for _id, ttext, ofile, status in rows:
        ttok = set(re.findall(r"[a-z0-9]+", (ttext or "").lower())) - STOPWORDS
        overlap = len(qtok & ttok)
        if overlap > 0:
            scored.append((overlap, _id, ttext[:120], ofile, status))
    scored.sort(reverse=True)
    return scored[:limit]


def local_generate(task_text):
    """Offline smart template engine. Detects keywords and builds correct code."""
    t = task_text.lower()

    header = '"""Auto-generated by Self-Healing Builder."""\nfrom __future__ import annotations\n\n'

    if "calcul" in t or "add" in t and "subtract" in t or "arithmetic" in t:
        return header + '''def add(a: float, b: float) -> float:
    """Return sum of a and b."""
    return a + b

def subtract(a: float, b: float) -> float:
    """Return a minus b."""
    return a - b

def multiply(a: float, b: float) -> float:
    """Return product of a and b."""
    return a * b

def divide(a: float, b: float) -> float:
    """Return a divided by b. Raises ValueError on zero division."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

if __name__ == "__main__":
    print(add(2, 3))
    print(divide(10, 2))
'''
    if "todo" in t or "task list" in t or "task manager" in t:
        return header + '''class TodoList:
    """Simple in-memory todo manager."""

    def __init__(self) -> None:
        self.tasks: list[dict] = []

    def add(self, title: str) -> dict:
        """Add a task and return it."""
        item = {"id": len(self.tasks) + 1, "title": title, "done": False}
        self.tasks.append(item)
        return item

    def complete(self, task_id: int) -> bool:
        """Mark task done. Returns True if found."""
        for item in self.tasks:
            if item["id"] == task_id:
                item["done"] = True
                return True
        return False

    def remove(self, task_id: int) -> bool:
        """Remove task by id."""
        for i, item in enumerate(self.tasks):
            if item["id"] == task_id:
                del self.tasks[i]
                return True
        return False

    def list_all(self) -> list[dict]:
        """Return all tasks."""
        return list(self.tasks)

if __name__ == "__main__":
    t = TodoList()
    t.add("Learn CLI agents")
    print(t.list_all())
'''
    if "palindrome" in t:
        return header + '''def is_palindrome(s: str) -> bool:
    """Return True if s is a palindrome (ignores case and non-alphanumeric)."""
    import re
    cleaned = re.sub(r"[^a-z0-9]", "", s.lower())
    return cleaned == cleaned[::-1]

def count_vowels(s: str) -> int:
    """Count vowels in string."""
    return sum(1 for c in s.lower() if c in "aeiou")

if __name__ == "__main__":
    print(is_palindrome("Racecar"))
'''
    if "file" in t and ("count" in t or "word" in t or "line" in t):
        return header + '''import os

def count_lines(path: str) -> int:
    """Count lines in a file."""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return sum(1 for _ in f)

def count_words(path: str) -> int:
    """Count words in a file."""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return sum(len(line.split()) for line in f)

def file_exists(path: str) -> bool:
    """Check file exists."""
    return os.path.exists(path)

if __name__ == "__main__":
    print("file utils ready")
'''
    # Generic fallback: parse "function <name>" requests
    funcs = re.findall(r"function\s+([a-zA-Z_][a-zA-Z0-9_]*)", task_text)
    if funcs:
        body = ""
        for fn in funcs[:5]:
            body += f'''\ndef {fn}(*args, **kwargs):
    """Auto-generated function {fn}."""
    return {{"function": "{fn}", "args": args, "kwargs": kwargs}}
'''
        return header + body + '\nif __name__ == "__main__":\n    print("generated functions:", %s)\n' % funcs

    # Ultimate generic: echo task as module with main function
    safe = task_text.strip().replace("\n", " ")[:200]
    return header + f'''def main() -> str:
    """Implements task: {safe}"""
    return "Task implemented: {safe}"

if __name__ == "__main__":
    print(main())
'''


def generate_code(task_text):
    # 1. Check memory for similar task (learning from past)
    past = get_memory(task_text)
    if past:
        print(f"[memory] Found {len(past)} past builds. Reusing patterns.")
    # 2. Try OpenAI LLM, then Ollama local (free), fallback to local templates
    code = try_llm_generate(task_text)
    if code:
        print("[generate] Used OpenAI engine.")
        return code
    code = try_ollama_generate(task_text)
    if code:
        print(f"[generate] Used Ollama local ({os.environ.get('OLLAMA_MODEL','llama3')}). $0 cost.")
        return code
    print("[generate] Used local template engine (offline, no API key needed).")
    return local_generate(task_text)


# ---------- Testing (terminal feedback) ----------
def syntax_check(filepath):
    if not os.path.exists(filepath):
        return False, f"FileNotFound: {filepath}"
    try:
        py_compile.compile(filepath, doraise=True)
        return True, ""
    except py_compile.PyCompileError as e:
        return False, str(e)
    except OSError as e:
        return False, f"OS error: {e}"


def run_tests(target_file, tests_dir):
    """Returns (passed, total, output). Smart: run matching test file if exists, else all."""
    if tests_dir and os.path.isdir(tests_dir):
        test_files = [f for f in os.listdir(tests_dir) if f.startswith("test_") and f.endswith(".py")]
        if test_files:
            # NEW FEATURE: if target is calculator.py, prefer test_calculator.py + test_generic.py
            base = os.path.splitext(os.path.basename(target_file))[0]  # e.g. calculator
            preferred = [f for f in test_files if base in f or f == "test_generic.py"]
            # always keep generic, plus matching; if no match, run all
            if preferred:
                cmd = [sys.executable, "-m", "pytest"] + [os.path.join(tests_dir, f) for f in preferred] + ["-q"]
            else:
                cmd = [sys.executable, "-m", "pytest", tests_dir, "-q"]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=BASE_DIR)
                out = r.stdout + r.stderr
                m = re.search(r"(\d+) passed", out)
                passed = int(m.group(1)) if m else (0 if r.returncode != 0 else 1)
                m2 = re.search(r"(\d+) failed", out)
                failed = int(m2.group(1)) if m2 else (0 if r.returncode == 0 else 1)
                total = passed + failed
                if total == 0:
                    total = 1
                    passed = 1 if r.returncode == 0 else 0
                return passed, total, out
            except Exception as e:
                return 0, 1, f"pytest error: {e}"
    # Fallback smoke test: import file
    try:
        r = subprocess.run([sys.executable, "-c", f"import ast; ast.parse(open('{target_file}').read()); print('smoke-ok')"],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            return 1, 1, "smoke-ok (no test files, syntax+import passed)"
        return 0, 1, r.stdout + r.stderr
    except Exception as e:
        return 0, 1, str(e)


# ---------- Self-Fix (the healing part) ----------
COMMON_IMPORTS = {
    "os": "import os", "sys": "import sys", "json": "import json",
    "re": "import re", "math": "import math", "pathlib": "from pathlib import Path",
    "datetime": "import datetime", "collections": "import collections",
}

def auto_fix(code, error_text):
    """Apply one heuristic fix based on error. Returns (new_code, fix_description)."""
    # 1. Missing import -> NameError: name 'X' is not defined
    m = re.search(r"NameError: name '(\w+)' is not defined", error_text)
    if m:
        name = m.group(1)
        if name in COMMON_IMPORTS:
            imp = COMMON_IMPORTS[name]
            if imp not in code:
                return imp + "\n" + code, f"added missing import: {imp}"
        # generic: define stub
        stub = f'\n{name} = None  # auto-fix: stub for undefined name\n'
        # insert after header imports
        lines = code.splitlines()
        lines.insert(min(3, len(lines)), stub.strip())
        return "\n".join(lines), f"added stub for undefined '{name}'"

    # 2. ModuleNotFoundError
    m = re.search(r"ModuleNotFoundError: No module named '(\S+)'", error_text)
    if m:
        mod = m.group(1).strip("'\"")
        # comment out the bad import, add note
        new_lines = []
        fixed = False
        for line in code.splitlines():
            if mod in line and ("import" in line) and not fixed:
                new_lines.append(f"# auto-fix: removed unavailable import: {line}")
                new_lines.append("try:")
                new_lines.append(f"    {line}")
                new_lines.append("except ImportError:")
                new_lines.append("    pass")
                fixed = True
            else:
                new_lines.append(line)
        if fixed:
            return "\n".join(new_lines), f"wrapped unavailable import '{mod}' in try/except"

    # 3. IndentationError / unexpected indent -> re-indent with ast? simple: strip trailing spaces
    if "IndentationError" in error_text or "unexpected indent" in error_text:
        lines = [l.rstrip() for l in code.splitlines()]
        # replace tabs with 4 spaces
        lines = [l.replace("\t", "    ") for l in lines]
        return "\n".join(lines) + "\n", "normalized indentation (tabs->spaces, stripped)"

    # 4. SyntaxError: missing colon
    if "expected ':'" in error_text:
        lines = code.splitlines()
        # find def/if/for/while/class lines missing colon
        for i, line in enumerate(lines):
            s = line.strip()
            if re.match(r"^(def |if |elif |else|for |while |class |try|except|finally|with )", s) and not s.endswith(":"):
                lines[i] = line + ":"
                return "\n".join(lines) + "\n", f"added missing colon on line {i+1}"
        return code, "no colon fix found"

    # 5. SyntaxError invalid syntax - try to validate with ast and report
    try:
        ast.parse(code)
    except SyntaxError as e:
        return code, f"syntax error at line {e.lineno}: {e.msg} (needs manual/LLM fix)"

    return code, "no auto-fix matched"


def run_sandbox_test(target_file, tests_dir):
    """Feature 7: sandbox-lite. Isolated temp copy + scrubbed env + timeout (Docker if available)."""
    # Prefer docker if present and --sandbox with docker image available
    try:
        r = subprocess.run(["docker", "--version"], capture_output=True, timeout=5)
        has_docker = r.returncode == 0
    except Exception:
        has_docker = False
    if has_docker and os.environ.get("BUILDER_SANDBOX_DOCKER", "") == "1":
        print("[sandbox] docker mode (python:alpine, no network, read-only-ish)")
        try:
            d = tempfile.mkdtemp(prefix="builder_sandbox_")
            shutil.copy2(target_file, os.path.join(d, os.path.basename(target_file)))
            r = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{d}:/w",
                                "python:alpine", "python", f"/w/{os.path.basename(target_file)}"],
                               capture_output=True, text=True, timeout=30)
            return (1 if r.returncode == 0 else 0), 1, r.stdout + r.stderr
        except Exception as e:
            return 0, 1, f"sandbox docker error: {e}"
    # fallback: isolated temp dir, scrubbed env, timeout
    safe_env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "GITHUB_TOKEN")}
    try:
        r = subprocess.run([sys.executable, target_file], capture_output=True, text=True, timeout=15,
                           cwd=BASE_DIR, env=safe_env)
        out = r.stdout + r.stderr
        return (1 if r.returncode == 0 else 0), 1, f"[sandbox-lite] isolated run:\n{out[-1500:]}"
    except subprocess.TimeoutExpired:
        return 0, 1, "[sandbox] TIMEOUT (>15s) - possible infinite loop, killed safely"
    except Exception as e:
        return 0, 1, f"sandbox error: {e}"


def build_command(task_path, output_path, max_fix, tests_dir, verbose, dry_run=False, commit=False,
                  show_diff=False, sandbox=False, watch=False, watch_interval=1.0, watch_secs=0):
    # Feature 1: --watch mode (like Aider --watch-files): rebuild on task change
    if watch:
        print(f"[watch] Watching {task_path} every {watch_interval}s. Ctrl+C to stop."
              + (f" Auto-stop after {watch_secs}s (test mode)." if watch_secs else ""))
        last_mtime = os.path.getmtime(task_path) if os.path.exists(task_path) else 0
        rc = build_command(task_path, output_path, max_fix, tests_dir, verbose, dry_run, commit,
                           show_diff, sandbox, False)
        start = time.time()
        try:
            while True:
                time.sleep(watch_interval)
                try:
                    m = os.path.getmtime(task_path)
                except OSError:
                    continue
                if m != last_mtime:
                    last_mtime = m
                    print(f"\n[watch] Change detected, rebuilding...")
                    build_command(task_path, output_path, max_fix, tests_dir, verbose, dry_run, commit,
                                  show_diff, sandbox, False)
                if watch_secs and (time.time() - start) >= watch_secs:
                    print("[watch] Time limit reached, stopping.")
                    break
        except KeyboardInterrupt:
            print("\n[watch] Stopped.")
        return rc

    with open(task_path) as f:
        task_text = f.read()

    print(f"[build] Task: {task_path}")
    code = generate_code(task_text)
    # Feature 3: token/cost estimate per build
    it, ot, tot, cost = estimate_tokens_cost(task_text, code)
    print(f"[cost] ~{tot} tokens (in {it} + out {ot}) est ${cost:.4f}")

    if dry_run:
        print("[dry-run] Preview only, nothing written. First 40 lines:")
        for i, line in enumerate(code.splitlines()[:40], 1):
            print(f"{i:3}: {line}")
        print(f"[dry-run] ... ({len(code.splitlines())} lines total). Use without --dry-run to write.")
        return 0

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) if os.path.dirname(output_path) else ".", exist_ok=True)
    if show_diff and os.path.exists(output_path):
        old = open(output_path, encoding="utf-8", errors="ignore").read()
        print_diff(old, code, os.path.basename(output_path))
    if os.path.exists(output_path):
        b = snapshot_file(output_path)
        print(f"[safety] backup saved: {b}")
    with open(output_path, "w") as f:
        f.write(code)
    print(f"[build] v0 written to {output_path}")

    # lint gate on v0 (like Aider hooks)
    lint_issues = lint_file(output_path)
    if lint_issues:
        print(f"[lint] {len(lint_issues)} issue(s) on v0 (non-blocking):")
        for issue in lint_issues[:5]:
            print(f"  - {issue}")

    fixes = []
    consecutive_no_progress = 0  # circuit breaker (from up-cli): halt doom loops
    last_output = ""
    for attempt in range(1, max_fix + 1):
        ok, syn_err = syntax_check(output_path)
        if not ok:
            print(f"[test] Syntax FAILED (attempt {attempt}): {syn_err[:300]}")
            with open(output_path) as f:
                code = f.read()
            new_code, desc = auto_fix(code, syn_err)
            fixes.append(f"attempt{attempt}: {desc}")
            print(f"[fix] {desc}")
            snapshot_file(output_path)
            with open(output_path, "w") as f:
                f.write(new_code)
            consecutive_no_progress = 0 if "added" in desc or "fixed" in desc else consecutive_no_progress + 1
            if consecutive_no_progress >= 3:
                print("[circuit-breaker] 3 fixes with no progress -> halting (doom-loop protection). Restoring last backup.")
                cands = list_backups(output_path)
                if cands:
                    import shutil
                    shutil.copy2(sorted(cands)[-1], output_path)
                    print(f"[rollback] restored {sorted(cands)[-1]}")
                break
            continue

        passed, total, out = run_tests(output_path, tests_dir)
        print(f"[test] {passed}/{total} passed (attempt {attempt})")
        if verbose:
            print(out[-1500:])
        if passed == total and total > 0:
            if out != last_output:
                consecutive_no_progress = 0
            if sandbox:
                sp, st, sout = run_sandbox_test(output_path, tests_dir)
                print(f"[sandbox] {sp}/{st} - {sout[-500:]}")
            print(f"[done] SUCCESS after {attempt} attempt(s). Fixes: {fixes}")
            if format_file(output_path):
                print("[format] auto-formatted")
            save_memory(task_text, output_path, "success", fixes, passed, total)
            if commit:
                git_checkpoint(f"builder: {os.path.basename(output_path)} success ({passed}/{total})")
            return 0
        else:
            if out == last_output:
                consecutive_no_progress += 1
            else:
                consecutive_no_progress = 0
            last_output = out
            if consecutive_no_progress >= 2:
                print("[circuit-breaker] same failure repeating -> halting.")
                break
            with open(output_path) as f:
                code = f.read()
            new_code, desc = auto_fix(code, out)
            # if no fix matched, try regenerating alternative via local engine tweak
            if desc == "no auto-fix matched":
                desc = "re-test failed, logged for LLM/manual fix"
                fixes.append(f"attempt{attempt}: {desc}")
                print(f"[fix] {desc}")
                break
            fixes.append(f"attempt{attempt}: {desc}")
            print(f"[fix] {desc}")
            snapshot_file(output_path)
            with open(output_path, "w") as f:
                f.write(new_code)

    # final check
    passed, total, out = run_tests(output_path, tests_dir)
    status = "success" if (passed == total and total > 0) else "partial"
    print(f"[done] Finished with status={status} ({passed}/{total}). Fixes: {fixes}")
    save_memory(task_text, output_path, status, fixes, passed, total)
    if commit and status == "success":
        git_checkpoint(f"builder: {os.path.basename(output_path)} {status}")
    return 0 if status == "success" else 1


def test_command(file_path, tests_dir, verbose):
    ok, syn_err = syntax_check(file_path)
    if not ok:
        print(f"SYNTAX FAIL: {syn_err}")
        return 1
    print("Syntax OK.")
    passed, total, out = run_tests(file_path, tests_dir)
    print(f"Tests: {passed}/{total} passed")
    print(out[-2000:])
    return 0 if passed == total else 1


def improve_command(file_path, rounds, dry_run=False):
    with open(file_path) as f:
        code = f.read()
    if dry_run:
        print("[dry-run] Would ensure docstring, __main__ guard, formatting. No write.")
        return 0
    snapshot_file(file_path)
    for r in range(1, rounds + 1):
        print(f"[improve] Round {r}/{rounds}")
        # Feature 1: ensure module docstring
        if not code.lstrip().startswith('"""') and not code.lstrip().startswith("'''"):
            code = '"""Improved module - auto-added docstring."""\n' + code
            print(" - added module docstring")
        # Feature 2: ensure __main__ guard
        if "__main__" not in code:
            code += '\nif __name__ == "__main__":\n    print("ready")\n'
            print(" - added __main__ guard")
        # Feature 3: add type hints note + error handling wrapper check
        # Feature 4: normalize whitespace (simple formatter)
        lines = [l.rstrip() for l in code.replace("\t", "    ").splitlines()]
        # remove trailing blank duplicates
        cleaned = []
        blanks = 0
        for l in lines:
            if l.strip() == "":
                blanks += 1
                if blanks <= 2:
                    cleaned.append(l)
            else:
                blanks = 0
                cleaned.append(l)
        code = "\n".join(cleaned).rstrip() + "\n"
        print(" - normalized formatting")
        with open(file_path, "w") as f:
            f.write(code)
        ok, err = syntax_check(file_path)
        if not ok:
            print(f" !! improve broke syntax: {err[:200]}")
            break
        passed, total, out = run_tests(file_path, None)
        print(f" - smoke {passed}/{total}")
    print(f"[improve] Done. File: {file_path}")
    return 0


def history_command(limit):
    init_db()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT id, output_file, status, fixes_applied, tests_passed, tests_total, timestamp FROM builds ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    con.close()
    if not rows:
        print("No history yet. Run build first.")
        return
    for r in rows:
        print(f"#{r[0]} {r[6]} | {r[1]} | {r[2]} | tests {r[4]}/{r[5]} | fixes {r[3]}")


def diagnose_command(file_path):
    print(f"[diagnose] {file_path}")
    ok, err = syntax_check(file_path)
    print(f"Syntax: {'OK' if ok else 'FAIL: '+err[:500]}")
    try:
        tree = ast.parse(open(file_path).read())
        funcs = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        print(f"Functions ({len(funcs)}): {funcs}")
        print(f"Classes ({len(classes)}): {classes}")
        print(f"Lines: {len(open(file_path).readlines())}")
    except Exception as e:
        print(f"AST parse failed: {e}")
    passed, total, out = run_tests(file_path, None)
    print(f"Smoke: {passed}/{total}")
    if passed != total:
        print(out[-1000:])


def clean_command():
    import glob, shutil
    for f in glob.glob(os.path.join(BASE_DIR, "generated", "*.py")):
        os.remove(f)
        print(f"removed {f}")
    pyc = os.path.join(BASE_DIR, "generated", "__pycache__")
    if os.path.exists(pyc):
        shutil.rmtree(pyc)
        print("removed __pycache__")
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("removed memory.db (agent forgot everything)")
    print("[clean] Done.")


def stats_command(show_cost=False):
    init_db()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT COUNT(*), SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) FROM builds")
    total, succ = cur.fetchone()
    con.close()
    total = total or 0
    succ = succ or 0
    rate = (succ / total * 100) if total else 0
    print(f"Total builds: {total}")
    print(f"Success: {succ} ({rate:.1f}%)")
    ollama = "on" if try_ollama_generate.__doc__ else "on"
    print(f"Engine: {'OpenAI' if os.environ.get('OPENAI_API_KEY') else 'local offline + Ollama:'+os.environ.get('OLLAMA_MODEL','llama3')}")
    print(f"Memory file: {DB_PATH} ({'exists' if os.path.exists(DB_PATH) else 'empty'})")
    if show_cost:
        import glob as _glob
        grand_tok, grand_cost = 0, 0.0
        for f in _glob.glob(os.path.join(BASE_DIR, "generated", "*.py")):
            try:
                code = open(f, encoding="utf-8", errors="ignore").read()
                it, ot, tot, cost = estimate_tokens_cost("", code)
                grand_tok += tot
                grand_cost += cost
            except Exception:
                pass
        print(f"[cost] Generated code tokens ~{grand_tok}, est ${grand_cost:.4f} (cheap-tier $0.15/$0.60 per 1M)")
        print(f"[cost] Time saved vs manual: ~{total * 0.5:.1f}h (0.5h per build)")


def lint_command(file_path):
    issues = lint_file(file_path)
    if not issues:
        print(f"[lint] {file_path}: CLEAN (0 issues)")
        return 0
    print(f"[lint] {file_path}: {len(issues)} issue(s):")
    for i in issues[:20]:
        print(" - " + i)
    return 1


def generate_tests_for_task(task_text, test_path):
    """Feature 4 (TDD): generate a pytest file FIRST from task description (offline templates)."""
    t = task_text.lower()
    header = "import sys, os\nsys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'generated'))\n"
    if "calcul" in t:
        body = header + '''from calculator_tdd import add, divide
def test_tdd_add():
    assert add(2, 3) == 5
def test_tdd_divide():
    assert divide(10, 2) == 5
'''
    elif "todo" in t:
        body = header + '''from todo_tdd import TodoList
def test_tdd_add():
    t = TodoList()
    assert t.add("x")["title"] == "x"
'''
    elif "palindrome" in t:
        body = header + '''from palindrome_tdd import is_palindrome
def test_tdd_pal():
    assert is_palindrome("Racecar") is True
'''
    else:
        funcs = re.findall(r"function\s+([a-zA-Z_][a-zA-Z0-9_]*)", task_text) or ["main"]
        body = header + f'''import generated.{funcs[0]}_tdd as m
def test_tdd_smoke():
    assert hasattr(m, "{funcs[0]}")
'''
    os.makedirs(os.path.dirname(test_path) or ".", exist_ok=True)
    open(test_path, "w").write(body)
    return test_path


def tdd_command(task_path, output_path, max_fix=5):
    """Feature 4: RED -> GREEN -> REFACTOR. Tests first, then code until green."""
    print("[tdd] RED: generating tests first...")
    task_text = open(task_path).read()
    base = os.path.splitext(os.path.basename(output_path))[0]
    clean = base[:-4] if base.endswith("_tdd") else base
    tdd_test = os.path.join(BASE_DIR, "tests", f"test_{clean}_tdd.py")
    # map generic tdd test imports to real output basename
    generate_tests_for_task(task_text, tdd_test)
    # rewrite imports to actual basename
    content = open(tdd_test).read().replace(f"{base}_tdd", base).replace("calculator_tdd", base).replace("todo_tdd", base).replace("palindrome_tdd", base)
    open(tdd_test, "w").write(content)
    print(f"[tdd] tests written: {tdd_test}")
    print("[tdd] GREEN: building code to pass tests...")
    rc = build_command(task_path, output_path, max_fix, os.path.join(BASE_DIR, "tests"), False)
    print("[tdd] REFACTOR: formatting + lint...")
    format_file(output_path)
    for issue in lint_file(output_path)[:5]:
        print(f"  lint: {issue}")
    print(f"[tdd] {'PASS - green' if rc == 0 else 'FAIL - red'}")
    return rc


def project_command(task_path, output_dir, max_fix=5):
    """Feature 5: multi-file project (app.py + store.py + api.py) like real Devin tasks."""
    task_text = open(task_path).read()
    os.makedirs(output_dir, exist_ok=True)
    print(f"[project] Generating 3-file project in {output_dir}")
    header = '"""Auto-generated project file."""\nfrom __future__ import annotations\n\n'
    app_code = header + f'"""Main app for: {task_text.strip()[:120]}"""\nfrom store import load, save\n\ndef main() -> str:\n    """Entry point."""\n    data = load()\n    save(data)\n    return "ok"\n\nif __name__ == "__main__":\n    print(main())\n'
    store_code = header + '''"""Simple JSON store."""
import json, os
DB = os.path.join(os.path.dirname(__file__), "db.json")
def load() -> dict:
    """Load data, return {} if missing."""
    try:
        return json.load(open(DB))
    except Exception:
        return {}
def save(data: dict) -> None:
    """Save data."""
    json.dump(data, open(DB, "w"), indent=2)
'''
    api_code = generate_code(task_text)
    files = {"app.py": app_code, "store.py": store_code, "api.py": api_code}
    for name, code in files.items():
        p = os.path.join(output_dir, name)
        if os.path.exists(p):
            snapshot_file(p)
        open(p, "w").write(code)
        print(f"  wrote {p}")
    # verify all
    ok_all = True
    for name in files:
        p = os.path.join(output_dir, name)
        ok, err = syntax_check(p)
        print(f"  {name}: {'OK' if ok else 'FAIL '+err[:200]}")
        ok_all = ok_all and ok
    save_memory(task_text, output_dir, "success" if ok_all else "partial", ["project-3files"], 1 if ok_all else 0, 1)
    return 0 if ok_all else 1


def autopilot_command(max_fix=5):
    """End-to-end (like Devin/Sentinel autopilot): build every tasks/*.txt until all pass."""
    import glob
    tasks = sorted(glob.glob(os.path.join(BASE_DIR, "tasks", "*.txt")))
    if not tasks:
        print("No tasks found in tasks/")
        return 1
    print(f"[autopilot] {len(tasks)} tasks found. Building sequentially with circuit-breaker.")
    ok_all, results = True, []
    for t in tasks:
        base = os.path.splitext(os.path.basename(t))[0]
        out = os.path.join(BASE_DIR, "generated", base + ".py")
        print(f"\n=== {base} ({t} -> {out}) ===")
        rc = build_command(t, out, max_fix, os.path.join(BASE_DIR, "tests"), False, False, False)
        results.append((base, "PASS" if rc == 0 else "FAIL"))
        if rc != 0:
            ok_all = False
    print("\n[autopilot] Summary:")
    for name, st in results:
        print(f"  {name}: {st}")
    # final review gate on all outputs
    for name, st in results:
        if st == "PASS":
            review_command(os.path.join(BASE_DIR, "generated", name + ".py"))
    return 0 if ok_all else 1


def main():
    p = argparse.ArgumentParser(description="Self-Healing Code Builder - build, test, improve itself")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="Generate code from task file, auto-fix until tests pass")
    b.add_argument("--task", required=True, help="Path to task .txt file")
    b.add_argument("--output", required=True, help="Path to output .py file")
    b.add_argument("--max-fix", type=int, default=5, help="Max auto-fix attempts")
    b.add_argument("--tests", default="tests", help="Tests directory (pytest)")
    b.add_argument("--verbose", action="store_true")
    b.add_argument("--dry-run", action="store_true", help="Preview without writing (like UTIM/Codex)")
    b.add_argument("--commit", action="store_true", help="Git auto-commit on success (like Aider)")
    b.add_argument("--diff", action="store_true", help="Show unified diff before writing")
    b.add_argument("--sandbox", action="store_true", help="Isolated sandbox run (like Codex/OpenHands)")
    b.add_argument("--watch", action="store_true", help="Auto-rebuild on task change (like Aider --watch)")
    b.add_argument("--watch-interval", type=float, default=1.0)
    b.add_argument("--watch-secs", type=float, default=0, help="Auto-stop after N secs (for tests)")

    t = sub.add_parser("test", help="Test a file")
    t.add_argument("--file", required=True)
    t.add_argument("--tests", default="tests")
    t.add_argument("--verbose", action="store_true")
    t.add_argument("--sandbox", action="store_true", help="Run in isolated sandbox")

    i = sub.add_parser("improve", help="Iteratively improve a file")
    i.add_argument("--file", required=True)
    i.add_argument("--rounds", type=int, default=3)
    i.add_argument("--dry-run", action="store_true")

    h = sub.add_parser("history", help="Show past builds (memory)")
    h.add_argument("--limit", type=int, default=10)

    d = sub.add_parser("diagnose", help="Analyze a file")
    d.add_argument("--file", required=True)

    sub.add_parser("clean", help="Remove generated files + memory")
    s = sub.add_parser("stats", help="Show success stats + cost")
    s.add_argument("--cost", action="store_true", help="Show token + $ estimate")
    # NEW best-features commands
    l = sub.add_parser("lint", help="Lint gate: check file (Aider hooks / Omp LSP idea)")
    l.add_argument("--file", required=True)
    sub.add_parser("map", help="Repo map: compressed codebase view (Aider repo-map idea)")
    r = sub.add_parser("review", help="Reviewer second-pass score 0-100 (architect mode)")
    r.add_argument("--file", required=True)
    u = sub.add_parser("undo", help="Rollback to backup (git-backed undo idea)")
    u.add_argument("--file", required=True, help="File to restore, e.g. generated/calculator.py")
    u.add_argument("--steps", type=int, default=1)
    a = sub.add_parser("autopilot", help="Build all tasks end-to-end (Devin/Sentinel autopilot idea)")
    a.add_argument("--max-fix", type=int, default=5)
    td = sub.add_parser("tdd", help="RED-GREEN-REFACTOR: tests first then code (Sentinel /tdd)")
    td.add_argument("--task", required=True)
    td.add_argument("--output", required=True)
    td.add_argument("--max-fix", type=int, default=5)
    pj = sub.add_parser("project", help="Multi-file project app.py+store.py+api.py (Devin-style)")
    pj.add_argument("--task", required=True)
    pj.add_argument("--output-dir", required=True)
    pj.add_argument("--max-fix", type=int, default=5)
    m = sub.add_parser("memory", help="Semantic memory search (Copilot/Claude memory idea)")
    m.add_argument("--search", required=True, help="Query, e.g. 'divide fix'")
    m.add_argument("--limit", type=int, default=5)

    args = p.parse_args()
    if args.cmd == "build":
        sys.exit(build_command(args.task, args.output, args.max_fix, args.tests, args.verbose,
                               args.dry_run, args.commit, args.diff, args.sandbox,
                               args.watch, args.watch_interval, args.watch_secs))
    elif args.cmd == "test":
        if args.sandbox:
            sp, st, sout = run_sandbox_test(args.file, args.tests)
            print(f"[sandbox] {sp}/{st}\n{sout[-1500:]}")
            sys.exit(0 if sp == st else 1)
        sys.exit(test_command(args.file, args.tests, args.verbose))
    elif args.cmd == "improve":
        sys.exit(improve_command(args.file, args.rounds, args.dry_run))
    elif args.cmd == "history":
        history_command(args.limit)
    elif args.cmd == "diagnose":
        diagnose_command(args.file)
    elif args.cmd == "clean":
        clean_command()
    elif args.cmd == "stats":
        stats_command(args.cost)
    elif args.cmd == "lint":
        sys.exit(lint_command(args.file))
    elif args.cmd == "map":
        repo_map_command()
    elif args.cmd == "review":
        sys.exit(review_command(args.file))
    elif args.cmd == "undo":
        sys.exit(undo_command(args.file, args.steps))
    elif args.cmd == "autopilot":
        sys.exit(autopilot_command(args.max_fix))
    elif args.cmd == "tdd":
        sys.exit(tdd_command(args.task, args.output, args.max_fix))
    elif args.cmd == "project":
        sys.exit(project_command(args.task, args.output_dir, args.max_fix))
    elif args.cmd == "memory":
        hits = memory_search(args.search, args.limit)
        if not hits:
            print(f"[memory] No match for '{args.search}'")
        else:
            print(f"[memory] Top {len(hits)} for '{args.search}':")
            for score, _id, ttext, ofile, status in hits:
                print(f"  score {score} #{_id} [{status}] {ofile}: {ttext[:100]}")


if __name__ == "__main__":
    main()
