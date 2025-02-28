import click
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized, NotFound
from . import config
from typing import Dict, Any, cast


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


def print_unwatched_movies(movies):
    """Print a list of unwatched movies."""
    unwatched_count = 0
    for movie in movies:
        if movie.isWatched is False:
            click.echo(f"{movie.title}")
            unwatched_count += 1

    if unwatched_count == 0:
        click.echo("No unwatched movies found.")
    else:
        click.echo(f"Total unwatched movies: {unwatched_count}")


def print_unwatched_shows(shows):
    """Print a list of shows with unwatched episodes."""
    shows_with_unwatched = 0
    for show in shows:
        episodes = show.episodes()
        unwatched_episodes = [
            episode for episode in episodes if episode.isWatched is False
        ]
        if len(unwatched_episodes) == 0:
            continue

        click.echo(
            f"{show.title} - {len(episodes)} episodes - {len(unwatched_episodes)} unwatched"
        )
        shows_with_unwatched += 1

    if shows_with_unwatched == 0:
        click.echo("No shows with unwatched episodes found.")


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
def sync():
    """Sync unwatched episodes based on configuration."""
    try:
        print("Loading config")
        cfg = config.load_config()

        # Debug output to see what's in the config
        print("Config loaded")

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

                click.echo(f"\n--- {show_name} (Latest {episode_limit} episodes) ---")
                try:
                    get_unwatched_episodes(show_name, library_name, episode_limit)
                except ValueError as e:
                    click.echo(f"Error: {str(e)}")
                except Exception as e:
                    click.echo(f"Error processing '{show_name}': {str(e)}")

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
        return

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

    for episode in limited_episodes:
        click.echo(
            f"- {episode.title} (Season {episode.seasonNumber}, Episode {episode.episodeNumber})"
        )
        try:
            click.echo(f"  {episode.media[0].parts[0].file}")
        except (IndexError, AttributeError):
            click.echo("  (File path not available)")

    if episode_limit and len(unwatched_episodes) > episode_limit:
        click.echo(
            f"Total unwatched episodes: {len(unwatched_episodes)} (showing latest {len(limited_episodes)})"
        )
    else:
        click.echo(f"Total unwatched episodes: {len(unwatched_episodes)}")

    return limited_episodes


def run_sync():
    """Run the sync logic without Click's decorators."""
    print("Running sync logic directly")
    try:
        cfg = config.load_config()

        # Check if sync configuration exists
        if "sync" not in cfg:
            print("Error: No sync configuration found in config file.")
            return

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
                    get_unwatched_episodes(show_name, library_name, episode_limit)
                except ValueError as e:
                    print(f"Error: {str(e)}")
                except Exception as e:
                    print(f"Error processing '{show_name}': {str(e)}")

    except Unauthorized:
        print("Error: Unauthorized access to Plex server. Check your token and URL.")
        exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)


if __name__ == "__main__":
    try:
        cli()
    except Exception as e:
        print(f"Error in CLI: {e}")
        import traceback

        traceback.print_exc()
