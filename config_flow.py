import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import callback

from .const import DOMAIN, DEFAULT_PORT
from .srcool_telnet import SRCOOLClient

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tripp Lite SRCOOL."""

    VERSION = 1
    reauth_entry = None

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("Validating credentials for host %s", user_input[CONF_HOST])
            client = SRCOOLClient(
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )

            try:
                # Run blocking get_status in executor
                await self.hass.async_add_executor_job(client.get_status)
            except Exception as err:
                _LOGGER.warning("Login validation failed: %s", err)
                errors["base"] = "auth"
            else:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data) -> FlowResult:
        """Handle reauthentication when credentials are invalid."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> FlowResult:
        errors: dict[str, str] = {}
        assert self.reauth_entry is not None

        if user_input is not None:
            existing = self.reauth_entry.data
            new_data = {
                **existing,
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }

            client = SRCOOLClient(
                new_data[CONF_HOST],
                new_data.get(CONF_PORT, DEFAULT_PORT),
                new_data[CONF_USERNAME],
                new_data[CONF_PASSWORD],
            )

            try:
                await self.hass.async_add_executor_job(client.get_status)
            except Exception as err:
                _LOGGER.warning("Reauth failed: %s", err)
                errors["base"] = "auth"
            else:
                # Update and reload the entry
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry, data=new_data
                )
                await self.hass.config_entries.async_reload(
                    self.reauth_entry.entry_id
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    @callback
    def async_get_options_flow(self, config_entry: config_entries.ConfigEntry):
        """Return the options flow handler if needed."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow if you want to add options later."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Example options schema (you can expand this)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )

