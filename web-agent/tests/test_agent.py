import json, os, subprocess, sys
import agent
from agent import human_cursor_path, human_scroll_plan, human_type_plan, parse_task

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
AG = os.path.join(BASE, "agent.py")

def test_bezier_path_shape():
    pts = human_cursor_path(0, 0, 100, 0, steps=10, seed=1)
    assert len(pts) == 11
    assert pts[0][0] == 0 and pts[-1][0] == 100  # starts/ends exact

def test_scroll_sums_exact():
    plan = human_scroll_plan(800, steps=12, seed=1)
    assert sum(plan) == 800
    assert len(plan) == 12

def test_type_plan_len():
    d = human_type_plan("Hi there", seed=1)
    assert len(d) == 8 and all(x > 0 for x in d)

def test_parse_task():
    steps = parse_task(os.path.join(BASE, "tasks", "search-click.txt"))
    assert len(steps) >= 4
    assert steps[0]["action"] == "open"

def run_cli(*args):
    r = subprocess.run([PY, AG, *args], capture_output=True, text=True, timeout=30, cwd=BASE)
    return r

def test_cli_scroll():
    r = run_cli("scroll", "--url", "https://example.com", "--pixels", "800", "--steps", "12", "--seed", "42")
    assert r.returncode == 0, r.stderr

def test_cli_move():
    r = run_cli("move", "--x", "600", "--y", "400", "--seed", "42")
    assert r.returncode == 0, r.stderr

def test_cli_run_task():
    out = os.path.join(BASE, "traces", "test_run.json")
    r = run_cli("run", "--task", os.path.join(BASE, "tasks", "search-click.txt"), "--output", out, "--seed", "42")
    assert r.returncode == 0, r.stdout + r.stderr
    data = json.load(open(out))
    assert data["status"] == "success"
    assert len(data["steps"]) >= 4
