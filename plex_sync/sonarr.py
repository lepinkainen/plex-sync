"""Sonarr API client for managing TV shows."""
import requests
from typing import Optional, Dict, Any
import click


class SonarrClient:
    """Client for interacting with Sonarr API."""

    def __init__(self, url: str, api_key: str):
        """Initialize the Sonarr client.

        Args:
            url: Sonarr server URL (e.g., http://localhost:8989)
            api_key: Sonarr API key
        """
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'X-Api-Key': api_key,
            'Content-Type': 'application/json'
        })

    def _get(self, endpoint: str) -> Optional[Any]:
        """Make a GET request to Sonarr API."""
        try:
            response = self.session.get(f"{self.url}/api/v3/{endpoint}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            click.echo(f"Sonarr API GET error: {str(e)}", err=True)
            return None

    def _delete(self, endpoint: str, params: Optional[Dict] = None) -> bool:
        """Make a DELETE request to Sonarr API."""
        try:
            response = self.session.delete(f"{self.url}/api/v3/{endpoint}", params=params)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            click.echo(f"Sonarr API DELETE error: {str(e)}", err=True)
            return False

    def find_series_by_title(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """Find a TV series in Sonarr by title and optionally year.

        Args:
            title: Series title
            year: Optional year for more accurate matching

        Returns:
            Series object from Sonarr if found, None otherwise
        """
        series_list = self._get("series")
        if not series_list:
            return None

        # Normalize the search title
        search_title = title.lower().strip()

        for series in series_list:
            series_title = series.get('title', '').lower().strip()

            # Try exact title match
            if series_title == search_title:
                # If year is provided, verify it matches
                if year:
                    series_year = series.get('year')
                    if series_year == year:
                        return series
                else:
                    return series

            # Try alternative titles
            alternative_titles = series.get('alternateTitles', [])
            for alt_title in alternative_titles:
                if alt_title.get('title', '').lower().strip() == search_title:
                    if year:
                        series_year = series.get('year')
                        if series_year == year:
                            return series
                    else:
                        return series

        # If no exact match found and year is provided, try title-only match
        if year:
            for series in series_list:
                series_title = series.get('title', '').lower().strip()
                if series_title == search_title:
                    return series

        return None

    def delete_series(self, plex_show, delete_files: bool = True, add_exclusion: bool = True) -> bool:
        """Delete a TV series from Sonarr.

        Args:
            plex_show: Plex show object
            delete_files: Whether to delete series files from disk
            add_exclusion: Whether to add the series to exclusion list (prevents re-downloading)

        Returns:
            True if successful, False otherwise
        """
        # Find the series in Sonarr
        title = plex_show.title
        year = getattr(plex_show, 'year', None)

        sonarr_series = self.find_series_by_title(title, year)

        if not sonarr_series:
            click.echo(f"Series '{title}' ({year}) not found in Sonarr", err=True)
            return False

        series_id = sonarr_series['id']
        click.echo(f"Found in Sonarr: {sonarr_series['title']} ({sonarr_series.get('year', 'N/A')}) [ID: {series_id}]")

        # Delete the series
        params = {
            'deleteFiles': 'true' if delete_files else 'false',
            'addImportListExclusion': 'true' if add_exclusion else 'false'
        }

        success = self._delete(f"series/{series_id}", params=params)

        if success:
            click.echo(f"Successfully deleted '{title}' from Sonarr (files deleted: {delete_files}, exclusion added: {add_exclusion})")
        else:
            click.echo(f"Failed to delete '{title}' from Sonarr", err=True)

        return success

    def get_series_by_id(self, series_id: int) -> Optional[Dict]:
        """Get series details by Sonarr ID."""
        return self._get(f"series/{series_id}")

    def test_connection(self) -> bool:
        """Test the connection to Sonarr."""
        try:
            result = self._get("system/status")
            if result:
                click.echo(f"Connected to Sonarr v{result.get('version', 'unknown')}")
                return True
            return False
        except Exception as e:
            click.echo(f"Failed to connect to Sonarr: {str(e)}", err=True)
            return False
