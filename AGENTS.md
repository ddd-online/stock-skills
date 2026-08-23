# Repository Guidelines

Self-contained Codex skills for A-share live trading. Each skill covers one stage of the trading lifecycle: analysis, planning, position management, review, and setup.

## Project Structure & Module Organization

Each skill lives in its own kebab-case directory at the repository root:

```
stock-skills/
├── <skill-name>/
│   ├── SKILL.md            # Required: frontmatter (name, description) + workflow
│   ├── agents/openai.yaml  # UI metadata: display_name, short_description, default_prompt
│   ├── references/         # Chinese reference docs, loaded on demand
│   ├── scripts/            # Python data-fetching scripts (standard library only)
│   └── assets/             # Seed templates (setup-stock-workspace only)
├── README.md
└── AGENTS.md
```

Skills must stay self-contained: `SKILL.md` is the entry point; `references/` and `scripts/` load relative to it.

## Build, Test, and Development Commands

No build step or package manager. Scripts run directly with Python 3 and network access:

```bash
python stock-analysis/scripts/fetch_quote.py sh600410 --days 60
python stock-analysis/scripts/fetch_fundamentals.py sz002491
python stock-analysis/scripts/fetch_news.py sh600410 --news 3 --ann 3
python stock-analysis/scripts/fetch_capital_flow.py sh600410
```

They pull real quote and fundamentals data from Tencent and Eastmoney public endpoints (no API keys). Verify syntax without a live run:

```bash
python -m py_compile stock-analysis/scripts/fetch_quote.py
```

## Coding Style & Naming Conventions

- Python: 4-space indentation, `snake_case` functions and variables, UTF-8 encoding, module docstring.
- Standard library only — never add third-party dependencies.
- Skill directories use kebab-case (`stock-review`); scripts use `snake_case.py` (`fetch_quote.py`); generated workspace stock folders use pure digits (`600410`).
- All files are UTF-8; scripts reconfigure stdout to UTF-8 for non-ASCII terminals.

## Testing Guidelines

No automated test suite exists yet. Smoke-test scripts against a real symbol (e.g., `sh600410`) before committing and confirm the output parses. Add tests under `tests/` as `test_<module>.py`. Do not commit cache artifacts — `.gitignore` covers `__pycache__/` and `*.pyc`.

## Data Integrity & Security

- Never fabricate market data. If an API fails, report the error explicitly.
- No secrets or API keys are used; keep it that way.
- Skill output must carry a not-investment-advice disclaimer.

## Commit & Pull Request Guidelines

Git history uses short Chinese summaries (e.g., `归档 A股交易 Codex skills 集合`). Match that style or use conventional commits (`feat:`, `fix:`, `docs:`); keep messages concise and name the changed skill.

Pull requests should:

- State which skill(s) changed and why.
- Link related issues when applicable.
- Include a sample command and output when behavior changed.
- Confirm scripts were run against live data with no fabricated figures.
