# Repository Guidelines

## Project Structure & Module Organization
Core source lives in `plex_sync/`. `main.py` defines the Click-based CLI entry point exposed as `plex-sync`, while `config.py` handles loading YAML settings. Root-level `config_example.yml` and `config.yml` provide local defaults; external runs read from `~/.config/plex-sync/config.yml`. Keep new modules in `plex_sync/` and pair behavioural changes with fixtures or helpers under `tests/`. Temporary sync metadata is stored in `last_sync.json`—do not rely on it for logic.

## Build, Test, and Development Commands
Install dependencies with Poetry: `poetry install`. Use editable installs when iterating on the CLI: `poetry install -e .`. Run the tool locally via `poetry run plex-sync --help` or targeted commands such as `poetry run plex-sync list libraries`. Execute the current test suite with `poetry run pytest`; add `pytest` to the dev group if it is missing after a fresh clone (`poetry add --group dev pytest`).

## Coding Style & Naming Conventions
This codebase targets Python 3.12 and follows standard 4-space indentation. Keep functions small, prefer descriptive snake_case names, and align Click option names with existing kebab-case CLI flags. Use type hints for new public functions and meaningful docstrings when behaviour is non-obvious. Run `python -m compileall plex_sync` before larger refactors if you need a quick syntax check.

## Testing Guidelines
Tests reside in `tests/` and are expected to use pytest. Name new files `test_<feature>.py`, mirror CLI verbs in test function names, and cover both success and failure paths. When adding network-dependent logic, isolate Plex API calls behind helpers so you can stub them. Ensure `poetry run pytest -q` passes before raising a PR and document any intentionally skipped checks.

## Commit & Pull Request Guidelines
Existing history uses concise, imperative commit summaries (for example, `Add sync + limiting per episode`). Follow the same format, keep body paragraphs wrapped at ~72 characters, and reference GitHub issues when relevant (`Fixes #123`). Pull requests should describe the motivation, summarize user-facing changes, list validation steps, and include screenshots or sample CLI output when UI-visible behaviour changes.

## Configuration Tips
Never commit real tokens or server URLs. Use `poetry run plex-sync config` to generate a local template and `poetry run plex-sync config --show` to confirm the active path. When sharing repro steps, redact secrets and point contributors to the sample `config_example.yml`.
