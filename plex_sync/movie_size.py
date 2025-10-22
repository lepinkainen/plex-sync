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
                duration_display = f"{hours}h {minutes}m"
                duration_minutes = movie.duration / (1000 * 60)
            
            # Calculate GB per minute
            gb_per_min_display = ""
            if duration_minutes > 0:
                gb_per_min_value = size_gb / duration_minutes
                gb_per_min_display = f"{gb_per_min_value:.3f}"
            
            movie_title = f"{movie.title} ({movie.year})" if movie.year else movie.title
            
            # Add row
            table.add_row(
                str(i),
                library_name,
                movie_title,
                duration_display,
                f"{size_gb:.2f}",
                gb_per_min_display
            )
    
    def on_data_table_header_clicked(self, event: DataTable.HeaderClicked) -> None:
        """Handle column header clicks for sorting."""
        table = self.query_one("#movie_table", DataTable)
        
        # Map column keys to data indices
        column_map = {
            "Rank": 0,
            "Library": 1, 
            "Movie": 2,
            "Duration": 3,
            "Size (GB)": 4,
            "GB/min": 5
        }
        
        if event.column_key in column_map:
            col_index = column_map[event.column_key]
            
            # Get current data and sort it
            current_data = []
            for row_key in table.rows:
                row_data = table.get_row(row_key)
                current_data.append((row_key, row_data))
            
            # Sort based on column type
            if event.column_key == "Rank":
                current_data.sort(key=lambda x: int(x[1][col_index]))
            elif event.column_key in ["Size (GB)", "GB/min", "Duration"]:
                # For numeric columns, extract the numeric value
                current_data.sort(key=lambda x: float(self._extract_numeric(x[1][col_index])))
            else:
                # For text columns, sort alphabetically
                current_data.sort(key=lambda x: x[1][col_index].lower())
            
            # Clear and repopulate table in sorted order
            table.clear()
            table.add_columns("Rank", "Library", "Movie", "Duration", "Size (GB)", "GB/min")
            
            for row_key, row_data in current_data:
                table.add_row(*row_data)
    
    def _extract_numeric(self, value: str) -> float:
        """Extract numeric value from formatted string."""
        if "GB" in value:
            return float(value.replace(" GB", ""))
        elif "h" in value and "m" in value:
            # Convert duration string to minutes
            parts = value.split()
            hours = int(parts[0].replace("h", ""))
            minutes = int(parts[1].replace("m", ""))
            return hours * 60 + minutes
        else:
            return float(value) if value else 0


@click.command()
def cli():
    """List top 20 largest watched movies by GB used."""
    try:
        server = get_plex_server()

        # Find movie libraries
        movie_sections = [
            section for section in server.library.sections() if section.type == "movie"
        ]

        if not movie_sections:
            click.echo("No movie libraries found.")
            return

        # Collect all watched movies with their sizes
        watched_movies = []

        for section in movie_sections:
            click.echo(f"Scanning library: {section.title}")
            for movie in section.all():
                if movie.isWatched and movie.media:
                    # Get total size in bytes from all media parts
                    total_size = sum(
                        part.size
                        for media in movie.media
                        for part in media.parts
                        if hasattr(part, "size")
                    )
                    if total_size > 0:
                        watched_movies.append((movie, total_size))

        # Sort by size (largest first) and take top 50
        watched_movies.sort(key=lambda x: x[1], reverse=True)
        top_movies = watched_movies[:50]

        if not top_movies:
            click.echo("No watched movies with size information found.")
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
