"""Discover battery level sensors and keep dashboard alerts in sync."""

import asyncio
from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT, PERCENTAGE
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store

from .const import (
    CONF_CRITICAL_THRESHOLD,
    CONF_EXCLUDED_BATTERIES,
    CONF_THRESHOLD,
    CONF_TOPIC,
    DEFAULT_CRITICAL_THRESHOLD,
    DOMAIN,
    NOTIFICATIONS_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=1)


def async_battery_states(hass: HomeAssistant) -> dict[str, State]:
    """Return the percentage sensors eligible for monitoring."""
    return {
        state.entity_id: state
        for state in hass.states.async_all("sensor")
        if state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.BATTERY
        and state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    }


def battery_level(state: State) -> float | None:
    """Return a valid battery percentage, if available."""
    try:
        level = float(state.state)
    except ValueError:
        return None
    return level if 0 <= level <= 100 else None


class BatteryMonitor:
    """Reconcile active alerts with current battery readings."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        settings = {**entry.data, **entry.options}
        self.topic = settings[CONF_TOPIC]
        self.critical_threshold = settings.get(
            CONF_CRITICAL_THRESHOLD, DEFAULT_CRITICAL_THRESHOLD
        )
        self.alert_threshold = max(settings[CONF_THRESHOLD], self.critical_threshold)
        self.excluded_batteries = frozenset(settings.get(CONF_EXCLUDED_BATTERIES, []))
        self.store = Store[dict[str, dict[str, str | bool]]](hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.alerts: dict[str, dict[str, str | bool]] = {}
        self.lock = asyncio.Lock()
        self.stopping = False
        self.started = False
        self.service_errors: set[tuple[str, str]] = set()

    async def async_start(self, hass: HomeAssistant) -> None:
        """Scan after Home Assistant has finished starting."""
        self.started = True
        await self.async_scan()

    async def async_scan(self, _now=None) -> None:
        """Find batteries, update changed alerts and dismiss recovered ones."""
        if not self.started or self.stopping or self.lock.locked():
            return

        async with self.lock:
            registry = er.async_get(self.hass)
            batteries = async_battery_states(self.hass)
            previous = self.alerts.copy()
            for entity_id, state in batteries.items():
                if entity_id in self.excluded_batteries:
                    continue
                level = battery_level(state)
                if level is None or level > self.alert_threshold:
                    continue
                critical = level <= self.critical_threshold
                title = "Critical battery" if critical else "Low battery"
                percentage = str(level).removesuffix(".0")
                payload = {
                    "topic": self.topic,
                    "title": f"{title}: {state.name}",
                    "message": f"{state.name} battery is at {percentage}%.",
                    "severity": "error" if critical else "warning",
                    "show_timestamp": False,
                }
                if self.alerts.get(entity_id) == payload:
                    continue
                if await self.async_notify(
                    "create",
                    entity_id,
                    **payload,
                    icon="mdi:battery-low",
                    persistent=True,
                ):
                    self.alerts[entity_id] = payload

            for entity_id in list(self.alerts):
                if entity_id not in self.excluded_batteries:
                    if entity_id in batteries:
                        level = battery_level(batteries[entity_id])
                        if level is None or level <= self.alert_threshold:
                            continue
                    else:
                        state = self.hass.states.get(entity_id)
                        if state is None:
                            registered = registry.async_get(entity_id)
                            if registered is not None and not registered.disabled:
                                continue
                        elif state.state in ("unknown", "unavailable"):
                            continue
                if await self.async_notify("dismiss", entity_id):
                    del self.alerts[entity_id]

            if self.alerts != previous:
                await self.store.async_save(self.alerts)

    async def async_notify(self, service: str, entity_id: str, **data) -> bool:
        """Call the dashboard service and retry failures on a later scan."""
        error_key = (service, entity_id)
        try:
            await self.hass.services.async_call(
                NOTIFICATIONS_DOMAIN,
                service,
                {"key": f"{DOMAIN}:{entity_id}", **data},
                blocking=True,
            )
        except HomeAssistantError as err:
            if error_key not in self.service_errors:
                _LOGGER.warning("Could not %s battery alert for %s: %s", service, entity_id, err)
                self.service_errors.add(error_key)
            return False
        self.service_errors.discard(error_key)
        return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Restore alert tracking and start automatic discovery."""
    monitor = BatteryMonitor(hass, entry)
    monitor.alerts = await monitor.store.async_load() or {}
    entry.runtime_data = monitor
    entry.async_on_unload(async_at_started(hass, monitor.async_start))
    entry.async_on_unload(async_track_time_interval(hass, monitor.async_scan, SCAN_INTERVAL))
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply changes to the threshold or topic."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Let any current scan finish before releasing listeners."""
    monitor: BatteryMonitor = entry.runtime_data
    monitor.stopping = True
    async with monitor.lock:
        return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clear this monitor's alerts when its integration entry is removed."""
    monitor = BatteryMonitor(hass, entry)
    for entity_id in await monitor.store.async_load() or {}:
        await monitor.async_notify("dismiss", entity_id)
    await monitor.store.async_remove()
