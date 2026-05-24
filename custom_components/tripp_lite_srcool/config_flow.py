"""Config flow for Tripp Lite SRCOOL integration."""
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN
from .srcool_telnet import SRCOOLClient  # or srcool_telnet3 if you renamed it

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Required("port", default=23): int,
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class TrippLiteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tripp Lite SRCOOL."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the user input step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client = SRCOOLClient(
                user_input["host"],
                user_input["port"],
                user_input["username"],
                user_input["password"],
            )
            # validate connectivity
            try:
                await self.hass.async_add_executor_job(client.get_status)
            except ConnectionError:
                _LOGGER.exception("SRCOOL cannot_connect")
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"SRCOOL {user_input['host']}", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Provide an options flow for this integration."""
        return TrippLiteOptionsFlowHandler(config_entry)


class TrippLiteOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for Tripp Lite SRCOOL."""

    def __init__(self, config_entry):
        """Initialize with the config entry."""
        # Store for reading existing values
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Kick off the options flow."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Allow the user to change host/port/credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Return the updated options
            return self.async_create_entry(title="", data=user_input)

        # Prepopulate form with either existing options or original data
        current = {}
        current.update(self._config_entry.data or {})
        current.update(self._config_entry.options or {})

        schema = vol.Schema(
            {
                vol.Required("host", default=current.get("host")): str,
                vol.Required("port", default=current.get("port", 23)): int,
                vol.Required("username", default=current.get("username")): str,
                vol.Required("password", default=current.get("password")): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
