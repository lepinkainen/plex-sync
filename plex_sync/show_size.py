import click
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized
from . import config
from .sonarr import SonarrClient
import sys
from datetime import datetime
from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer, Header
from textual.containers import Container
from textual.binding import Binding


class ShowSizeApp(App):
    """Textual app for displaying TV show size table."""

    CSS = """
    Screen {
        background: $surface;
    }

    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_select", "Select/Deselect", show=True),
        Binding("d", "delete_selected", "Delete Selected", show=True),
        Binding("r", "generate_reencode", "Generate Re-encode Script", show=True),
        Binding("s", "toggle_view", "Toggle Season/Show View", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, shows_data, sonarr_client=None):
        super().__init__()
        self.shows_data = shows_data
        self.sonarr_client = sonarr_client
        self.selected_rows = set()
        self.row_to_show = {}  # Maps row index to show object
        self.view_mode = "show"  # "show" or "season"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            DataTable(id="show_table")
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#show_table", DataTable)
        table.cursor_type = "row"

        # Populate the table (this adds columns and data)
        self.populate_table()

    def populate_table(self):
        """Populate the table with shows/seasons data."""
        table = self.query_one("#show_table", DataTable)
        table.clear(columns=True)  # Clear both rows and columns
        self.row_to_show.clear()
        self.selected_rows.clear()

        # Add columns based on view mode
        if self.view_mode == "show":
            table.add_columns("✓", "Rank", "Library", "Show", "Episodes", "Size (GB)", "GB/ep", "Rating", "Audience")
        else:  # season view
            table.add_columns("✓", "Rank", "Library", "Show - Season", "Episodes", "Size (GB)", "GB/ep")

        # Build display list based on view mode
        display_items = []

        for show, size_bytes, episode_count, season_data in self.shows_data:
            if self.view_mode == "show":
                display_items.append((show, size_bytes, episode_count, None, season_data))
            else:  # season mode
                for season_num, (season_size, season_ep_count) in season_data.items():
                    display_items.append((show, season_size, season_ep_count, season_num, season_data))

        # Sort by size
        display_items.sort(key=lambda x: x[1], reverse=True)

        # Add rows to table
        row_key = 0
        for i, (show, size_bytes, episode_count, season_num, season_data) in enumerate(display_items, 1):
            size_gb = size_bytes / (1024**3)
            library_name = (
                show.section().title
                if hasattr(show, "section") and show.section()
                else "Unknown"
            )

            # Calculate GB per episode
            gb_per_episode_display = ""
            if episode_count > 0:
                gb_per_episode = size_gb / episode_count
                gb_per_episode_display = f"{gb_per_episode:.3f}"

            if self.view_mode == "show":
                show_title = f"{show.title} ({show.year})" if hasattr(show, 'year') and show.year else show.title

                # Get ratings
                critic_rating = ""
                if hasattr(show, 'rating') and show.rating:
                    critic_rating = f"{show.rating:.1f}"

                audience_rating = ""
                if hasattr(show, 'audienceRating') and show.audienceRating:
                    audience_rating = f"{show.audienceRating:.1f}"

                # Add row with zero-padded numeric values for proper sorting
                table.add_row(
                    " ",  # Checkbox column
                    f"{i:03d}",
                    library_name,
                    show_title,
                    f"{episode_count:04d}",
                    f"{size_gb:.2f}",
                    gb_per_episode_display or "0.000",
                    critic_rating or "N/A",
                    audience_rating or "N/A"
                )
            else:  # season view
                # Handle None season numbers (specials/extras)
                if season_num is None:
                    show_title = f"{show.title} - Specials"
                else:
                    show_title = f"{show.title} - S{season_num:02d}"
                table.add_row(
                    " ",  # Checkbox column
                    f"{i:03d}",
                    library_name,
                    show_title,
                    f"{episode_count:04d}",
                    f"{size_gb:.2f}",
                    gb_per_episode_display or "0.000"
                )

            # Store show reference for this row
            self.row_to_show[row_key] = (show, season_num)
            row_key += 1

    def action_toggle_select(self) -> None:
        """Toggle selection of the current row."""
        table = self.query_one("#show_table", DataTable)
        if table.cursor_row is not None:
            row_index = table.cursor_row
            # Get the actual row key from the ordered rows
            row_keys = list(table.rows.keys())
            # Get column key for the checkbox column (first column)
            column_keys = list(table.columns.keys())

            if row_index < len(row_keys) and len(column_keys) > 0:
                row_key = row_keys[row_index]
                checkbox_column_key = column_keys[0]

                if row_key in self.selected_rows:
                    self.selected_rows.remove(row_key)
                    # Update the checkbox column (first column)
                    table.update_cell(row_key, checkbox_column_key, " ")
                else:
                    self.selected_rows.add(row_key)
                    # Update the checkbox column (first column)
                    table.update_cell(row_key, checkbox_column_key, "✓")

    def action_delete_selected(self) -> None:
        """Delete selected TV shows via Sonarr API."""
        if not self.selected_rows:
            self.notify("No shows selected", severity="warning")
            return

        if not self.sonarr_client:
            self.notify("Sonarr client not configured", severity="error")
            return

        # Get show objects for selected rows (only shows, not individual seasons)
        selected_shows = []
        for row_key in self.selected_rows:
            if row_key in self.row_to_show:
                show, season_num = self.row_to_show[row_key]
                # Only delete entire shows, not individual seasons
                if show not in selected_shows:
                    selected_shows.append(show)

        if not selected_shows:
            self.notify("No shows selected", severity="warning")
            return

        self.notify(f"Deleting {len(selected_shows)} shows via Sonarr...", severity="information")

        for show in selected_shows:
            try:
                success = self.sonarr_client.delete_series(show)
                if success:
                    self.notify(f"Deleted: {show.title}", severity="success")
                else:
                    self.notify(f"Failed to delete: {show.title}", severity="error")
            except Exception as e:
                self.notify(f"Error deleting {show.title}: {str(e)}", severity="error")

        # Clear selections after deletion
        self.selected_rows.clear()
        self.notify("Deletion complete", severity="success")

    def action_generate_reencode(self) -> None:
        """Generate ffmpeg re-encode script for selected shows/seasons."""
        if not self.selected_rows:
            self.notify("No items selected", severity="warning")
            return

        # Collect file paths based on view mode
        file_paths = []

        for row_key in self.selected_rows:
            if row_key not in self.row_to_show:
                continue

            show, season_num = self.row_to_show[row_key]

            try:
                if self.view_mode == "show" or season_num is None:
                    # Get all episodes from the show
                    episodes = show.episodes()
                else:
                    # Get episodes from specific season
                    season = show.season(season_num)
                    episodes = season.episodes()

                # Extract file paths from episodes
                for episode in episodes:
                    if episode.media:
                        for media in episode.media:
                            for part in media.parts:
                                if hasattr(part, "file") and part.file:
                                    file_paths.append(part.file)

            except Exception as e:
                self.notify(f"Error collecting files for {show.title}: {str(e)}", severity="error")
                continue

        if not file_paths:
            self.notify("No file paths found for selected items", severity="warning")
            return

        # Generate script
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        script_path = f"reencode_shows_{timestamp}.sh"

        try:
            script_content = self._generate_ffmpeg_script(file_paths)
            with open(script_path, 'w') as f:
                f.write(script_content)

            # Make script executable
            Path(script_path).chmod(0o755)

            self.notify(f"Generated script: {script_path} ({len(file_paths)} files)", severity="success")
        except Exception as e:
            self.notify(f"Error generating script: {str(e)}", severity="error")

    def _generate_ffmpeg_script(self, file_paths):
        """Generate bash script content with ffmpeg re-encoding commands."""
        script = """#!/bin/bash
# FFmpeg re-encoding script for Plex media
# Generated: {timestamp}
#
# This script uses AMD VAAPI hardware acceleration to re-encode videos
# to H.265/HEVC with quality preset qp=28 for significant size reduction
# while maintaining good quality.
#
# Audio streams are copied without re-encoding to preserve quality.
# Originals are replaced only after successful encoding and verification.

set -e  # Exit on error

TOTAL_FILES={total_files}
CURRENT=0

# Color codes for output
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
RED='\\033[0;31m'
NC='\\033[0m' # No Color

echo "Starting re-encode of $TOTAL_FILES files..."
echo ""

""".format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_files=len(file_paths)
        )

        for i, file_path in enumerate(file_paths, 1):
            # Escape single quotes in file paths
            safe_path = file_path.replace("'", "'\\''")

            script += f"""
# File {i}/{len(file_paths)}
CURRENT=$((CURRENT + 1))
echo "${{YELLOW}}[$CURRENT/$TOTAL_FILES]${{NC}} Processing: '{safe_path}'"

INPUT_FILE='{safe_path}'
TEMP_FILE="${{INPUT_FILE}}.tmp.mkv"

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "${{RED}}ERROR:${{NC}} Input file not found, skipping"
    continue
fi

# Re-encode with VAAPI hardware acceleration
if ffmpeg -y \\
    -vaapi_device /dev/dri/renderD128 \\
    -i "$INPUT_FILE" \\
    -vf 'format=nv12,hwupload' \\
    -c:v hevc_vaapi \\
    -qp 28 \\
    -c:a copy \\
    -c:s copy \\
    "$TEMP_FILE"; then

    # Verify the output file is valid
    if ffprobe -v error "$TEMP_FILE" >/dev/null 2>&1; then
        # Get file sizes for comparison
        ORIGINAL_SIZE=$(stat -c%s "$INPUT_FILE")
        NEW_SIZE=$(stat -c%s "$TEMP_FILE")
        REDUCTION=$(echo "scale=1; (1 - $NEW_SIZE / $ORIGINAL_SIZE) * 100" | bc)

        echo "${{GREEN}}SUCCESS:${{NC}} Size reduction: ${{REDUCTION}}%"

        # Replace original with re-encoded file
        mv "$TEMP_FILE" "$INPUT_FILE"
    else
        echo "${{RED}}ERROR:${{NC}} Verification failed, keeping original"
        rm -f "$TEMP_FILE"
    fi
else
    echo "${{RED}}ERROR:${{NC}} Encoding failed, keeping original"
    rm -f "$TEMP_FILE"
fi

echo ""
"""

        script += """
echo "${GREEN}Re-encoding complete!${NC}"
"""

        return script

    def action_toggle_view(self) -> None:
        """Toggle between show view and season view."""
        self.view_mode = "season" if self.view_mode == "show" else "show"
        self.populate_table()
        self.notify(f"Switched to {self.view_mode} view")


@click.command()
@click.option(
    "--limit",
    "-n",
    default=100,
    type=int,
    help="Number of shows to show (default: 100)"
)
@click.option(
    "--watched",
    is_flag=True,
    help="Only include fully watched shows"
)
def cli(limit, watched):
    """List largest TV shows by size."""
    try:
        server = get_plex_server()

        # Load config to check for Sonarr settings
        cfg = config.load_config()
        sonarr_client = None

        # Initialize Sonarr client if enabled
        if cfg.get("sonarr", {}).get("enabled", False):
            sonarr_url = cfg["sonarr"].get("url")
            sonarr_api_key = cfg["sonarr"].get("api_key")

            if sonarr_url and sonarr_api_key:
                try:
                    sonarr_client = SonarrClient(sonarr_url, sonarr_api_key)
                    if sonarr_client.test_connection():
                        click.echo("Sonarr integration enabled")
                    else:
                        click.echo("Warning: Failed to connect to Sonarr", err=True)
                        sonarr_client = None
                except Exception as e:
                    click.echo(f"Warning: Error initializing Sonarr client: {str(e)}", err=True)
            else:
                click.echo("Warning: Sonarr is enabled but URL or API key is missing", err=True)

        # Find TV show libraries
        show_sections = [
            section for section in server.library.sections() if section.type == "show"
        ]

        if not show_sections:
            click.echo("No TV show libraries found.")
            return

        # Collect shows with their sizes
        shows_list = []

        for section in show_sections:
            click.echo(f"Scanning library: {section.title}")
            for show in section.all():
                episodes = show.episodes()

                # Filter based on watched flag
                if watched:
                    # Only include shows where ALL episodes are watched
                    if not all(ep.isWatched for ep in episodes):
                        continue

                if episodes:
                    # Get total size and per-season breakdown
                    total_size = 0
                    total_episode_count = 0
                    season_data = {}

                    try:
                        for season in show.seasons():
                            season_size = 0
                            season_ep_count = 0
                            for episode in season.episodes():
                                if episode.media:
                                    episode_size = sum(
                                        part.size
                                        for media in episode.media
                                        for part in media.parts
                                        if hasattr(part, "size")
                                    )
                                    season_size += episode_size
                                    season_ep_count += 1

                            if season_size > 0:
                                season_data[season.seasonNumber] = (season_size, season_ep_count)
                                total_size += season_size
                                total_episode_count += season_ep_count
                    except AttributeError:
                        # Fallback for shows without proper season structure
                        for episode in episodes:
                            if episode.media:
                                total_size += sum(
                                    part.size
                                    for media in episode.media
                                    for part in media.parts
                                    if hasattr(part, "size")
                                )
                        total_episode_count = len(episodes)

                    if total_size > 0:
                        shows_list.append((show, total_size, total_episode_count, season_data))

        # Sort by size (largest first) and take top N
        shows_list.sort(key=lambda x: x[1], reverse=True)
        top_shows = shows_list[:limit]

        if not top_shows:
            click.echo("No TV shows with size information found.")
            return

        # Run Textual app with Sonarr client if available
        app = ShowSizeApp(top_shows, sonarr_client=sonarr_client)
        app.run()

    except Unauthorized:
        click.echo(
            "Error: Unauthorized access to Plex server. Check your token and URL."
        )
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {str(e)}")
        sys.exit(1)


def get_plex_server():
    """Get a connection to the Plex server."""
    cfg = config.load_config()
    url = cfg["plex"]["url"]
    token = cfg["plex"]["token"]

    if not token:
        raise ValueError(
            "Plex token not configured. Run 'plex-sync config' to create a config file."
        )

    return PlexServer(url, token)
