"""Client for the undocumented Bartlett KilnAid API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession

from .const import OFFLINE_AFTER

LOGIN_URL = "https://bartinst-user-service-prod.herokuapp.com/login"
KILN_API_URL = "https://kiln.bartinst.com"


class BartlettApiError(Exception):
    """Base Bartlett API error."""


class BartlettAuthError(BartlettApiError):
    """Bartlett authentication failed."""


@dataclass(frozen=True, slots=True)
class KilnData:
    """Normalized state for one kiln."""

    serial_number: str
    external_id: str
    name: str
    firmware: str | None
    temperature_scale: str
    number_of_zones: int
    zone_temperatures: tuple[float | None, float | None, float | None]
    set_point: float | None
    mode: str
    program: str | None
    segment: str | None
    firing_minutes: int | None
    hold_minutes: int | None
    total_firings: int | None
    alarm: str | None
    error_number: int | None
    error_text: str | None
    updated_at: datetime | None

    @property
    def online(self) -> bool:
        """Return whether the controller has reported recently."""
        if self.updated_at is None:
            return False
        return datetime.now(UTC) - self.updated_at <= OFFLINE_AFTER


class BartlettApiClient:
    """Read kiln data from Bartlett's cloud services."""

    def __init__(self, session: ClientSession, email: str, token: str) -> None:
        self._session = session
        self.email = email
        self.token = token
        self._kiln_metadata: dict[str, dict[str, Any]] | None = None

    @classmethod
    async def async_authenticate(
        cls, session: ClientSession, email: str, password: str
    ) -> BartlettApiClient:
        """Log in and return an authenticated client."""
        try:
            async with session.post(
                LOGIN_URL,
                json={"email": email.strip(), "password": password},
                headers={"Accept": "application/json", "kaid-version": "kaid-plus"},
            ) as response:
                if response.status in (400, 401, 403):
                    await response.read()
                    raise BartlettAuthError("Invalid KilnAid email or password")
                data = await _response_json(response)
        except TimeoutError as err:
            raise BartlettApiError("KilnAid login timed out") from err
        except ClientError as err:
            raise BartlettApiError("Unable to reach the KilnAid login service") from err

        if response.status >= 400:
            raise BartlettApiError(f"KilnAid login failed with HTTP {response.status}")
        if not isinstance(data, dict) or not data.get("authentication_token"):
            raise BartlettApiError("KilnAid login returned an unexpected response")

        return cls(session, email.strip(), str(data["authentication_token"]))

    async def async_get_kilns(self) -> dict[str, KilnData]:
        """Fetch current state for all kilns claimed by the user."""
        if self._kiln_metadata is None:
            settings = await self._request("POST", "/kilns/settings", json={})
            if not isinstance(settings, list):
                raise BartlettApiError("KilnAid returned invalid kiln settings")
            claimed = [item for item in settings if isinstance(item, dict)]
            external_ids = [
                str(item["kiln_id"]) for item in claimed if item.get("kiln_id")
            ]
            if not external_ids:
                self._kiln_metadata = {}
                return {}

            details = await self._request(
                "POST",
                "/kilnaid-data/settings",
                json={"externalIds": external_ids},
            )
            if not isinstance(details, list):
                raise BartlettApiError("KilnAid returned invalid kiln metadata")
            details_by_id = {
                str(item["externalId"]): item
                for item in details
                if isinstance(item, dict) and item.get("externalId")
            }
            self._kiln_metadata = {
                external_id: {**item, **details_by_id.get(external_id, {})}
                for item in claimed
                if (external_id := str(item.get("kiln_id") or ""))
            }

        if not self._kiln_metadata:
            return {}

        response = await self._request(
            "POST",
            "/kilnaid-data/status",
            json={"externalIds": list(self._kiln_metadata)},
        )
        if not isinstance(response, list):
            raise BartlettApiError("KilnAid returned invalid kiln data")

        status_by_id = {
            str(item["externalId"]): item
            for item in response
            if isinstance(item, dict) and item.get("externalId")
        }
        return {
            kiln.serial_number: kiln
            for external_id, metadata in self._kiln_metadata.items()
            if (
                kiln := parse_kiln(status_by_id.get(external_id, {}), metadata)
            ).serial_number
        }

    async def _request(
        self, method: str, path: str, *, json: dict[str, Any] | None = None
    ) -> Any:
        """Make an authenticated kiln API request."""
        try:
            async with self._session.request(
                method,
                f"{KILN_API_URL}{path}",
                json=json,
                headers={
                    "Accept": "application/json",
                    "auth-token": f"binst-cookie={self.token}",
                    "email": self.email,
                    "kaid-version": "kaid-plus",
                    "x-app-name-token": "kiln-aid",
                },
            ) as response:
                if response.status in (401, 403):
                    await response.read()
                    raise BartlettAuthError("KilnAid authentication expired")
                data = await _response_json(response)
        except TimeoutError as err:
            raise BartlettApiError("KilnAid request timed out") from err
        except ClientError as err:
            raise BartlettApiError("Unable to reach the KilnAid service") from err

        if response.status == 400 and "authentication" in str(data).lower():
            raise BartlettAuthError("KilnAid authentication expired")
        if response.status >= 400:
            raise BartlettApiError(
                f"KilnAid request failed with HTTP {response.status}"
            )
        return data


async def _response_json(response: ClientResponse) -> Any:
    """Decode JSON even when the service sends an incorrect content type."""
    try:
        return await response.json(content_type=None)
    except (ValueError, TypeError) as err:
        raise BartlettApiError("KilnAid returned a non-JSON response") from err


def parse_kiln(status: dict[str, Any], metadata: dict[str, Any]) -> KilnData:
    """Normalize compact KilnAid status and settings responses."""
    scale = str(
        status.get("temperatureScale") or metadata.get("temperatureScale") or "F"
    ).upper()
    temperatures = tuple(_number(status.get(f"t{zone}")) for zone in range(1, 4))
    zones = _integer(status.get("numZones") or metadata.get("numZones")) or 1
    if zones not in (1, 2, 3):
        zones = 1

    return KilnData(
        serial_number=str(
            metadata.get("serialNumber") or metadata.get("serial_number") or ""
        ),
        external_id=str(
            status.get("externalId")
            or metadata.get("externalId")
            or metadata.get("kiln_id")
            or ""
        ),
        name=str(metadata.get("name") or status.get("name") or "Bartlett Kiln"),
        firmware=_text(metadata.get("firmwareVersion")),
        temperature_scale=scale,
        number_of_zones=zones,
        zone_temperatures=temperatures,  # type: ignore[arg-type]
        set_point=_number(status.get("setPoint")),
        mode=str(status.get("mode") or "Not Connected"),
        program=_text(status.get("programName")),
        segment=_text(status.get("segment")),
        firing_minutes=_duration_minutes(status.get("firingTime")),
        hold_minutes=_duration_minutes(status.get("holdRemainingTime")),
        total_firings=_integer(
            metadata.get("numFirings") or status.get("currentFiringNumber")
        ),
        alarm=_text(status.get("alarmAbbreviation")),
        error_number=None,
        error_text=_text(status.get("errorText")),
        updated_at=_datetime(status.get("updatedAt") or metadata.get("updatedAt")),
    )


def _number(value: Any) -> float | None:
    if value in (None, "", "--", "---"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _duration_minutes(value: Any) -> int | None:
    if not isinstance(value, str) or ":" not in value:
        return None
    hours, minutes = value.split(":", 1)
    try:
        return int(hours) * 60 + int(minutes)
    except ValueError:
        return None


def _text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
