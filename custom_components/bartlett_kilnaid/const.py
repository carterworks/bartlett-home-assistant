"""Constants for the Bartlett KilnAid integration."""

from datetime import timedelta

DOMAIN = "bartlett_kilnaid"
CONF_TOKEN = "token"
PLATFORMS = ["binary_sensor", "sensor"]
POLL_INTERVAL = timedelta(seconds=30)
OFFLINE_AFTER = timedelta(minutes=5)
