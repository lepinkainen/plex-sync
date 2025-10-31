import click
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized, NotFound
from . import config
from typing import Dict, Any, cast, List, Optional
import os
import subprocess
import sys
import json
from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import DataTable
from textual.containers import Container


@click.group()
def cli():
    """Plex Sync - A tool to manage and sync Plex content."""
    pass


@click.group()
def list():
    """List libraries, shows, or unwatched content."""
    pass


@list.command()
def libraries():
    """List all libraries on the Plex server."""
    click.echo("Listing libraries")
    try:
        sections = get_plex_server().library.sections()

        for section in sections:
            click.echo(f"- {section.title} ({section.type})")
    except Unauthorized:
        click.echo(
            "Error: Unauthorized access to Plex server. Check your token and URL."
        )
        exit(1)
    except Exception as e:
        click.echo(f"Error connecting to Plex server: {str(e)}")
        exit(1)


@list.command()
@click.argument("name")
def library(name):
    """List unwatched content from a specific library."""
    click.echo(f"Listing unwatched from library '{name}'")
    try:
        sections = get_plex_server().library.sections()

        for section in sections:
            if section.title == name:
                if section.type == "show":
                    print_unwatched_shows(section.all())
                elif section.type == "movie":
                    print_unwatched_movies(section.all())
                return

        click.echo(f"Library '{name}' not found.")
    except Unauthorized:
        click.echo(
            "Error: Unauthorized access to Plex server. Check your token and URL."
        )
        exit(1)
    except Exception as e:
        click.echo(f"Error connecting to Plex server: {str(e)}")
        exit(1)


class LibraryListApp(App):
    """Textual app for displaying library content table."""
    
    def __init__(self, content_data, content_type):
        super().__init__()
        self.content_data = content_data
        self.content_type = content_type
    
    def compose(self) -> ComposeResult:
        yield Container(
            DataTable(id="content_table")
        )
    
    def on_mount(self) -> None:
        table = self.query_one("#content_table", DataTable)
        table.cursor_type = "row"
        
        if self.content_type == "show":
            table.add_columns("Show", "Total Episodes", "Unwatched", "% Unwatched")
            
            for show_data in self.content_data:
                show_title = show_data["title"]
                total_episodes = show_data["total_episodes"]
                unwatched_episodes = show_data["unwatched_episodes"]
                unwatched_percentage = (unwatched_episodes / total_episodes * 100) if total_episodes > 0 else 0
                
                table.add_row(
                    show_title,
                    str(total_episodes),
                    str(unwatched_episodes),
                    f"{unwatched_percentage:.1f}%"
                )
        elif self.content_type == "movie":
            table.add_columns("Movie", "Year", "Duration")
            
            for movie_data in self.content_data:
                movie_title = movie_data["title"]
                year = str(movie_data.get("year", ""))
                duration = movie_data.get("duration", "")
                
                table.add_row(movie_title, year, duration)


def print_unwatched_movies(movies):
    """Display unwatched movies in a table."""
    movies_data = []
    for movie in movies:
        if movie.isWatched is False:
            duration_display = ""
            if hasattr(movie, 'duration') and movie.duration:
                hours = movie.duration // (1000 * 60 * 60)
                minutes = (movie.duration % (1000 * 60 * 60)) // (1000 * 60)
                duration_display = f"{hours}h {minutes}m"
            
            movies_data.append({
                "title": movie.title,
                "year": movie.year,
                "duration": duration_display
            })
    
    if not movies_data:
        click.echo("No unwatched movies found.")
        return
    
    app = LibraryListApp(movies_data, "movie")
    app.run()


def print_unwatched_shows(shows):
    """Display shows with unwatched episodes in a table."""
    shows_data = []
    for show in shows:
        episodes = show.episodes()
        unwatched_episodes = [
            episode for episode in episodes if episode.isWatched is False
        ]
        if len(unwatched_episodes) == 0:
            continue
        
        shows_data.append({
            "title": show.title,
            "total_episodes": len(episodes),
            "unwatched_episodes": len(unwatched_episodes)
        })
    
    if not shows_data:
        click.echo("No shows with unwatched episodes found.")
        return
    
    app = LibraryListApp(shows_data, "show")
    app.run()


@list.command()
@click.argument("show_name")
@click.option("--library", "-l", default=None, help="Library name containing the show")
def unwatched(show_name, library):
    """List unwatched episodes for a specific show."""
    try:
        get_unwatched_episodes(show_name, library)
    except Unauthorized:
        click.echo(
            "Error: Unauthorized access to Plex server. Check your token and URL."
        )
        exit(1)
    except Exception as e:
        click.echo(f"Error: {str(e)}")
        exit(1)


@cli.command()
@click.option(
    "--dry-run", is_flag=True, help="Show what would be synced without actually syncing"
)
@click.option(
    "--rsync-only",
    is_flag=True,
    help="Only perform the rsync operation on previously found files",
)
def sync(dry_run, rsync_only):
    """Sync unwatched episodes based on configuration."""
    try:
        print("Loading config")
        cfg = config.load_config()

        # Debug output to see what's in the config
        print("Config loaded")

        # Collect all file paths to sync
        all_files_to_sync = []

        if not rsync_only:
            # Get default episode limit from config or use 10 if not specified
            default_episode_limit = 10
            if "defaults" in cfg["sync"] and "episode_limit" in cfg["sync"]["defaults"]:
                sync_defaults = cast(Dict[str, Any], cfg["sync"]["defaults"])
                default_episode_limit = sync_defaults["episode_limit"]

            print("Connecting to Plex server")
            plex = get_plex_server()
            print("Connected to Plex server")

            # Process each library in the sync config
            for library_name, shows in cfg["sync"].items():
                # Skip the defaults section
                if library_name == "defaults":
                    continue

                click.echo(f"\n=== Library: {library_name} ===")

                # Find the library
                library = None
                for section in plex.library.sections():
                    if section.title == library_name:
                        library = section
                        break

                if not library:
                    click.echo(
                        f"Warning: Library '{library_name}' not found on Plex server. Skipping."
                    )
                    continue

                if not shows:
                    click.echo(f"No shows configured for library '{library_name}'")
                    continue

                # Process each show in the library
                for show_config in shows:
                    # Handle both string format and dictionary format
                    show_name = show_config
                    episode_limit = default_episode_limit

                    # If show_config is a dictionary with name and episode_limit
                    if isinstance(show_config, dict) and "name" in show_config:
                        show_dict = cast(Dict[str, Any], show_config)
                        show_name = show_dict["name"]
                        if "episode_limit" in show_dict:
                            episode_limit = show_dict["episode_limit"]

                    click.echo(
                        f"\n--- {show_name} (Latest {episode_limit} episodes) ---"
                    )
                    try:
                        episode_files = get_unwatched_episodes(
                            show_name, library_name, episode_limit
                        )
                        all_files_to_sync.extend(episode_files)
                    except ValueError as e:
                        click.echo(f"Error: {str(e)}")
                    except Exception as e:
                        click.echo(f"Error processing '{show_name}': {str(e)}")

            # Save the list of files for future rsync-only operations
            if all_files_to_sync:
                save_synced_files(all_files_to_sync)
        else:
            click.echo("Rsync-only mode: Loading previously synced files from cache")
            all_files_to_sync = load_synced_files()
            if not all_files_to_sync:
                click.echo("No previously synced files found in cache")
                return

        # Sync all collected files
        if all_files_to_sync:
            click.echo(f"\nFound {len(all_files_to_sync)} files to sync")
            if dry_run:
                click.echo("Dry run mode - not actually syncing files")
                for file_path in all_files_to_sync:
                    click.echo(f"Would sync: {file_path}")
            else:
                sync_files_with_rsync(all_files_to_sync)
        else:
            click.echo("No files found to sync")

    except Unauthorized:
        click.echo(
            "Error: Unauthorized access to Plex server. Check your token and URL."
        )
        exit(1)
    except Exception as e:
        click.echo(f"Error: {str(e)}")
        exit(1)


@cli.command()
def debug():
    """Debug command to print configuration information."""
    config_path = config.get_config_path()
    click.echo(f"Config file path: {config_path}")

    if config_path:
        click.echo(f"Config file exists: {config_path.exists()}")
        try:
            with open(config_path, "r") as file:
                content = file.read()
                click.echo(f"Config file content:\n{content}")
        except Exception as e:
            click.echo(f"Error reading config file: {e}")

    cfg = config.load_config()
    click.echo(f"Loaded config: {cfg}")


@cli.command()
@click.option(
    "--dry-run", is_flag=True, help="Show what would be synced without actually syncing"
)
def rsync(dry_run):
    """Sync previously found unwatched episodes using rsync."""
    try:
        click.echo("Loading previously synced files from cache")
        files_to_sync = load_synced_files()

        if not files_to_sync:
            click.echo("No previously synced files found in cache")
            return

        click.echo(f"Found {len(files_to_sync)} files to sync")

        if dry_run:
            click.echo("Dry run mode - not actually syncing files")
            for file_path in files_to_sync:
                click.echo(f"Would sync: {file_path}")
        else:
            sync_files_with_rsync(files_to_sync)

    except Exception as e:
        click.echo(f"Error: {str(e)}")
        exit(1)


cli.add_command(list)


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


def get_unwatched_episodes(show_name, library_name=None, episode_limit=None):
    """Get unwatched episodes for a specific show."""
    # Get all shows
    sections = get_plex_server().library.sections()

    # Find the right library
    target_section = None
    if library_name:
        for section in sections:
            if section.type == "show" and section.title == library_name:
                target_section = section
                break

        if not target_section:
            raise ValueError(
                f"Library '{library_name}' not found or is not a TV show library"
            )
    else:
        # Try to find a TV show library
        for section in sections:
            if section.type == "show":
                target_section = section
                break

        if not target_section:
            raise ValueError("No TV show library found")

    # Get all shows from the library
    shows = target_section.all()

    # Find the specific show
    target_show = None
    for show in shows:
        if show.title.lower() == show_name.lower():
            target_show = show
            break

    if target_show is None:
        raise ValueError(f"Show '{show_name}' not found in Plex library")

    # Get all episodes for the show
    episodes = target_show.episodes()

    # Filter unwatched episodes
    unwatched_episodes = [episode for episode in episodes if episode.isWatched is False]

    if not unwatched_episodes:
        click.echo(f"No unwatched episodes found for '{show_name}'")
        return []

    # Sort episodes by air date (oldest first) and limit if specified
    unwatched_episodes.sort(
        key=lambda x: x.originallyAvailableAt or x.addedAt, reverse=False
    )

    if episode_limit and len(unwatched_episodes) > episode_limit:
        limited_episodes = unwatched_episodes[:episode_limit]
        click.echo(
            f"Showing {episode_limit} latest unwatched episodes for '{target_show.title}' (out of {len(unwatched_episodes)} total):"
        )
    else:
        limited_episodes = unwatched_episodes
        click.echo(f"Unwatched episodes for '{target_show.title}':")

    # Sort limited episodes by season and episode for display
    limited_episodes.sort(key=lambda x: (x.seasonNumber or 0, x.episodeNumber or 0))

    # Collect file paths for episodes
    episode_files = []

    for episode in limited_episodes:
        click.echo(
            f"- {episode.title} (Season {episode.seasonNumber}, Episode {episode.episodeNumber})"
        )
        try:
            file_path = episode.media[0].parts[0].file
            click.echo(f"  {file_path}")
            episode_files.append(file_path)
        except (IndexError, AttributeError):
            click.echo("  (File path not available)")

    if episode_limit and len(unwatched_episodes) > episode_limit:
        click.echo(
            f"Total unwatched episodes: {len(unwatched_episodes)} (showing latest {len(limited_episodes)})"
        )
    else:
        click.echo(f"Total unwatched episodes: {len(unwatched_episodes)}")

    return episode_files


def run_sync(rsync_only=False):
    """Run the sync logic without Click's decorators."""
    print("Running sync logic directly")
    try:
        cfg = config.load_config()

        # Check if sync configuration exists
        if "sync" not in cfg:
            print("Error: No sync configuration found in config file.")
            return

        # Collect all file paths to sync
        all_files_to_sync = []

        if not rsync_only:
            # Get default episode limit from config or use 10 if not specified
            default_episode_limit = 10
            if "defaults" in cfg["sync"] and "episode_limit" in cfg["sync"]["defaults"]:
                sync_defaults = cast(Dict[str, Any], cfg["sync"]["defaults"])
                default_episode_limit = sync_defaults["episode_limit"]

            plex = get_plex_server()

            # Process each library in the sync config
            for library_name, shows in cfg["sync"].items():
                # Skip the defaults section
                if library_name == "defaults":
                    continue

                print(f"\n=== Library: {library_name} ===")

                # Find the library
                library = None
                for section in plex.library.sections():
                    if section.title == library_name:
                        library = section
                        break

                if not library:
                    print(
                        f"Warning: Library '{library_name}' not found on Plex server. Skipping."
                    )
                    continue

                if not shows:
                    print(f"No shows configured for library '{library_name}'")
                    continue

                # Process each show in the library
                for show_config in shows:
                    # Handle both string format and dictionary format
                    show_name = show_config
                    episode_limit = default_episode_limit

                    # If show_config is a dictionary with name and episode_limit
                    if isinstance(show_config, dict) and "name" in show_config:
                        show_dict = cast(Dict[str, Any], show_config)
                        show_name = show_dict["name"]
                        if "episode_limit" in show_dict:
                            episode_limit = show_dict["episode_limit"]

                    print(f"\n--- {show_name} (Latest {episode_limit} episodes) ---")
                    try:
                        episode_files = get_unwatched_episodes(
                            show_name, library_name, episode_limit
                        )
                        all_files_to_sync.extend(episode_files)
                    except ValueError as e:
                        print(f"Error: {str(e)}")
                    except Exception as e:
                        print(f"Error processing '{show_name}': {str(e)}")

            # Save the list of files for future rsync-only operations
            if all_files_to_sync:
                save_synced_files(all_files_to_sync)
        else:
            print("Rsync-only mode: Loading previously synced files from cache")
            all_files_to_sync = load_synced_files()
            if not all_files_to_sync:
                print("No previously synced files found in cache")
                return

        # Sync all collected files
        if all_files_to_sync:
            print(f"\nFound {len(all_files_to_sync)} files to sync")
            sync_files_with_rsync(all_files_to_sync)
        else:
            print("No files found to sync")

    except Unauthorized:
        print("Error: Unauthorized access to Plex server. Check your token and URL.")
        exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)


def sync_files_with_rsync(file_paths):
    """Sync files using rsync based on configuration."""
    if not file_paths:
        click.echo("No files to sync")
        return

    cfg = config.load_config()

    # Check if rsync configuration exists
    if "rsync" not in cfg:
        click.echo("Error: No rsync configuration found in config file.")
        return

    server_path = cfg["rsync"].get("server_path")
    target = cfg["rsync"].get("target")
    rsync_options = cfg["rsync"].get("options", "-avP")

    if not server_path:
        click.echo("Error: server_path not configured in rsync settings")
        return

    if not target:
        click.echo("Error: target not configured in rsync settings")
        return

    click.echo(f"\n=== Syncing {len(file_paths)} files with rsync ===")

    for file_path in file_paths:
        # Convert server-side path to local path by removing the server_path prefix
        if server_path and file_path.startswith(server_path):
            relative_path = file_path[len(server_path) :].lstrip("/")
        else:
            # If the file path doesn't start with server_path, use the full path
            # This might happen if the server_path is not correctly configured
            click.echo(
                f"Warning: File path {file_path} doesn't start with server_path {server_path}"
            )
            relative_path = file_path.lstrip("/")

        # Construct the destination path
        dest_path = f"{target}{relative_path}"

        click.echo(f"Syncing: {file_path} -> {dest_path}")

        # Construct the rsync command
        # The file_path is the source on the Plex server
        # The dest_path is where we want to copy it to locally
        rsync_cmd = ["rsync"]
        rsync_cmd.extend(rsync_options.split())
        rsync_cmd.append(file_path)
        rsync_cmd.append(dest_path)

        try:
            # Execute the rsync command
            click.echo(f"Running: {' '.join(rsync_cmd)}")
            result = subprocess.run(
                rsync_cmd, capture_output=True, text=True, check=False
            )

            if result.returncode == 0:
                click.echo(f"Successfully synced: {file_path}")
            else:
                click.echo(f"Error syncing {file_path}: {result.stderr}")
        except Exception as e:
            click.echo(f"Error executing rsync: {str(e)}")


def get_cache_path():
    """Get the path to the cache file."""
    config_path = config.get_config_path()
    if config_path:
        cache_dir = config_path.parent
    else:
        # Use default cache location
        cache_dir = Path.home() / ".cache" / "plex-sync"
        cache_dir.mkdir(parents=True, exist_ok=True)

    return cache_dir / "last_sync.json"


def save_synced_files(file_paths):
    """Save the list of synced files to a cache file."""
    cache_path = get_cache_path()
    try:
        with open(cache_path, "w") as f:
            json.dump({"files": file_paths}, f)
        click.echo(f"Saved {len(file_paths)} file paths to {cache_path}")
        return True
    except Exception as e:
        click.echo(f"Error saving synced files: {str(e)}")
        return False


def load_synced_files():
    """Load the list of previously synced files from the cache file."""
    cache_path = get_cache_path()
    if not cache_path.exists():
        click.echo(f"Cache file not found: {cache_path}")
        return []

    try:
        with open(cache_path, "r") as f:
            data = json.load(f)
            return data.get("files", [])
    except Exception as e:
        click.echo(f"Error loading synced files: {str(e)}")
        return []


if __name__ == "__main__":
    try:
        cli()
    except Exception as e:
        print(f"Error in CLI: {e}")
        import traceback

        traceback.print_exc()
