# GitHub Actions Alternatives — Free / Free-Tier for Scheduled Python Scripts

For `social-media-automation/main.py` scheduled 3x daily (`0 9,15,21 * * *`).

Current setup: `.github/workflows/social-automation.yml` — checkout → setup-python 3.10 → `pip install -r requirements.txt` → `python main.py [--dry-run]` → upload artifacts → commit `output/`.

Usage estimate: ~5 min/run × 3/day × 30 days = ~450 min/month.

GitHub Actions free baseline (2026):
- Private repos: 2,000 Linux min/mo + 500 MB storage
- Public repos: unlimited minutes
- Limits: cron can delay 10-30 min, ephemeral storage, 6h max per job

---

## 1. CI/CD Replacements (Same YAML Concept)

| Platform | Free Tier (2026) | Verdict |
|----------|------------------|---------|
| CircleCI | 6,000 build-min/mo (30,000 credits), private + public | Best free CI. Direct replacement. |
| GitLab CI/CD | 400 min/mo, 5 GB storage | Too small for 3x/day. |
| Bitbucket Pipelines | 50 min/mo (up to 5 users) | Too small. |
| Azure Pipelines | 1 free parallel job, ~1,800 min/mo private, unlimited public | OK alternative. |
| Semaphore | ~$15/mo free usage, no seat cost | OK for small repo. |
| Travis CI | No real free tier now | Skip. |
| Jenkins / Drone CI / Woodpecker CI / Gitea Actions | Unlimited, self-hosted, open-source | Truly free if you host. |

### CircleCI example (`.circleci/config.yml`)

```yaml
version: 2.1
jobs:
  automate-content:
    docker:
      - image: cimg/python:3.10
    steps:
      - checkout
      - run:
          name: Install dependencies
          command: |
            cd social-media-automation
            pip install -r requirements.txt
      - run:
          name: Run automation
          command: |
            cd social-media-automation
            python main.py --dry-run
workflows:
  daily-automation:
    triggers:
      - schedule:
          cron: "0 9,15,21 * * *"
          filters:
            branches:
              only:
                - main
    jobs:
      - automate-content
```

Set secrets in CircleCI Project Settings > Environment Variables: `TWITTER_API_KEY`, `YOUTUBE_API_KEY`, `OPENAI_API_KEY`, etc.

### GitLab CI example (`.gitlab-ci.yml`)

```yaml
automate-content:
  image: python:3.10
  script:
    - cd social-media-automation
    - pip install -r requirements.txt
    - python main.py --dry-run
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
```

Then add Pipeline Schedule in GitLab UI with cron `0 9,15,21 * * *`.

---

## 2. Scheduled Python Hosting (No CI Needed)

### A. VPS Cron — cheapest long-term, persistent storage

Works on any Linux VM, Raspberry Pi, WSL.

```bash
crontab -e
# 9 AM, 3 PM, 9 PM UTC
0 9,15,21 * * * cd ~/terminal-projects/social-media-automation && /usr/bin/python3 main.py >> logs/run.log 2>&1
```

systemd alternative (`/etc/systemd/system/social-automation.timer`):

```ini
[Unit]
Description=Run social automation 3x daily

[Timer]
OnCalendar=09,15,21:00
Persistent=true

[Install]
WantedBy=timers.target
```

Pros: no minute limits, `output/` and `automation_history.json` persist, no commit-back hack.
Cons: you manage server, secrets, logs.

Free option: **Oracle Cloud Always Free** — 2 AMD VMs forever, run cron unlimited free.

### B. Serverless — pay-per-run, generous free tier

**AWS Lambda + EventBridge (recommended free):**
- Free: 1M requests + 400k GB-sec/mo forever
- EventBridge cron: `cron(0 9,15,21 * * ? *)`
- Store secrets in Secrets Manager / Lambda Env Vars
- Fits 3x/day easily, $0

**Google Cloud Run + Cloud Scheduler:**
- Free: 2M invocations/mo
- Dockerize `main.py`, set schedule `0 9,15,21 * * *`

**Azure Functions Timer Trigger:**
- Free: 1M executions/mo
- `function.json`: `"schedule": "0 0 9,15,21 * * *"`

**Modal (best Python-native):**
- Free: $30/mo Starter credits
- `modal schedule` for Python functions, cron jobs, PIL/carousel works natively

```python
import modal
app = modal.App("social-automation")
image = modal.Image.debian_slim().pip_install_from_requirements("requirements.txt")

@app.function(image=image, schedule=modal.Cron("0 9,15,21 * * *"), secrets=[modal.Secret.from_name("social-keys")])
def run():
    import subprocess
    subprocess.run(["python", "main.py"], cwd="/root/social-media-automation")
```

**Cloudflare Workers Cron:**
- Free: 100k req/day with cron triggers
- Note: Python beta, PIL/carousel generation may hit limits. PreferWorkers for lightweight pingers.

### C. PaaS Cron

| Platform | Free Tier | Note |
|----------|-----------|------|
| PythonAnywhere Beginner | Free: 1 web app, 512 MB, 100 CPU-sec/day, 2 consoles | No scheduled tasks on free. Need Developer $10/mo for cron. |
| Render Cron Jobs | Billed per second, $1 min/job/mo | No real free for cron. Free 750h only for web services (spin down after 15 min). |
| Railway | $5 Hobby includes $5 usage | Trial-like, then paid. Cron min 5 min interval. |
| Fly.io | shared-cpu-1x 256 MB ~$1.94/mo Ashburn | Cheap, not free. Use Scheduled Machines / supercronic. |
| Heroku Scheduler | Eco $5/mo, sleep after 30 min | Not free. |

### D. Automation Platforms

| Platform | Free Tier | Note |
|----------|-----------|------|
| Pipedream | 100 invocations/day free | Run Python + cron + native Twitter/YouTube nodes. Good fit. |
| n8n (self-host) | Unlimited self-hosted | Trigger Python code on schedule, native social nodes. Host on Oracle Free VM = $0. |
| Make / Zapier / IFTTT | Very limited free (100-1k ops/mo) | OK for notifications, not for heavy carousel gen. |

---

## 3. Keep GitHub Actions But Make It Reliable (Free)

GHA cron delays 10-30 min. Use external free pinger to trigger `workflow_dispatch`:

**cron-job.org (free unlimited) → GitHub API:**

```
POST https://api.github.com/repos/<owner>/<repo>/actions/workflows/social-automation.yml/dispatches
Authorization: Bearer <PAT with actions:write>
{"ref":"main","inputs":{"dry_run":"true"}}
```

Same with UptimeRobot / EasyCron (free tier).

You still use 450/2000 free minutes, but runs start on time.

---

## Recommendation for This Repo

1. **Stay on GitHub Actions** — 450 min < 2000 min free, commit-back + artifacts already work.
2. **If you exceed limit or need persistence** — move to:
   - `CircleCI` (6k min free, 10-min port), or
   - `AWS Lambda + EventBridge` ($0 forever), or
   - `Oracle Free VM + cron` ($0 forever, keeps `output/`).
3. **If you add retries / Slack alerts / multi-account queue** — move to `Prefect / Airflow / Dagster` or self-hosted `n8n`.

### Secrets Checklist (any platform)

```
TWITTER_API_KEY
TWITTER_API_SECRET
TWITTER_BEARER_TOKEN
YOUTUBE_API_KEY
OPENAI_API_KEY
FACEBOOK_ACCESS_TOKEN
FACEBOOK_PAGE_ID
INSTAGRAM_ACCESS_TOKEN
INSTAGRAM_ACCOUNT_ID
LINKEDIN_ACCESS_TOKEN
LINKEDIN_ORG_ID
```

Never commit `config/config.json`, `.env`, `output/`, `automation_history.json` — see `.gitignore`.

---

## References

- Current workflow: `.github/workflows/social-automation.yml`
- Entry point: `main.py --dry-run`
- Requirements: `requirements.txt`
