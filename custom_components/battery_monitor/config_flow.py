"""Configure the notification topic and low-battery threshold."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import async_battery_states, battery_level
from .const import (
    CONF_CRITICAL_THRESHOLD,
    CONF_EXCLUDED_BATTERIES,
    CONF_THRESHOLD,
    CONF_TOPIC,
    DEFAULT_CRITICAL_THRESHOLD,
    DEFAULT_THRESHOLD,
    DOMAIN,
    NOTIFICATIONS_DOMAIN,
)


def _topic_options(hass):
    """Get topic names and IDs from Dashboard Notifications settings."""
    return [
        {"label": topic["name"], "value": topic["id"]}
        for entry in hass.config_entries.async_entries(NOTIFICATIONS_DOMAIN)
        for topic in entry.options.get("topics", [])
    ]


def _schema(topics, settings, batteries=None):
    """Build the form with the available topics and any discovered batteries."""
    topic_ids = {topic["value"] for topic in topics}
    topic = settings.get(CONF_TOPIC)
    topic_field = (
        vol.Required(CONF_TOPIC, default=topic)
        if topic in topic_ids
        else vol.Required(CONF_TOPIC)
    )
    fields = {
        topic_field: SelectSelector(
            SelectSelectorConfig(options=topics, mode=SelectSelectorMode.DROPDOWN)
        ),
        vol.Required(
            CONF_THRESHOLD, default=settings.get(CONF_THRESHOLD, DEFAULT_THRESHOLD)
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Required(
            CONF_CRITICAL_THRESHOLD,
            default=settings.get(CONF_CRITICAL_THRESHOLD, DEFAULT_CRITICAL_THRESHOLD),
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
    if batteries is not None:
        excluded = settings.get(CONF_EXCLUDED_BATTERIES, [])
        labels = {}
        for entity_id, state in batteries.items():
            level = battery_level(state)
            reading = f"{level:g}%" if level is not None else "Unavailable"
            labels[entity_id] = f"{state.name} · {reading} ({entity_id})"
        for entity_id in excluded:
            labels.setdefault(entity_id, f"{entity_id} (unavailable)")
        if labels:
            fields[vol.Required(CONF_EXCLUDED_BATTERIES, default=excluded)] = SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"label": label, "value": entity_id}
                        for entity_id, label in sorted(
                            labels.items(), key=lambda item: item[1].casefold()
                        )
                    ],
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            )
    return vol.Schema(fields)


def _errors(topics, user_input):
    """Validate the selected topic and the order of the thresholds."""
    if user_input is None:
        return {}
    errors = {}
    if user_input[CONF_TOPIC] not in {topic["value"] for topic in topics}:
        errors[CONF_TOPIC] = "topic_missing"
    if user_input[CONF_CRITICAL_THRESHOLD] > user_input[CONF_THRESHOLD]:
        errors[CONF_CRITICAL_THRESHOLD] = "critical_above_warning"
    return errors


class BatteryMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up one monitor for this Home Assistant instance."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        """Create the options flow."""
        return BatteryMonitorOptionsFlow()

    async def async_step_user(self, user_input=None):
        """Choose the topic and threshold."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        topics = _topic_options(self.hass)
        if not topics:
            return self.async_abort(reason="no_topics")
        errors = _errors(topics, user_input)
        if user_input is not None and not errors:
            return self.async_create_entry(title="Battery Monitor", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(topics, user_input or {}),
            errors=errors,
        )


class BatteryMonitorOptionsFlow(config_entries.OptionsFlow):
    """Change the notification topic, threshold, or exclusions."""

    async def async_step_init(self, user_input=None):
        """Show the current settings."""
        topics = _topic_options(self.hass)
        if not topics:
            return self.async_abort(reason="no_topics")
        errors = _errors(topics, user_input)
        if user_input is not None and not errors:
            return self.async_create_entry(title="", data=user_input)
        settings = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(
                topics, user_input or settings, async_battery_states(self.hass)
            ),
            errors=errors,
        )
