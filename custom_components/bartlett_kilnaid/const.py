"""Constants for the Bartlett KilnAid integration."""

from datetime import timedelta

DOMAIN = "bartlett_kilnaid"
CONF_TOKEN = "token"
PLATFORMS = ["binary_sensor", "sensor"]
ACTIVE_POLL_INTERVAL = timedelta(minutes=1)
IDLE_POLL_INTERVAL = timedelta(minutes=5)
RATE_LIMIT_RETRY_AFTER = IDLE_POLL_INTERVAL.total_seconds()
OFFLINE_AFTER = timedelta(minutes=5)
