# pr-reviewer-agent — CodeRabbit-like PR Reviewer (Free, via opencode + GitHub Actions)

Auto-reviews every PR and posts issues like CodeRabbit. Runs **opencode in GitHub Actions terminal** with a **free Zen model** — $0 API cost.

- Auto review on `pull_request: [opened, synchronize, reopened, ready_for_review]`
- Manual trigger: comment `/oc` or `/opencode` on any PR / issue / line
- Free model default: `opencode/big-pickle` (also free: `space-bunny-free`, `muse-spark-1.3-contributor-free`, `exo-free`)
- No GitHub App install needed (uses `GITHUB_TOKEN`)

## 1. Setup (2 min)

1. Get a free key at https://opencode.ai/auth (Zen, no credit card for free models).
2. In GitHub repo → Settings → Secrets and variables → Actions → New secret:
   - Name: `OPENCODE_API_KEY`, Value: your key
3. Push this folder + `.github/workflows/opencode-*.yml` to `main`.
4. Open a test PR → bot comments within ~1-2 min.

## 2. Terminal usage (free, local)

```bash
# install
curl -fsSL https://opencode.ai/install | bash

# set free key
export OPENCODE_API_KEY=xxx

# review current branch vs main (in any repo checkout)
opencode run --model opencode/big-pickle "Follow pr-reviewer-agent/REVIEW_PROMPT.md and review $(git diff main...HEAD --stat). Full diff: $(git diff main...HEAD | head -n 400)"

# or interactive
opencode
# > /agent reviewer
# > review the diff of this PR branch
```

## 3. Manual trigger in GitHub

On any PR comment or inline line comment:

```
/oc review this PR for bugs and security issues
```

```
/opencode explain this diff
```

```
/oc fix the critical issue you found and commit to this branch
```

## 4. Files

- `REVIEW_PROMPT.md` — the CodeRabbit-style prompt (edit review rules here)
- `opencode.json` — `reviewer` subagent definition
- `AGENTS.md` — repo conventions the reviewer respects
- `../.github/workflows/opencode-review.yml` — auto review on PR
- `../.github/workflows/opencode-comment.yml` — `/oc` comment trigger

## 5. Change model / cost

Free (default): `opencode/big-pickle`
Other free: `opencode/space-bunny-free`, `opencode/exo-free`, `opencode/muse-spark-1.3-contributor-free`
Paid (better): `opencode/gpt-5.4-mini`, `anthropic/claude-sonnet-4-5`

Edit `model:` in both workflow files.

## 6. How it works

`pull_request` event → `actions/checkout` → `anomalyco/opencode/github@latest` with `use_github_token: true` → opencode reads diff + repo context → posts summary + Critical/Warnings/Nitpicks comment.
