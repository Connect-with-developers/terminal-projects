# LinkedIn Manager Agent v2 - complete agent

Browser-automation agent that runs LinkedIn **as you**, with Telegram approval gate.
Nothing posts/sends without your approve.

## Daily loop (start here, 2 min)

```bash
cd linkedin-agent
pip install -r requirements.txt
python linkedin_agent.py init
python linkedin_agent.py sync --simulate   # sample data, no login needed
python linkedin_agent.py digest            # says what happened + what to do next
```

`digest` = views + comments-on-you + unread inbox (recruiters first) + hiring in feed + pending approvals + ordered todo.

## Complete commands

```bash
# FEED - view + agent summary (what happened, who is hiring)
python linkedin_agent.py feed --limit 8
python linkedin_agent.py feed-read --id 4

# COMMENTS - see + write for visibility (5 value-comments > 20 "nice post")
python linkedin_agent.py comments --mine          # comments ON your posts (reply in 2h = boost)
python linkedin_agent.py comments --limit 5       # where to comment (ranked)
python linkedin_agent.py comment-draft --id 1     # 3 styles: value/question/story, scored
python linkedin_agent.py comment-draft --for "post text" --author "Name"
python linkedin_agent.py comment-queue
python linkedin_agent.py comment-approve --id 1
python linkedin_agent.py comment-post --id 1 --simulate   # --real types it, YOU click Reply

# INBOX - see messages + manage
python linkedin_agent.py inbox
python linkedin_agent.py inbox-read --id 1        # full text + suggested reply (recruiter template if hiring)
python linkedin_agent.py inbox-reply --id 1 --text "Hi..."   # queued, you paste/send. --real opens browser.

# CONNECTS - network manage
python linkedin_agent.py connects
python linkedin_agent.py connect-accept --id 4    # logged + thank-you template

# POSTS - viral drafts
python linkedin_agent.py draft --topic "my lesson"
python linkedin_agent.py queue
python linkedin_agent.py approve --id 1
python linkedin_agent.py post --id 1 --simulate
python linkedin_agent.py reply-draft --comment "Great post, how...?"
python linkedin_agent.py analytics
python linkedin_agent.py audit --config config.example.json
```

## Telegram gate

```bash
export TELEGRAM_TOKEN=xxx TELEGRAM_CHAT_ID=yyy
python telegram_approval.py test
python telegram_approval.py listen
# /pending = posts + comments, /approve <id>, /capprove <id>, /digest
```

## Real LinkedIn (browser as you)

```bash
python linkedin_agent.py feed --real      # persistent login in .browser-profile/, saves traces/feed_*.png/.txt
python linkedin_agent.py inbox --real
python linkedin_agent.py sync --real
python linkedin_agent.py post --id 1 --real
python linkedin_agent.py comment-post --id 1 --real
```
You login once manually. Final Post/Send/Reply click is ALWAYS yours (safety).

## Safety

- Caps: 1 post/day, 20 comments/day, 15 replies/day, 45s+ delays. Enforced in code.
- Never auto-DM strangers / mass-connect / pods. Highest ban risk.
- Never share `.browser-profile/`.

## Strategies
- `strategies/recruiter_visibility.md`
- `strategies/viral_playbook.md`
