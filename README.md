# Plex Sync

A command-line tool to manage and sync Plex content, with features for:
- Tracking and syncing unwatched episodes
- Analyzing watched movies and TV shows by size and space efficiency
- Integration with Radarr and Sonarr for automated media management and cleanup

## Installation

This project is managed with `uv`. To install:

```bash
# Clone the repository
git clone https://github.com/yourusername/plex-sync.git
cd plex-sync

# Install dependencies
uv sync
```

## Configuration

Create a configuration file at `~/.config/plex-sync/config.yml` or in your current directory as `config.yml`:

```yaml
plex:
  url: http://your-plex-server:32400
  token: your-plex-token

# Optional: Radarr configuration for movie management
radarr:
  enabled: true
  url: http://localhost:7878
  api_key: your_radarr_api_key

# Optional: Sonarr configuration for TV show management
sonarr:
  enabled: true
  url: http://localhost:8989
  api_key: your_sonarr_api_key
```

See `config_example.yml` for a complete example.

You can also override Plex settings with environment variables:

```bash
export PLEX_URL="http://your-plex-server:32400"
export PLEX_TOKEN="your-plex-token"
```

## Usage

### Basic Library Commands

List all libraries on your Plex server:

```bash
uv run plex-sync list libraries
```

List unwatched content from a specific library:

```bash
uv run plex-sync list library "TV Shows"
```

List unwatched episodes for a specific show:

```bash
uv run plex-sync list unwatched "Show Name"

# Specify a library if needed
uv run plex-sync list unwatched "Show Name" --library "TV Shows"
```

### Analyze Space Usage - Movies

Find watched movies that take too much space relative to their runtime:

```bash
# Show top 50 watched movies by size (default)
uv run plex-movie-size

# Show top 100 watched movies
uv run plex-movie-size --limit 100

# Show unwatched movies instead
uv run plex-movie-size --unwatched
```

**Interactive Features:**
- Use arrow keys to navigate
- Press **SPACE** to select/deselect movies
- Press **D** to delete selected movies via Radarr (if configured)
- Press **Q** to quit

**Display Columns:**
- **Rank**: Position in sorted list
- **Library**: Plex library name
- **Movie**: Title and year
- **Duration**: Runtime
- **Size (GB)**: Total file size
- **GB/min**: Space efficiency metric (lower is better)
- **Rating**: Critic rating from Plex
- **Audience**: Audience rating from Plex

### Analyze Space Usage - TV Shows

Find TV shows that take too much space:

```bash
# Show top 50 TV shows by total size (default)
uv run plex-show-size

# Show top 100 shows
uv run plex-show-size --limit 100

# Only show fully watched shows
uv run plex-show-size --watched
```

**Interactive Features:**
- Use arrow keys to navigate
- Press **SPACE** to select/deselect shows
- Press **D** to delete selected shows via Sonarr (if configured)
- Press **Q** to quit

**Display Columns:**
- **Rank**: Position in sorted list
- **Library**: Plex library name
- **Show**: Title and year
- **Episodes**: Total episode count
- **Size (GB)**: Total size across all episodes
- **GB/ep**: Space per episode (lower is better)
- **Rating**: Critic rating from Plex
- **Audience**: Audience rating from Plex

## Radarr and Sonarr Integration

When Radarr and/or Sonarr are configured in your `config.yml`, you can delete media directly from the interactive tables and have it automatically:

1. **Delete the files** from your disk
2. **Unmonitor/exclude** the movie or show so it won't be re-downloaded

### How It Works

1. **Configure Radarr/Sonarr** in your `config.yml` (see Configuration section)
2. **Run the size analyzer** commands (`plex-movie-size` or `plex-show-size`)
3. **Review the list** - sorted by size to help identify space-wasting content
4. **Check ratings** - use the Rating and Audience columns to help decide what to keep
5. **Select items** - press SPACE on movies/shows you want to delete
6. **Press D** - confirms deletion via Radarr/Sonarr API
7. **Files are removed** and items are excluded from future downloads

### Finding Radarr/Sonarr API Keys

**Radarr:**
1. Open Radarr web interface
2. Go to Settings → General
3. Click "Show Advanced"
4. Copy the API Key

**Sonarr:**
1. Open Sonarr web interface
2. Go to Settings → General
3. Click "Show Advanced"
4. Copy the API Key

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
