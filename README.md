# Plex Sync

A command-line tool to manage and sync Plex content, with a focus on tracking unwatched episodes.

## Installation

This project is managed with Poetry. To install:

```bash
# Clone the repository
git clone https://github.com/yourusername/plex-sync.git
cd plex-sync

# Install with Poetry
poetry install

# Or install in development mode
poetry install -e .
```

## Configuration

Before using Plex Sync, you need to configure it with your Plex server details:

```bash
# Create a default configuration file
poetry run plex-sync config

# Edit the configuration file (located at ~/.config/plex-sync/config.yml)
```

The configuration file uses YAML format:

```yaml
plex:
  url: http://your-plex-server:32400
  token: your-plex-token
```

You can also check the location of your current configuration file:

```bash
poetry run plex-sync config --show
```

Alternatively, you can set environment variables:

```bash
export PLEX_URL="http://your-plex-server:32400"
export PLEX_TOKEN="your-plex-token"
```

## Usage

### List all libraries on your Plex server

```bash
poetry run plex-sync list libraries
```

### List unwatched content from a specific library

```bash
poetry run plex-sync list library "TV Shows"
```

### List unwatched episodes for a specific show

```bash
poetry run plex-sync list unwatched "Show Name"

# Specify a library if needed
poetry run plex-sync list unwatched "Show Name" --library "TV Shows"
```

## Getting Your Plex Token

To find your Plex token:

1. Log in to Plex Web App
2. Play any video
3. While the video is playing, press F12 to open developer tools
4. Go to the Network tab
5. Look for a request to a URL containing "?X-Plex-Token="
6. The value after "X-Plex-Token=" is your Plex token

Alternatively, you can use the [Plex Token Bookmarklet](https://github.com/jacobwgillespie/plex-token-bookmarklet).

## License

MIT
