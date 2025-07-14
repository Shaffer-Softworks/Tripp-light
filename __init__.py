from __future__ import annotations
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers import discovery, config_validation as cv
from .const import DOMAIN, DEFAULT_PORT

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional("name", default="SRCOOL AC"): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass: HomeAssistant, config: dict):
    conf = config[DOMAIN]
    hass.data[DOMAIN] = conf
    hass.async_create_task(
        discovery.async_load_platform(hass, "climate", DOMAIN, conf, config)
    )
    return True
