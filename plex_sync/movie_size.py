import click
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized
from . import config
import sys
from textual.app import App, ComposeResult
from textual.widgets import DataTable
from textual.containers import Container


class MovieSizeApp(App):
    """Textual app for displaying movie size table."""
    
    def __init__(self, movies_data):
        super().__init__()
        self.movies_data = movies_data
    
    def compose(self) -> ComposeResult:
        yield Container(
            DataTable(id="movie_table")
        )
    
    def on_mount(self) -> None:
        table = self.query_one("#movie_table", DataTable)
        table.cursor_type = "row"
        
        # Add columns
        table.add_columns("Rank", "Library", "Movie", "Duration", "Size (GB)", "GB/min")
        
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
                gb_per_min_display = f"{gb_per_min_value:07.3f}"

            movie_title = f"{movie.title} ({movie.year})" if movie.year else movie.title

            # Add row with zero-padded numeric values for proper sorting
            table.add_row(
                f"{i:03d}",
                library_name,
                movie_title,
                duration_display or "   0h 00m",
                f"{size_gb:09.2f}",
                gb_per_min_display or "000.000"
            )


@click.command()
@click.option(
    "--limit",
    "-n",
    default=50,
    type=int,
    help="Number of movies to show (default: 50)"
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

        # Run Textual app
        app = MovieSizeApp(top_movies)
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
