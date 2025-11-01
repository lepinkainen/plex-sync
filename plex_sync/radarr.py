"""Radarr API client for managing movies."""
import requests
from typing import Optional, Dict, Any
import click


class RadarrClient:
    """Client for interacting with Radarr API."""

    def __init__(self, url: str, api_key: str):
        """Initialize the Radarr client.

        Args:
            url: Radarr server URL (e.g., http://localhost:7878)
            api_key: Radarr API key
        """
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'X-Api-Key': api_key,
            'Content-Type': 'application/json'
        })

    def _get(self, endpoint: str) -> Optional[Any]:
        """Make a GET request to Radarr API."""
        try:
            response = self.session.get(f"{self.url}/api/v3/{endpoint}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            click.echo(f"Radarr API GET error: {str(e)}", err=True)
            return None

    def _delete(self, endpoint: str, params: Optional[Dict] = None) -> bool:
        """Make a DELETE request to Radarr API."""
        try:
            response = self.session.delete(f"{self.url}/api/v3/{endpoint}", params=params)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            click.echo(f"Radarr API DELETE error: {str(e)}", err=True)
            return False

    def find_movie_by_title(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """Find a movie in Radarr by title and optionally year.

        Args:
            title: Movie title
            year: Optional movie year for more accurate matching

        Returns:
            Movie object from Radarr if found, None otherwise
        """
        movies = self._get("movie")
        if not movies:
            return None

        # Normalize the search title
        search_title = title.lower().strip()

        for movie in movies:
            movie_title = movie.get('title', '').lower().strip()

            # Try exact title match
            if movie_title == search_title:
                # If year is provided, verify it matches
                if year:
                    movie_year = movie.get('year')
                    if movie_year == year:
                        return movie
                else:
                    return movie

            # Try alternative titles
            alternative_titles = movie.get('alternateTitles', [])
            for alt_title in alternative_titles:
                if alt_title.get('title', '').lower().strip() == search_title:
                    if year:
                        movie_year = movie.get('year')
                        if movie_year == year:
                            return movie
                    else:
                        return movie

        # If no exact match found and year is provided, try title-only match
        if year:
            for movie in movies:
                movie_title = movie.get('title', '').lower().strip()
                if movie_title == search_title:
                    return movie

        return None

    def delete_movie(self, plex_movie, delete_files: bool = True, add_exclusion: bool = True) -> bool:
        """Delete a movie from Radarr.

        Args:
            plex_movie: Plex movie object
            delete_files: Whether to delete movie files from disk
            add_exclusion: Whether to add the movie to exclusion list (prevents re-downloading)

        Returns:
            True if successful, False otherwise
        """
        # Find the movie in Radarr
        title = plex_movie.title
        year = getattr(plex_movie, 'year', None)

        radarr_movie = self.find_movie_by_title(title, year)

        if not radarr_movie:
            click.echo(f"Movie '{title}' ({year}) not found in Radarr", err=True)
            return False

        movie_id = radarr_movie['id']
        click.echo(f"Found in Radarr: {radarr_movie['title']} ({radarr_movie.get('year', 'N/A')}) [ID: {movie_id}]")

        # Delete the movie
        params = {
            'deleteFiles': 'true' if delete_files else 'false',
            'addImportExclusion': 'true' if add_exclusion else 'false'
        }

        success = self._delete(f"movie/{movie_id}", params=params)

        if success:
            click.echo(f"Successfully deleted '{title}' from Radarr (files deleted: {delete_files}, exclusion added: {add_exclusion})")
        else:
            click.echo(f"Failed to delete '{title}' from Radarr", err=True)

        return success

    def get_movie_by_id(self, movie_id: int) -> Optional[Dict]:
        """Get movie details by Radarr ID."""
        return self._get(f"movie/{movie_id}")

    def test_connection(self) -> bool:
        """Test the connection to Radarr."""
        try:
            result = self._get("system/status")
            if result:
                click.echo(f"Connected to Radarr v{result.get('version', 'unknown')}")
                return True
            return False
        except Exception as e:
            click.echo(f"Failed to connect to Radarr: {str(e)}", err=True)
            return False
