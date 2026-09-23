# Self-Healing Code Builder v3 - all 8 best features implemented

CLI agent that builds, tests and improves itself. 100% terminal, only `--commands`.

Research: Aider, Claude Code, Codex CLI, Copilot CLI, Omp, Sentinel, UTIM, OpenHands (2026).

## All commands (15 total, no interaction)
```bash
# core loop
python builder.py build --task tasks/calculator.txt --output generated/calculator.py --max-fix 5
python builder.py test --file generated/calculator.py --tests tests
python builder.py improve --file generated/calculator.py --rounds 3
# 1. watch (Aider --watch-files)
python builder.py build --task tasks/x.txt --output generated/x.py --watch --watch-interval 1 --watch-secs 60
# 2. diff preview (Claude Code / Codex approval gate)
python builder.py build --task tasks/x.txt --output generated/x.py --diff
# 3. cost tracker
python builder.py stats --cost
# 4. TDD RED-GREEN-REFACTOR (Sentinel /tdd)
python builder.py tdd --task tasks/calculator.txt --output generated/calculator.py
# 5. multi-file project (Devin-style)
python builder.py project --task tasks/todo.txt --output-dir generated/shop
# 6. Ollama local LLM ($0, private) - auto fallback: OpenAI -> Ollama -> offline
OLLAMA_MODEL=llama3 python builder.py build --task tasks/x.txt --output generated/x.py
# 7. sandbox (Codex/OpenHands) - isolated run, scrubbed secrets, timeout, docker if BUILDER_SANDBOX_DOCKER=1
python builder.py test --file generated/x.py --tests tests --sandbox
python builder.py build --task tasks/x.txt --output generated/x.py --sandbox
# 8. memory search (Copilot/Claude memory, vectorless BM25-lite)
python builder.py memory --search "divide fix" --limit 3
# safety + quality (v2)
python builder.py lint --file generated/x.py
python builder.py review --file generated/x.py
python builder.py map
python builder.py undo --file generated/x.py --steps 1
python builder.py autopilot --max-fix 5
python builder.py diagnose --file generated/x.py
python builder.py history --limit 10
python builder.py stats
python builder.py clean
```

## Verified v3
- 17/17 pytest pass (15 old + 2 new TDD)
- builder.py 1222 lines, 15 commands
- watch: rebuilds on change, --watch-secs for tests
- diff: unified preview before write
- cost: ~555 tokens $0.0003, 4h saved
- tdd: RED tests-first -> GREEN build -> REFACTOR format
- project: app.py + store.py + api.py all syntax OK
- ollama: silent fallback when no server (correct)
- sandbox: isolated run 1/1 pass, timeout kills loops
- memory: ranks past builds by word overlap
