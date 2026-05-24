# Tripp Lite SRCOOL Custom Integration

![Tripp Lite SRCOOL Icon](icon.png)

> Control and monitor your Tripp Lite portable air conditioner from Home Assistant over Telnet.

**Supported hardware:** This integration works only with the [Tripp Lite SRCOOLNET SNMP Webcard Interface Module](https://tripplite.eaton.com/snmp-webcard-interface-module-remote-cooling-management-srcool12k-srxcool12k~SRCOOLNET) (Remote Cooling Management for SRCOOL12K / SRXCOOL12K). It does not support direct connection to SRCOOL units without this adapter.

---

## Features

- **Climate control**
  - Set target temperature (63 °F – 86 °F) via UI slider
  - Change fan speed (Low, Medium, High, Auto)
  - Toggle cooling on/off
- **Status monitoring**
  - Return Air Temperature
  - Water Status (Not Full / Full)
  - Quiet Mode (Enabled / Disabled)
  - Auto Fan Speed (On / Off)
- **Device info** exposed as entity attributes and sensors
  - Device Name, Vendor, Product, Protocol, Installation Date, State, Type, Port Mode, Port Name
- **Separate sensors** for each status field (water status, quiet mode, auto-fan, fan speed, etc.)
- **Config flow**–driven setup (no YAML) with reauthentication support

---

## Prerequisites

- Home Assistant Core **2024.9** or later (integration UI brand images require **2026.3** or later)
- [HACS](https://hacs.xyz/) (recommended) or manual install
- Tripp Lite **SRCOOLNET** SNMP Webcard Interface Module, with Telnet enabled
- Network reachability from your Home Assistant host to the adapter

---

## Installation

### HACS (recommended)

1. Open **HACS** → **Integrations** → **⋮** → **Custom repositories**.
2. Add repository URL `https://github.com/sickkick/Tripp-light` and category **Integration**.
3. Search for **Tripp Lite SRCOOL**, download, and restart Home Assistant.
4. Go to **Settings** → **Devices & services** → **Add integration** → **Tripp Lite SRCOOL**.

### Manual

Copy the integration folder into your Home Assistant `config` directory:

```bash
mkdir -p config/custom_components
git clone https://github.com/sickkick/Tripp-light.git /tmp/tripp-light
cp -R /tmp/tripp-light/custom_components/tripp_lite_srcool config/custom_components/
```

Restart Home Assistant, then add the integration from **Settings** → **Devices & services**.

---

## Configuration

During setup you will be prompted for:

| Field    | Description                          |
|----------|--------------------------------------|
| Host     | IP address or hostname of the SRCOOLNET adapter |
| Port     | Telnet port (default `23`)         |
| Username | Telnet username                      |
| Password | Telnet password                      |

If credentials change, use **Reconfigure** on the integration device page.

Brand icons for the integration picker and device UI are included under `custom_components/tripp_lite_srcool/brand/` (Home Assistant 2026.3+).

---

## HACS repository settings

If you fork this repo, set these on GitHub so HACS validation passes:

- **Description:** e.g. “Home Assistant custom integration for Tripp Lite SRCOOLNET Remote Cooling Management over Telnet.”
- **Topics:** `home-assistant`, `homeassistant`, `hacs`, `hacs-integration` (and optionally `tripp-lite`)

---

## Support

- [Documentation](https://github.com/sickkick/Tripp-light)
- [Issues](https://github.com/sickkick/Tripp-light/issues)
