# Plex Sync Development Guidelines

## Build & Test Commands
- `poetry install` - Install dependencies  
- `poetry install -e .` - Install in editable mode for CLI development
- `poetry run plex-sync --help` - Test CLI locally
- `poetry run pytest` - Run all tests
- `poetry run pytest tests/test_file.py::test_function` - Run single test
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
- Ensure `poetry run pytest -q` passes before commits