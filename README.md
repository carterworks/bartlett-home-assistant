# Bartlett KilnAid for Home Assistant

Read-only Home Assistant integration for Bartlett Genesis kiln controllers registered with KilnAid.

## Entities

- Controller connectivity, mode, alarm, and error state
- Thermocouple temperatures and firing set point
- Program, segment, firing time, and hold time remaining
- Total firing count and last cloud update

The integration polls every 30 seconds and treats controller data older than five minutes as offline. It does not expose remote start, stop, or programming controls.

## Prerequisites

1. Create an account at [KilnAid](https://kilnaid.bartinst.com/).
2. Claim the controller using its serial number and MAC address from `Menu > Data Menu > Kiln Info`.
3. Confirm that the kiln appears in the KilnAid app or website.

## Installation

This repository is structured as a HACS custom integration. Once it is hosted on GitHub, add its URL to HACS as an **Integration** custom repository, install **Bartlett KilnAid**, and restart Home Assistant.

Then open **Settings > Devices & services > Add integration**, search for **Bartlett KilnAid**, and enter the KilnAid account credentials. The password is used only to obtain an authentication token and is not stored.

## Local log server

The Genesis controller also has a manually enabled historical-log server:

```text
GET http://CONTROLLER_IP/index?code=DISPLAYED_CODE
GET http://CONTROLLER_IP/log_file.csv?code=DISPLAYED_CODE,id=LOG_ID
```

Enable it with `Menu > Configuration > Export Log File`. It exposes up to ten firing CSV files, but it must be manually enabled and is not used for live Home Assistant data.

## Status

This integration is based on the request flow used by KilnAid 5.0.13 and has been validated against a claimed Genesis 2 controller running firmware `LT4-4.22.0`.

Kiln inventory is loaded when the integration starts. Reload the integration after claiming or unclaiming a controller.
