# Human-like Web Agent (cmds only, no interaction)

CLI agent that browses like a human: search, click, fill, press, scroll,
Bezier cursor, smooth scroll, typed delays. 100% terminal.

```bash
# atomic human-like steps (simulate mode = no install needed)
python agent.py open --url https://example.com --output traces/open.json --seed 42
python agent.py search --query "playwright python" --output traces/s.json --seed 42
python agent.py click --url https://example.com --selector "a" --seed 42
python agent.py fill --url https://example.com --selector "input" --text "hello" --seed 42
python agent.py press --url https://example.com --key Enter --seed 42
python agent.py scroll --url https://example.com --direction down --pixels 800 --steps 12 --seed 42
python agent.py move --x 600 --y 400 --steps 15 --seed 42
python agent.py snapshot --url https://example.com --output traces/snap.json
python agent.py screenshot --url https://example.com --output traces/shot.png

# multi-step task files (DSL)
python agent.py run --task tasks/search-click.txt --output traces/run.json --seed 42
python agent.py run --task tasks/form-fill.txt --output traces/run2.json --seed 42

# memory
python agent.py history --limit 10 --mode simulate
python agent.py stats
python agent.py clean --yes
```

# speed: --no-human / --fast skips delays; run --real reuses ONE browser
```bash
python agent.py run --task tasks/search-click.txt --no-human --fast --seed 42
python agent.py scroll --url https://example.com --pixels 800 --no-human --fast
```

# DSL additions (quotes supported): wait / assert / steps
```
open https://example.com
search "playwright python" https://www.duckduckgo.com
scroll down 800 steps 12
move 600 400 steps 15
wait 1000
assert body
screenshot traces/shot.png
```

Real browser (human cursor truly moves):
```bash
pip install playwright && playwright install chromium
python agent.py scroll --url https://example.com --pixels 800 --real
python agent.py run --task tasks/search-click.txt --real --output traces/real.json
```

Human-like details:
- cursor: cubic Bezier + jitter, 8-25ms per point
- scroll: ease-out plan summing exactly to pixels, 40-120ms per step
- type: 45ms + 0-60ms jitter, +80-180ms on space, +20-60ms on caps
- think: 350-1200ms between actions, random viewport + UA
- stealth: hides webdriver flag, paired viewports, en-US locale

CAPTCHA (no auto-bypass guaranteed — designed to block bots):
- detect (default): flags `g-recaptcha/h-captcha/turnstile/data-sitekey`
- `... --real --captcha wait --captcha-wait-ms 60000 --no-headless`: pauses for YOU to solve
- `... --captcha 2captcha` with `TWOCAPTCHA_KEY` set: hook point for solver API
