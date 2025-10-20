import os
import yaml
from pathlib import Path

# Default configuration
DEFAULT_CONFIG = {
    "plex": {
        "url": "http://localhost:32400",
        "token": "",
    },
    "rsync": {
        "server_path": "",
        "target": "",
        "options": "-avP",
    },
}


def get_config_path():
    """Get the path to the config file."""
    # Check for config in current directory first
    local_config = Path.cwd() / "config.yml"
    if local_config.exists():
        return local_config

    # Check for config in user's home directory
    home_config = Path.home() / ".config" / "plex-sync" / "config.yml"
    if home_config.exists():
        return home_config

    # Check for config in XDG_CONFIG_HOME
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        xdg_config = Path(xdg_config_home) / "plex-sync" / "config.yml"
        if xdg_config.exists():
            return xdg_config

    return None


def load_config():
    """Load configuration from environment variables or config file."""
    config = DEFAULT_CONFIG.copy()

    # Try to load from config file
    config_path = get_config_path()
    if config_path:
        try:
            with open(config_path, "r") as file:
                file_config = yaml.safe_load(file)
                if file_config:
                    # Merge configurations
                    deep_update(config, file_config)
        except Exception as e:
            print(f"Warning: Error reading config file: {e}")

    # Override with environment variables if present
    plex_url = os.environ.get("PLEX_URL")
    if plex_url:
        config["plex"]["url"] = plex_url

    plex_token = os.environ.get("PLEX_TOKEN")
    if plex_token:
        config["plex"]["token"] = plex_token

    return config


def deep_update(source, overrides):
    """Recursively update a nested dictionary."""
    for key, value in overrides.items():
        if isinstance(value, dict) and key in source and isinstance(source[key], dict):
            deep_update(source[key], value)
        else:
            source[key] = value


def create_default_config(path=None):
    """Create a default configuration file."""
    if path is None:
        # Create in user's config directory
        config_dir = Path.home() / ".config" / "plex-sync"
        config_dir.mkdir(parents=True, exist_ok=True)
        path = config_dir / "config.yml"

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write the default config
    with open(path, "w") as file:
        yaml.dump(DEFAULT_CONFIG, file, default_flow_style=False, sort_keys=False)

    return path
