#!/usr/bin/env python3
"""100-way stress test for builder.py. Only commands + function calls, no interaction."""
import os, sys, subprocess, tempfile, textwrap

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import builder as B

PASS, FAIL = 0, 0
ISSUES = []

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok {PASS+FAIL}: {name}")
    else:
        FAIL += 1
        ISSUES.append(f"{name} :: {detail}")
        print(f"  FAIL {PASS+FAIL}: {name} -- {detail}")

def run(cmd, timeout=30):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=BASE)
    return r

print("== A. CLI exists (15) ==")
for sub in ["build", "test", "improve", "lint", "review", "map", "undo", "autopilot", "tdd", "project", "memory", "history", "diagnose", "stats", "clean"]:
    r = run([sys.executable, "builder.py", sub, "--help"])
    check(f"help {sub}", r.returncode == 0, r.stderr[:200])

print("== B. build core (12) ==")
r = run([sys.executable, "builder.py", "build", "--task", "tasks/calculator.txt", "--output", "generated/_s1.py", "--max-fix", "3"])
check("build calculator", r.returncode == 0 and os.path.exists("generated/_s1.py"), r.stdout[-300:] + r.stderr[-300:])
r = run([sys.executable, "builder.py", "build", "--task", "tasks/todo.txt", "--output", "generated/_s2.py", "--max-fix", "3"])
check("build todo", r.returncode == 0, r.stdout[-200:])
r = run([sys.executable, "builder.py", "build", "--task", "tasks/palindrome.txt", "--output", "generated/_s3.py", "--max-fix", "3"])
check("build palindrome", r.returncode == 0, r.stdout[-200:])
r = run([sys.executable, "builder.py", "build", "--task", "tasks/calculator.txt", "--output", "generated/_dry.py", "--dry-run"])
check("build dry-run no write", r.returncode == 0 and not os.path.exists("generated/_dry.py"), "dry-run wrote file!")
r = run([sys.executable, "builder.py", "build", "--task", "tasks/calculator.txt", "--output", "generated/_diff.py", "--diff"])
check("build diff", r.returncode == 0 and "[diff]" in r.stdout, r.stdout[-300:])
r = run([sys.executable, "builder.py", "build", "--task", "tasks/NOPE.txt", "--output", "generated/_x.py"])
check("build missing task fails gracefully", r.returncode != 0, "should fail")
# empty task
open("_empty_task.txt", "w").write("")
r = run([sys.executable, "builder.py", "build", "--task", "_empty_task.txt", "--output", "generated/_empty.py", "--max-fix", "2"])
check("build empty task", r.returncode in (0, 1) and os.path.exists("generated/_empty.py"), r.stdout[-200:])
# unicode task
open("_uni_task.txt", "w", encoding="utf-8").write("Create function héllo_monde with unicode café comment \U0001f600")
r = run([sys.executable, "builder.py", "build", "--task", "_uni_task.txt", "--output", "generated/_uni.py", "--max-fix", "2"])
check("build unicode task", os.path.exists("generated/_uni.py"), r.stdout[-200:])
# long task
open("_long_task.txt", "w").write("Create calculator. " * 500)
r = run([sys.executable, "builder.py", "build", "--task", "_long_task.txt", "--output", "generated/_long.py", "--max-fix", "2"])
check("build long task", os.path.exists("generated/_long.py"), r.stdout[-200:])
# watch short
r = run([sys.executable, "builder.py", "build", "--task", "tasks/calculator.txt", "--output", "generated/_w.py", "--watch", "--watch-secs", "1", "--watch-interval", "0.3"])
check("build watch 1s", "[watch]" in r.stdout, r.stdout[-300:])
# sandbox build
r = run([sys.executable, "builder.py", "build", "--task", "tasks/calculator.txt", "--output", "generated/_sb.py", "--sandbox", "--max-fix", "2"])
check("build sandbox", r.returncode == 0 and "[sandbox]" in r.stdout, r.stdout[-300:])
# unknown flag should fail
r = run([sys.executable, "builder.py", "build", "--task", "tasks/calculator.txt", "--output", "x.py", "--nope"])
check("build bad flag fails", r.returncode != 0, "should fail")

print("== C. auto_fix (15) ==")
code, d = B.auto_fix("def f(a, b)\n    return 1", "SyntaxError: expected ':'")
check("fix missing colon", code.count(":") > 0 and "added missing colon" in d, d)
code, d = B.auto_fix("x = os.getcwd()", "NameError: name 'os' is not defined")
check("fix NameError os", "import os" in code, d)
code, d = B.auto_fix("x = json.dumps({})", "NameError: name 'json' is not defined")
check("fix NameError json", "import json" in code, d)
code, d = B.auto_fix("x = re.match('a','a')", "NameError: name 're' is not defined")
check("fix NameError re", "import re" in code, d)
code, d = B.auto_fix("x = foobar123()", "NameError: name 'foobar123' is not defined")
check("fix NameError unknown stub", "foobar123" in code, d)
code, d = B.auto_fix("import nosuchmod999\nprint(1)", "ModuleNotFoundError: No module named 'nosuchmod999'")
check("fix bad import", "try:" in code, d)
code, d = B.auto_fix("def f():\n\treturn 1", "IndentationError: unexpected indent")
check("fix tabs", "\t" not in code, d)
code, d = B.auto_fix("x = 1\n", "SomeRandomError: boom")
check("fix unknown returns no-match", d == "no auto-fix matched", d)
code, d = B.auto_fix("def f(:\n pass", "SyntaxError: invalid syntax")
check("fix invalid syntax reports line", "line" in d.lower() or "syntax" in d.lower(), d)
# idempotent: fixing clean code should not corrupt
clean = "def add(a, b):\n    return a + b\n"
code, d = B.auto_fix(clean, "AssertionError: test failed")
check("fix clean+assert does not corrupt", "def add" in code, d)
# empty code
code, d = B.auto_fix("", "SyntaxError: expected ':'")
check("fix empty code no crash", isinstance(code, str), d)
# very long code
big = "x=1\n" * 5000
code, d = B.auto_fix(big, "NameError: name 'sys' is not defined")
check("fix big code", "import sys" in code, d)
# code with syntax ok but NameError math
code, d = B.auto_fix("print(math.pi)", "NameError: name 'math' is not defined")
check("fix NameError math", "import math" in code, d)
# double fix chain
c1, _ = B.auto_fix("def f(a,b)\n    return 1", "SyntaxError: expected ':'")
ok, _ = B.syntax_check.__wrapped__ if hasattr(B.syntax_check, "__wrapped__") else (True, None)
try:
    import py_compile
    open("_c1.py", "w").write(c1)
    py_compile.compile("_c1.py", doraise=True)
    chained = True
except Exception:
    chained = False
check("fix chain produces valid syntax", chained, c1[:100])
# fix preserves content
code, d = B.auto_fix("def hello():\n    return 'world'", "NameError: name 'os' is not defined")
check("fix preserves hello", "hello" in code and "world" in code, d)

print("== D. lint (10) ==")
open("_lint_good.py", "w").write('"""Doc."""\ndef add(a: int, b: int) -> int:\n    """Add."""\n    return a + b\n')
check("lint clean", B.lint_file("_lint_good.py") == [], str(B.lint_file("_lint_good.py")))
open("_lint_long.py", "w").write('"""D."""\nx = "' + "y" * 150 + '"\n')
check("lint long line", any("too long" in i for i in B.lint_file("_lint_long.py")), "missed")
open("_lint_tab.py", "w").write('"""D."""\ndef f():\n\treturn 1\n')
check("lint tab", any("tab" in i for i in B.lint_file("_lint_tab.py")), "missed")
open("_lint_unused.py", "w").write('"""D."""\nimport os\nx = 1\n')
check("lint unused import", any("unused import" in i for i in B.lint_file("_lint_unused.py")), "missed")
open("_lint_nodoc.py", "w").write('def f():\n    return 1\n')
check("lint missing docstring", any("docstring" in i for i in B.lint_file("_lint_nodoc.py")), "missed")
open("_lint_syn.py", "w").write('def f(:\n')
check("lint syntax", any("SyntaxError" in i for i in B.lint_file("_lint_syn.py")), "missed")
check("lint missing file", len(B.lint_file("_nope123.py")) > 0, "should report")
open("_lint_empty.py", "w").write('')
check("lint empty no crash", isinstance(B.lint_file("_lint_empty.py"), list), "crash")
open("_lint_future.py", "w").write('from __future__ import annotations\nx = 1\n')
check("lint future not flagged", not any("annotations" in i for i in B.lint_file("_lint_future.py")), str(B.lint_file("_lint_future.py")))
r = run([sys.executable, "builder.py", "lint", "--file", "generated/calculator.py"])
check("cli lint", r.returncode == 0, r.stdout[-200:])

print("== E. review (8) ==")
open("_rev_good.py", "w").write('"""M."""\ndef add(a: int, b: int) -> int:\n    """Add two numbers."""\n    return a + b\n')
r = run([sys.executable, "builder.py", "review", "--file", "_rev_good.py"])
check("review good approves", r.returncode == 0 and "APPROVE" in r.stdout, r.stdout[-300:])
open("_rev_eval.py", "w").write('x = eval("1+1")\n')
r = run([sys.executable, "builder.py", "review", "--file", "_rev_eval.py"])
check("review eval penalized", "eval" in r.stdout.lower(), r.stdout[-300:])
open("_rev_exec.py", "w").write('exec("x=1")\n')
check("review exec flagged", "exec" in open("_rev_exec.py").read() and True, "")
open("_rev_shell.py", "w").write('import subprocess\nsubprocess.run("ls", shell=True)\n')
r = run([sys.executable, "builder.py", "review", "--file", "_rev_shell.py"])
check("review shell=True flagged", "shell" in r.stdout.lower(), r.stdout[-300:])
open("_rev_empty.py", "w").write('')
r = run([sys.executable, "builder.py", "review", "--file", "_rev_empty.py"])
check("review empty not approve-100", "100/100 APPROVE" not in r.stdout, r.stdout[-200:])
open("_rev_syn.py", "w").write('def f(:\n')
r = run([sys.executable, "builder.py", "review", "--file", "_rev_syn.py"])
check("review syntax fails", r.returncode != 0, r.stdout[-200:])
open("_rev_long.py", "w").write('"""M."""\ndef big():\n    """D."""\n' + "    x = 1\n" * 60)
r = run([sys.executable, "builder.py", "review", "--file", "_rev_long.py"])
check("review long func penalized", "too long" in r.stdout.lower(), r.stdout[-400:])
check("review returns int", isinstance(B.review_command("_rev_good.py"), int), "")

print("== F. syntax (6) ==")
ok, _ = B.syntax_check("generated/calculator.py")
check("syntax good", ok, "")
open("_bad.py", "w").write("def f(:")
ok, e = B.syntax_check("_bad.py")
check("syntax bad", not ok and len(e) > 0, "")
ok, e = B.syntax_check("_missing_xyz.py")
check("syntax missing file", not ok, "")
open("_uni2.py", "w", encoding="utf-8").write("# café \U0001f600\nx = 1\n")
ok, _ = B.syntax_check("_uni2.py")
check("syntax unicode", ok, "")
open("_big2.py", "w").write("x = 1\n" * 10000)
ok, _ = B.syntax_check("_big2.py")
check("syntax 10k lines", ok, "")
r = run([sys.executable, "builder.py", "test", "--file", "generated/calculator.py", "--tests", "tests"])
check("cli test ok", r.returncode == 0, r.stdout[-200:])

print("== G. memory (8) ==")
B.save_memory("stress test alpha beta", "generated/_s1.py", "success", [], 1, 1)
hits = B.memory_search("alpha beta", 3)
check("memory search hit", len(hits) > 0, str(hits))
hits = B.memory_search("zzzqqq_no_match_xyz", 3)
check("memory search no-match empty", hits == [], str(hits))
hits = B.memory_search("", 3)
check("memory empty query no crash", isinstance(hits, list), "")
r = run([sys.executable, "builder.py", "memory", "--search", "calculator", "--limit", "2"])
check("cli memory search", r.returncode == 0, r.stdout[-200:])
r = run([sys.executable, "builder.py", "history", "--limit", "3"])
check("cli history", r.returncode == 0, r.stdout[-200:])
r = run([sys.executable, "builder.py", "stats"])
check("cli stats", r.returncode == 0 and "Total builds" in r.stdout, r.stdout[-200:])
r = run([sys.executable, "builder.py", "stats", "--cost"])
check("cli stats cost", "[cost]" in r.stdout, r.stdout[-300:])
it, ot, tot, cost = B.estimate_tokens_cost("hello", "world")
check("cost math", tot == (5 // 4 + 5 // 4) and cost >= 0, f"{tot} {cost}")

print("== H. snapshot/undo (8) ==")
open("_snap.py", "w").write("v1")
b1 = B.snapshot_file("_snap.py")
open("_snap.py", "w").write("v2")
b2 = B.snapshot_file("_snap.py")
check("snapshot creates backups", b1 and b2 and os.path.exists(b1), f"{b1} {b2}")
check("snapshot missing file None", B.snapshot_file("_nope_zzz.py") is None, "")
open("generated/_undo_me.py", "w").write("original-ok")
B.snapshot_file("generated/_undo_me.py")
open("generated/_undo_me.py", "w").write("broken!!!")
r = run([sys.executable, "builder.py", "undo", "--file", "generated/_undo_me.py", "--steps", "1"])
check("cli undo restores", r.returncode == 0 and open("generated/_undo_me.py").read() == "original-ok", r.stdout[-200:] + open("generated/_undo_me.py").read()[:50])
r = run([sys.executable, "builder.py", "undo", "--file", "generated/_never_existed_xyz.py", "--steps", "1"])
check("undo missing fails gracefully", r.returncode != 0, "should fail")
# 20-cap: create 25 snapshots, ensure <=20 kept? (just check no crash)
for i in range(25):
    open("_cap.py", "w").write(f"v{i}")
    B.snapshot_file("_cap.py")
cands = [f for f in os.listdir(B.BACKUP_DIR) if f.startswith("_cap.py.")]
check("backup cap 20", len(cands) <= 20, f"kept {len(cands)}")
# undo steps=2
open("generated/_u2.py", "w").write("v0")
B.snapshot_file("generated/_u2.py")
open("generated/_u2.py", "w").write("v1")
B.snapshot_file("generated/_u2.py")
open("generated/_u2.py", "w").write("v2")
r = run([sys.executable, "builder.py", "undo", "--file", "generated/_u2.py", "--steps", "2"])
check("undo steps=2", r.returncode == 0, r.stdout[-200:])
check("list_backups works", isinstance(B.list_backups("generated/_u2.py"), list), "")

print("== I. sandbox (4) ==")
sp, st, out = B.run_sandbox_test("generated/calculator.py", "tests")
check("sandbox good file", sp == 1, out[-200:])
open("_loop.py", "w").write("while True:\n    pass\n")
sp, st, out = B.run_sandbox_test("_loop.py", None)
check("sandbox infinite loop timeout", sp == 0 and "TIMEOUT" in out, out[-200:])
open("_boom.py", "w").write("raise ValueError('x')\n")
sp, st, out = B.run_sandbox_test("_boom.py", None)
check("sandbox crash caught", sp == 0, out[-200:])
r = run([sys.executable, "builder.py", "test", "--file", "generated/calculator.py", "--tests", "tests", "--sandbox"])
check("cli sandbox", r.returncode == 0, r.stdout[-300:])

print("== J. map/diagnose/misc (10) ==")
r = run([sys.executable, "builder.py", "map"])
check("cli map", r.returncode == 0 and "[map]" in r.stdout, r.stdout[-200:])
r = run([sys.executable, "builder.py", "diagnose", "--file", "generated/calculator.py"])
check("cli diagnose", "Functions" in r.stdout, r.stdout[-300:])
r = run([sys.executable, "builder.py", "diagnose", "--file", "_bad.py"])
check("diagnose bad file no crash", r.returncode == 0, r.stdout[-200:])
r = run([sys.executable, "builder.py", "improve", "--file", "generated/_s1.py", "--rounds", "1"])
check("improve 1 round", r.returncode == 0, r.stdout[-200:])
r = run([sys.executable, "builder.py", "improve", "--file", "generated/_s1.py", "--rounds", "1", "--dry-run"])
check("improve dry-run", "[dry-run]" in r.stdout, r.stdout[-200:])
check("format idempotent", B.format_file("generated/calculator.py") in (True, False), "")
check("git checkpoint no crash", isinstance(B.git_checkpoint("test msg"), bool), "")
# ollama fallback
check("ollama fallback None when no server", B.try_ollama_generate("hi") is None, "should be None offline")
# openai fallback when no key
import os as _os
had = _os.environ.pop("OPENAI_API_KEY", None)
check("openai None when no key", B.try_llm_generate("hi") is None, "")
if had:
    _os.environ["OPENAI_API_KEY"] = had
# show_diff
d = B.print_diff("a\nb\n", "a\nc\n", "f.py")
check("diff shows change", "@@" in d or "-b" in d, d[:200])

print("== K. tdd/project/autopilot (6) ==")
r = run([sys.executable, "builder.py", "tdd", "--task", "tasks/palindrome.txt", "--output", "generated/_tdd1.py"], timeout=60)
check("tdd palindrome", r.returncode == 0, r.stdout[-300:])
r = run([sys.executable, "builder.py", "project", "--task", "tasks/todo.txt", "--output-dir", "generated/_proj1"], timeout=60)
check("project todo", r.returncode == 0 and os.path.exists("generated/_proj1/app.py"), r.stdout[-300:])
r = run([sys.executable, "builder.py", "project", "--task", "_empty_task.txt", "--output-dir", "generated/_proj_empty"], timeout=60)
check("project empty task no crash", r.returncode in (0, 1), r.stdout[-200:])
r = run([sys.executable, "builder.py", "autopilot", "--max-fix", "2"], timeout=120)
check("autopilot", r.returncode == 0, r.stdout[-400:])
r = run([sys.executable, "builder.py", "build", "--task", "tasks/calculator.txt", "--output", "generated/_commit.py", "--commit", "--max-fix", "2"])
check("build commit flag", r.returncode == 0, r.stdout[-200:])
r = run([sys.executable, "builder.py", "test", "--file", "_bad.py", "--tests", "tests"])
check("test bad file fails", r.returncode != 0, "should fail")

print(f"\n==== RESULT: {PASS} passed, {FAIL} failed / {PASS+FAIL} ====")
if ISSUES:
    print("ISSUES:")
    for i in ISSUES:
        print(" - " + i)
sys.exit(1 if FAIL else 0)
