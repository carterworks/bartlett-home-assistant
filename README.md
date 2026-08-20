# Bartlett KilnAid for Home Assistant

Read-only Home Assistant integration for Bartlett Genesis kiln controllers registered with KilnAid.

> [!WARNING]
> This is experimental, slop/vibe-coded software that has only been tested with a Bartlett Genesis 2.0. It is unofficial, is not affiliated with or supported by Bartlett Instrument Company, and must not be used as a kiln safety system. Always monitor and operate a kiln according to its manufacturer's safety instructions.

## Entities

- Controller connectivity, mode, alarm, and error state
- Thermocouple temperatures and firing set point
- Program, segment, firing time, and hold time remaining
- Total firing count and last cloud update

The integration treats controller data older than five minutes as offline. It does not expose remote start, stop, or programming controls.

## Cloud polling

One coordinator fetches all claimed kilns for an account in a shared cloud request. Home Assistant schedules that request only while coordinator entities have subscribers.

- Approximately every minute after an online kiln is detected firing, waiting for a delayed start, reporting an error, completing a firing, or in another active or transitional mode
- Approximately every five minutes when every kiln is idle, not connected, or offline
- An idle-to-active transition can therefore take nearly five minutes to detect; polling changes to the one-minute interval after detection
- After an HTTP 429 response, according to a valid `Retry-After` delay bounded between one second and 24 hours, with a five-minute fallback when no valid delay is provided

## Pairing and safety

Claiming and pairing are different operations in KilnAid:

- **Claiming** associates a controller with an account and is required for monitoring.
- **Pairing** authorizes remote programming and stopping after a firing.

This integration only reads monitoring data, so the controller does not need to be paired. Remote-control endpoints are intentionally not implemented.

## Prerequisites

1. Create an account at [KilnAid](https://kilnaid.bartinst.com/).
2. Claim the controller using its serial number and MAC address from `Menu > Data Menu > Kiln Info`.
3. Confirm that the kiln appears in the KilnAid app or website.

## Installation

Add `https://github.com/carterworks/bartlett-home-assistant` to HACS as an **Integration** custom repository, install **Bartlett KilnAid**, and restart Home Assistant.

Then open **Settings > Devices & services > Add integration**, search for **Bartlett KilnAid**, and enter the KilnAid account credentials. The password is used only to obtain an authentication token and is not stored.

At least one kiln must already be claimed. If none are claimed, the config entry remains in setup retry and checks inventory again on a later retry; claim a kiln and reload the entry to retry immediately.

## Local log server

The Genesis controller also has a manually enabled historical-log server:

```text
GET http://CONTROLLER_IP/index?code=DISPLAYED_CODE
GET http://CONTROLLER_IP/log_file.csv?code=DISPLAYED_CODE,id=LOG_ID
```

Enable it with `Menu > Configuration > Export Log File`. It exposes up to ten firing CSV files, but it must be manually enabled and is not used for live Home Assistant data.

## Status

This integration is based on the request flow used by KilnAid and has been validated against a claimed Bartlett Genesis controller.

Kiln inventory is loaded when the integration starts. Reload the integration after claiming or unclaiming a controller.
