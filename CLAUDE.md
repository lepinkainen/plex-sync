# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Plex Sync is a command-line tool for managing Plex media content, focusing on tracking and syncing unwatched TV show episodes to a target location. It's built with Python 3.12+ using the Click CLI framework and PlexAPI library.

## Development Commands

### Installation and Setup

```bash
# Install dependencies
poetry install

# Run the CLI
poetry run plex-sync

# Debug configuration
poetry run plex-sync debug
```

### Running Tests

```bash
# Run tests (if tests are implemented)
poetry run pytest
```

## Configuration System

The application uses a hierarchical configuration system (plex_sync/config.py:19-38):

1. **Local config** (highest priority): `./config.yml` in current directory
2. **User config**: `~/.config/plex-sync/config.yml`
3. **XDG config**: `$XDG_CONFIG_HOME/plex-sync/config.yml`
4. **Environment variables**: `PLEX_URL` and `PLEX_TOKEN` override file values

Configuration includes:
- Plex server URL and authentication token
- Sync definitions per library with episode limits
- Rsync settings for file transfer (server_path, target, options)

Example configuration structure in `config_example.yml`:
- `sync.defaults.episode_limit`: Default number of episodes to sync
- Per-library show lists with optional episode_limit overrides
- Shows can be defined as strings or dictionaries with name/episode_limit

## Core Architecture

### CLI Structure (plex_sync/main.py)

The CLI uses Click's command groups:
- `list libraries`: List all Plex libraries
- `list library <name>`: List unwatched content from a library
- `list unwatched <show>`: List unwatched episodes for a specific show
- `sync`: Main sync command with `--dry-run` and `--rsync-only` flags
- `rsync`: Standalone rsync of previously cached files
- `debug`: Print configuration information

### Sync Workflow (plex_sync/main.py:131-235)

1. Load configuration and connect to Plex server
2. For each library in sync config:
   - Process each configured show
   - Retrieve unwatched episodes (sorted by air date, oldest first)
   - Limit episodes per show based on config (default 10)
   - Collect file paths from episode metadata
3. Save file paths to cache (`last_sync.json`)
4. Execute rsync for each file using configured settings

The `--rsync-only` flag skips Plex queries and uses cached file paths from previous runs.

### Episode Limiting (plex_sync/main.py:301-389)

Episodes are filtered and limited in `get_unwatched_episodes()`:
- Unwatched episodes are sorted by `originallyAvailableAt` (air date) or `addedAt`
- The episode_limit is applied after sorting (oldest unwatched episodes first)
- Final display shows episodes sorted by season/episode number for readability

### File Caching (plex_sync/main.py:556-595)

File paths are cached in `last_sync.json` (or `~/.cache/plex-sync/last_sync.json`):
- Enables `--rsync-only` mode to repeat syncs without querying Plex
- Cache location determined by config directory or default cache path

## Key Implementation Details

### Show Matching
Show names are matched case-insensitively (plex_sync/main.py:334).

### Rsync Integration
The tool constructs rsync commands by:
1. Stripping `server_path` prefix from Plex file paths
2. Building destination path by appending relative path to `target`
3. Executing rsync with configured options (default: `-avP`)

### Error Handling
- Unauthorized Plex access returns exit code 1
- Missing shows/libraries log warnings but continue processing
- Individual show errors don't stop batch processing

## Dependencies

- `plexapi ^4.15.15`: Plex server API client
- `click ^8.1.7`: CLI framework
- `pyyaml ^6.0.2`: Configuration file parsing
