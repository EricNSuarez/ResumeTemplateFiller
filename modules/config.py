import configparser
from pathlib import Path
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """Raised when config is invalid or missing required fields."""

def load_config(
    config_path: Path,
    required_sections: List[Tuple[str, List[str]]]
) -> configparser.ConfigParser:
    """
    Load and validate a configuration file.

    Args:
    config_path: Path to the config file.
    required_sections: List of tuples specifying required sections and their required keys.
                              Example: [('database', ['DBPath']), ('user_story', ['USER_STORY'])]

    Returns
        Loaded ConfigParser object.

    Raises
        ConfigError: If config file is missing or validation fails.
    """
    logger.debug("Loading configuration from %s", config_path)

    if not config_path.exists():
        logger.error("Config file %s does not exist", config_path)
        raise ConfigError(f"Config file {config_path} not found")

    config = configparser.ConfigParser()
    config.read(config_path)

    for section, required_keys in required_sections:
        if section not in config:
            logger.error("Config file %s missing [%s] section", config_path, section)
            raise ConfigError(f"Missing [{section}] section")

        for key in required_keys:
            if key not in config[section]:
                logger.error("Config file %s missing %s in [%s]", config_path, key, section)
                raise ConfigError(f"Missing {key} in [{section}]")

    logger.info("Configuration loaded successfully")
    return config