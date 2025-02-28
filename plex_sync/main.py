import click
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized, NotFound
from . import config


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


@cli.command(name="config")
@click.option("--path", "-p", default=None, help="Path to save the config file")
@click.option("--show", "-s", is_flag=True, help="Show the configuration file path")
def config_cmd(path, show):
    """Manage configuration settings."""
    if show:
        config_path = config.get_config_path()
        if config_path:
            click.echo(f"Configuration file: {config_path}")
        else:
            click.echo("No configuration file found.")
        return

    try:
        config_path = config.create_default_config(path)
        click.echo(f"Created default configuration file at: {config_path}")
        click.echo("Please edit this file to add your Plex server URL and token.")
        click.echo("\nExample configuration:")
        click.echo("""
plex:
  url: http://your-plex-server:32400
  token: your-plex-token
""")
    except Exception as e:
        click.echo(f"Error creating configuration file: {str(e)}")
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


def get_unwatched_episodes(show_name, library_name=None):
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

    click.echo(f"Unwatched episodes for '{target_show.title}':")
    for episode in unwatched_episodes:
        click.echo(
            f"- {episode.title} (Season {episode.seasonNumber}, Episode {episode.episodeNumber})"
        )
        try:
            click.echo(f"  {episode.media[0].parts[0].file}")
        except (IndexError, AttributeError):
            click.echo("  (File path not available)")

    click.echo(f"Total unwatched episodes: {len(unwatched_episodes)}")
    return unwatched_episodes


if __name__ == "__main__":
    cli()
