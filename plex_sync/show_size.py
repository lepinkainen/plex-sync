import click
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized
from . import config
from .sonarr import SonarrClient
import sys
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
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, shows_data, sonarr_client=None):
        super().__init__()
        self.shows_data = shows_data
        self.sonarr_client = sonarr_client
        self.selected_rows = set()
        self.row_to_show = {}  # Maps row index to show object

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            DataTable(id="show_table")
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#show_table", DataTable)
        table.cursor_type = "row"

        # Add columns
        table.add_columns("✓", "Rank", "Library", "Show", "Episodes", "Size (GB)", "GB/ep", "Rating", "Audience")

        # Store the data with sortable values
        for i, (show, size_bytes, episode_count) in enumerate(self.shows_data, 1):
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
                gb_per_episode_display = f"{gb_per_episode:07.3f}"

            show_title = f"{show.title} ({show.year})" if hasattr(show, 'year') and show.year else show.title

            # Get ratings
            critic_rating = ""
            if hasattr(show, 'rating') and show.rating:
                critic_rating = f"{show.rating:.1f}"

            audience_rating = ""
            if hasattr(show, 'audienceRating') and show.audienceRating:
                audience_rating = f"{show.audienceRating:.1f}"

            # Add row with zero-padded numeric values for proper sorting
            row_key = table.add_row(
                " ",  # Checkbox column
                f"{i:03d}",
                library_name,
                show_title,
                f"{episode_count:04d}",
                f"{size_gb:09.2f}",
                gb_per_episode_display or "000.000",
                critic_rating or "N/A",
                audience_rating or "N/A"
            )
            # Store show reference for this row
            self.row_to_show[row_key] = show

    def action_toggle_select(self) -> None:
        """Toggle selection of the current row."""
        table = self.query_one("#show_table", DataTable)
        if table.cursor_row is not None:
            row_key = table.cursor_row
            if row_key in self.selected_rows:
                self.selected_rows.remove(row_key)
                # Update the checkbox column (first column, index 0)
                table.update_cell(row_key, 0, " ")
            else:
                self.selected_rows.add(row_key)
                # Update the checkbox column (first column, index 0)
                table.update_cell(row_key, 0, "✓")

    def action_delete_selected(self) -> None:
        """Delete selected TV shows via Sonarr API."""
        if not self.selected_rows:
            self.notify("No shows selected", severity="warning")
            return

        if not self.sonarr_client:
            self.notify("Sonarr client not configured", severity="error")
            return

        # Get show objects for selected rows
        selected_shows = [self.row_to_show[row_key] for row_key in self.selected_rows if row_key in self.row_to_show]

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


@click.command()
@click.option(
    "--limit",
    "-n",
    default=50,
    type=int,
    help="Number of shows to show (default: 50)"
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
                    # Get total size in bytes from all episode media parts
                    total_size = 0
                    for episode in episodes:
                        if episode.media:
                            total_size += sum(
                                part.size
                                for media in episode.media
                                for part in media.parts
                                if hasattr(part, "size")
                            )

                    if total_size > 0:
                        shows_list.append((show, total_size, len(episodes)))

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
