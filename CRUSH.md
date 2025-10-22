# Plex Sync Development Guidelines

## Build & Test Commands

- `uv sync` - Install dependencies
- `uv sync --dev` - Install with development dependencies
- `uv run plex-sync --help` - Test CLI locally
- `uv run pytest` - Run all tests
- `uv run pytest tests/test_file.py::test_function` - Run single test
- `python -m compileall plex_sync` - Quick syntax check

## Code Style

- Python 3.12+, 4-space indentation
- Use type hints for public functions: `def func(arg: str) -> List[str]:`
- Descriptive snake_case naming for functions and variables
- Click CLI flags use kebab-case: `--dry-run`, `--rsync-only`
- No comments unless explicitly requested
- Import order: stdlib, third-party, local modules
- Error handling: catch specific exceptions, exit with code 1 on auth failures
- Follow existing patterns in plex_sync/ for new modules

## Testing

- Tests in tests/ named `test_<feature>.py`
- Mirror CLI verbs in test function names
- Use pytest, stub network calls when testing Plex API logic
- Ensure `uv run pytest -q` passes before commits
