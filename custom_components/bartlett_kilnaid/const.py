"""Constants for the Bartlett KilnAid integration."""

from datetime import timedelta

DOMAIN = "bartlett_kilnaid"
CONF_TOKEN = "token"
PLATFORMS = ["binary_sensor", "sensor"]
ACTIVE_POLL_INTERVAL = timedelta(minutes=1)
IDLE_POLL_INTERVAL = timedelta(minutes=5)
RATE_LIMIT_RETRY_AFTER = IDLE_POLL_INTERVAL.total_seconds()
MIN_RATE_LIMIT_RETRY_AFTER = 1
MAX_RATE_LIMIT_RETRY_AFTER = 24 * 60 * 60
OFFLINE_AFTER = timedelta(minutes=5)
