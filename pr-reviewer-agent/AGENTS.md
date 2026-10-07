# AGENTS.md — pr-reviewer-agent conventions

- Reviewer is read-only in CI: comment findings, never push unless user says `/oc fix`.
- Always cite `file:line`. Quote code. Show fix.
- Python: ruff-style, type hints, no bare `except:`, no `os.system`, use `subprocess`.
- Ignore: `__pycache__/`, `output/`, `*.png`, `*.mp4`, `automation_history.json`.
- Keep reviews under ~600 words. Severity order: Critical > Warnings > Nitpicks.
- Verdict must be one of: APPROVE / REQUEST CHANGES / COMMENT.
