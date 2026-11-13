"""Config Flow: Einrichtung ohne Eingaben, nur eine Instanz (siehe manifest.json)."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN, TITLE


class CoffeeNordConfigFlow(ConfigFlow, domain=DOMAIN):
    """Einrichtung der CoffeeNørd-Integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Bestätigungsschritt, danach wird der Eintrag angelegt."""
        if user_input is not None:
            return self.async_create_entry(title=TITLE, data={})
        return self.async_show_form(step_id="user")
