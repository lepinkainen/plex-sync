import click
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized
from . import config
from .radarr import RadarrClient
import sys
from datetime import datetime
from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer, Header
from textual.containers import Container
from textual.binding import Binding


class MovieSizeApp(App):
    """Textual app for displaying movie size table."""

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
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, movies_data, radarr_client=None):
        super().__init__()
        self.movies_data = movies_data
        self.radarr_client = radarr_client
        self.selected_rows = set()
        self.row_to_movie = {}  # Maps row index to movie object

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            DataTable(id="movie_table")
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#movie_table", DataTable)
        table.cursor_type = "row"

        # Add columns
        table.add_columns("✓", "Rank", "Library", "Movie", "Duration", "Size (GB)", "GB/min", "Rating", "Audience")

        # Store the data with sortable values
        for i, (movie, size_bytes) in enumerate(self.movies_data, 1):
            size_gb = size_bytes / (1024**3)
            library_name = (
                movie.section().title
                if hasattr(movie, "section") and movie.section()
                else "Unknown"
            )

            # Format duration (milliseconds to hours:minutes)
            duration_display = ""
            duration_minutes = 0
            if hasattr(movie, 'duration') and movie.duration:
                hours = movie.duration // (1000 * 60 * 60)
                minutes = (movie.duration % (1000 * 60 * 60)) // (1000 * 60)
                duration_display = f"{hours}h {minutes:02d}m"
                duration_minutes = movie.duration / (1000 * 60)

            # Calculate GB per minute
            gb_per_min_display = ""
            gb_per_min_value = 0
            if duration_minutes > 0:
                gb_per_min_value = size_gb / duration_minutes
                gb_per_min_display = f"{gb_per_min_value:.3f}"

            movie_title = f"{movie.title} ({movie.year})" if movie.year else movie.title

            # Get ratings
            critic_rating = ""
            if hasattr(movie, 'rating') and movie.rating:
                critic_rating = f"{movie.rating:.1f}"

            audience_rating = ""
            if hasattr(movie, 'audienceRating') and movie.audienceRating:
                audience_rating = f"{movie.audienceRating:.1f}"

            # Add row with zero-padded numeric values for proper sorting
            row_key = table.add_row(
                " ",  # Checkbox column
                f"{i:03d}",
                library_name,
                movie_title,
                duration_display or "   0h 00m",
                f"{size_gb:.2f}",
                gb_per_min_display or "0.000",
                critic_rating or "N/A",
                audience_rating or "N/A"
            )
            # Store movie reference for this row
            self.row_to_movie[row_key] = movie

    def action_toggle_select(self) -> None:
        """Toggle selection of the current row."""
        table = self.query_one("#movie_table", DataTable)
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
        """Delete selected movies via Radarr API."""
        if not self.selected_rows:
            self.notify("No movies selected", severity="warning")
            return

        if not self.radarr_client:
            self.notify("Radarr client not configured", severity="error")
            return

        # Get movie objects for selected rows
        selected_movies = [self.row_to_movie[row_key] for row_key in self.selected_rows if row_key in self.row_to_movie]

        self.notify(f"Deleting {len(selected_movies)} movies via Radarr...", severity="information")

        for movie in selected_movies:
            try:
                success = self.radarr_client.delete_movie(movie)
                if success:
                    self.notify(f"Deleted: {movie.title}", severity="success")
                else:
                    self.notify(f"Failed to delete: {movie.title}", severity="error")
            except Exception as e:
                self.notify(f"Error deleting {movie.title}: {str(e)}", severity="error")

        # Clear selections after deletion
        self.selected_rows.clear()
        self.notify("Deletion complete", severity="success")

    def action_generate_reencode(self) -> None:
        """Generate ffmpeg re-encode script for selected movies."""
        if not self.selected_rows:
            self.notify("No movies selected", severity="warning")
            return

        # Get movie objects for selected rows
        selected_movies = [self.row_to_movie[row_key] for row_key in self.selected_rows if row_key in self.row_to_movie]

        if not selected_movies:
            self.notify("No valid movies selected", severity="warning")
            return

        # Collect file paths
        file_paths = []
        for movie in selected_movies:
            if movie.media:
                for media in movie.media:
                    for part in media.parts:
                        if hasattr(part, "file") and part.file:
                            file_paths.append(part.file)

        if not file_paths:
            self.notify("No file paths found for selected movies", severity="warning")
            return

        # Generate script
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        script_path = f"reencode_movies_{timestamp}.sh"

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


@click.command()
@click.option(
    "--limit",
    "-n",
    default=100,
    type=int,
    help="Number of movies to show (default: 100)"
)
@click.option(
    "--unwatched",
    is_flag=True,
    help="Show unwatched movies instead of watched"
)
def cli(limit, unwatched):
    """List largest movies by size (watched by default, use --unwatched for unwatched)."""
    try:
        server = get_plex_server()

        # Load config to check for Radarr settings
        cfg = config.load_config()
        radarr_client = None

        # Initialize Radarr client if enabled
        if cfg.get("radarr", {}).get("enabled", False):
            radarr_url = cfg["radarr"].get("url")
            radarr_api_key = cfg["radarr"].get("api_key")

            if radarr_url and radarr_api_key:
                try:
                    radarr_client = RadarrClient(radarr_url, radarr_api_key)
                    if radarr_client.test_connection():
                        click.echo("Radarr integration enabled")
                    else:
                        click.echo("Warning: Failed to connect to Radarr", err=True)
                        radarr_client = None
                except Exception as e:
                    click.echo(f"Warning: Error initializing Radarr client: {str(e)}", err=True)
            else:
                click.echo("Warning: Radarr is enabled but URL or API key is missing", err=True)

        # Find movie libraries
        movie_sections = [
            section for section in server.library.sections() if section.type == "movie"
        ]

        if not movie_sections:
            click.echo("No movie libraries found.")
            return

        # Collect movies with their sizes based on watch status
        filter_type = "unwatched" if unwatched else "watched"
        movies_list = []

        for section in movie_sections:
            click.echo(f"Scanning library: {section.title} ({filter_type} movies)")
            for movie in section.all():
                if movie.isWatched != unwatched and movie.media:
                    # Get total size in bytes from all media parts
                    total_size = sum(
                        part.size
                        for media in movie.media
                        for part in media.parts
                        if hasattr(part, "size")
                    )
                    if total_size > 0:
                        movies_list.append((movie, total_size))

        # Sort by size (largest first) and take top N
        movies_list.sort(key=lambda x: x[1], reverse=True)
        top_movies = movies_list[:limit]

        if not top_movies:
            click.echo(f"No {filter_type} movies with size information found.")
            return

        # Run Textual app with Radarr client if available
        app = MovieSizeApp(top_movies, radarr_client=radarr_client)
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
