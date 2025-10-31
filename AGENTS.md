# Repository Guidelines

## Project Structure & Module Organization
- Core CLI logic lives in `plex_sync/`; `main.py` exposes the Click entry point (`plex-sync`) and `config.py` loads YAML settings.
- Tests reside in `tests/` and should mirror CLI verbs (e.g., `test_list_libraries.py`).
- Example configs sit at the repo root (`config_example.yml`, `config.yml`); external runs read from `~/.config/plex-sync/config.yml`.
- Temporary sync artifacts such as `last_sync.json` support diagnostics only—do not drive logic from them.

## Build, Test, and Development Commands
- `uv sync` installs and updates project dependencies.
- `uv run plex-sync --help` shows available CLI verbs; `uv run plex-sync list libraries` is a quick smoke test.
- `uv run pytest -q` executes the suite; add `-k <pattern>` for targeted runs.
- `python -m compileall plex_sync` performs a fast syntax check before larger refactors.

## Coding Style & Naming Conventions
- Target Python 3.12 with 4-space indentation and descriptive snake_case names.
- Align Click flag names with existing kebab-case patterns (e.g., `--dry-run`).
- Type-hint new public functions; add docstrings when behaviour is non-obvious.
- Keep modules small; place new helpers under `plex_sync/` and share fixtures via `tests/conftest.py`.

## Testing Guidelines
- Use pytest for all tests; name files `test_<feature>.py` and functions after the CLI verb being exercised.
- Cover both success and failure paths, stubbing Plex API calls behind helper abstractions.
- Ensure `uv run pytest -q` passes before sending a PR; document intentionally skipped checks in the PR description.

## Commit & Pull Request Guidelines
- Follow the existing history style: concise, imperative summaries such as `Add sync limiting per episode`; wrap commit body text at ~72 characters.
- Pull requests should describe motivation, list user-facing changes, reference issues (`Fixes #123`), and capture validation steps or CLI output when behaviour changes.

## Security & Configuration Tips
- Never commit real tokens or server URLs; rely on `uv run plex-sync config` to scaffold safe local configs.
- Confirm the active configuration with `uv run plex-sync config --show`, and redact secrets in shared logs or issue reports.
