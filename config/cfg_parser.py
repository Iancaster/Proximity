
"""
Loads configuration details from the .ini files.
"""

from configparser import ConfigParser
from pathlib import Path
from os import environ
from datetime import datetime as dt

class Config:

    def __init__(self):

        self.parser = ConfigParser(interpolation = None)
        config_path = Path.cwd() / "config"

        self._load_config(config_path / "default.ini")
        self._load_config(config_path / "local.ini")

        return

    def get(self, section: str, option: str) -> bool | int | float | str:

        env_var = f"{section.upper()}_{option.upper()}"
        if env_var in environ:
            return environ[env_var]

        result = self.parser.get(
            section, 
            option, 
            fallback = "Missing.", 
            raw = True)
        if result == "Missing.":
            raise KeyError(f"Missing config option \"{option}\" in section \"{section}\"!")

        return self._reduce_var(result)

    def _load_config(self, config_path: Path) -> None:

        if not config_path.exists():
            return
        
        try:
            self.parser.read(config_path)
            print(f"Loaded config from {config_path}.")

        except Exception as e:
            print(f"Failed to load config from {config_path}: {e}.")
            
        return

    def _reduce_var(self, value: str) -> bool | int | float | str:

        if not value or value.strip() == '':
            return False

        value_lower = value.lower()
        if value_lower in ('true', 'false'):
            return value_lower == 'true'

        if value.strip().lstrip('-+').isdigit():
            return int(value)

        try:
            return float(value)
        except ValueError:
            pass

        return value
        
config = Config()
def cfg(section: str, option: str) -> int | float | str:
    return config.get(section, option)