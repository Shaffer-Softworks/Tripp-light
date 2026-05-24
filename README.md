# Tripp Lite SRCOOL Custom Integration

![Tripp Lite SRCOOL Icon](icon.png)

> Control and monitor your Tripp Lite portable air conditioner from Home Assistant over Telnet.

**Supported hardware:** This integration works only with the [Tripp Lite SRCOOLNET SNMP Webcard Interface Module](https://tripplite.eaton.com/snmp-webcard-interface-module-remote-cooling-management-srcool12k-srxcool12k~SRCOOLNET) (Remote Cooling Management for SRCOOL12K / SRXCOOL12K). It does **not** support direct telnet to SRCOOL units without this adapter, and it does **not** support the SRCOOLNETLX adapter.

---

## Features

### Climate (`climate`)

- Set target temperature (**63 °F – 86 °F**)
- Fan speed: **Low**, **Medium**, **High**, **Auto**
- **Shut down** the unit from Home Assistant (see [Limitations](#limitations))

### Switch

- **Dehumidify Mode** — toggles the AC unit’s dehumidifying operating mode (separate from normal cooling). Use when you want the unit to focus on moisture removal rather than standard rack/room cooling.

### Binary sensor

- **Water Tank Full** — `on` when the condensate tank needs draining (useful for automations and notifications)

### Sensors

Status and identification values are exposed as individual sensors, including:

| Category | Examples |
|----------|----------|
| **Runtime** | Return air temperature, target temperature, operating mode, fan speed, auto fan, quiet mode, water status |
| **Identification** | Device name, vendor, product, serial number, location, region, asset tag, port name |
| **Preferences** | Units |
| **Card diagnostics** | OS, MAC address, driver/engine version, driver file status (hidden by default — see below) |

All entities attach to a single device in the Home Assistant device registry.

### Setup

- **Config flow** only (no YAML)
- **Reconfigure** / reauth when Telnet credentials change
- Brand images under `custom_components/tripp_lite_srcool/brand/` (Home Assistant **2026.3+**)

---

## Entities at a glance

| Entity | Type | Writable | Notes |
|--------|------|----------|-------|
| Tripp Lite SRCOOL | `climate` | Temp, fan, shutdown | COOL mode display only — cannot power on via telnet |
| Dehumidify Mode | `switch` | Yes | Independent of climate setpoint/fan |
| Water Tank Full | `binary_sensor` | No | Derived from water status text |
| Status sensors | `sensor` | No | One entity per telnet field |
| Card diagnostics | `sensor` (diagnostic) | No | Enable **Show diagnostic entities** on the device page |

---

## Dehumidify Mode

The **Dehumidify Mode** switch controls a separate operating mode on the AC unit (telnet **Devices → Preferences → Dehumidifying Status**):

- **Off** — normal cooling behavior
- **On** — unit runs in dehumidify mode

This is **not** the same as the climate card, fan speed, or water tank status:

- It does **not** turn cooling on or off by itself
- It is **not** a humidifier (the unit removes moisture when enabled)
- Running dehumidify for long periods may fill the condensate tank sooner — watch **Water Tank Full**

A read-only **Dehumidifying Status** sensor also exists but is hidden as a diagnostic entity (redundant with the switch).

---

## Limitations

The SRCOOLNET Telnet interface has important constraints:

| Topic | Behavior |
|-------|----------|
| **Power on** | **Not available** via telnet. Controls menu item `1` is **Reboot SNMP Card**, not start. Selecting **COOL** on the climate entity is ignored; only **OFF** (shutdown) is sent to the device. Power the unit on from the front panel or PowerAlert web UI. |
| **Polling** | One Telnet session, **60 s** interval. The adapter does not tolerate frequent or overlapping requests. |
| **Quiet mode** | Read-only — no telnet control path |
| **Diagnostics** | Card firmware/details refresh on startup and every **hour**; cached between refreshes |

---

## Device info

The device registry is populated from Telnet identification and diagnostics screens:

| Field | Source |
|-------|--------|
| Model | Product (e.g. SR(X)COOL12K) |
| Manufacturer | Vendor (Tripp Lite) |
| Firmware | PowerAlert **driver version** (card firmware) |
| Serial number | Unit serial from Identification screen |
| Configuration URL | `http://<host>` from integration settings |

The **Date Installed** sensor reflects when the card driver was installed — it is **not** the firmware version.

---

## Diagnostic entities

These sensors are categorized as **diagnostic** and hidden by default:

- Card: OS, agent type, MAC address, card serial, driver/engine version, driver file status
- Dehumidifying Status (raw text; use the **Dehumidify Mode** switch instead)

To show them: open the device page → **Device info** → enable **Show diagnostic entities**.

---

## Prerequisites

- Home Assistant Core **2024.9** or later (brand images require **2026.3+**)
- [HACS](https://hacs.xyz/) (recommended) or manual install
- Tripp Lite **SRCOOLNET** with Telnet enabled
- Network reachability from Home Assistant to the adapter

---

## Installation

### HACS (recommended)

1. Open **HACS** → **Integrations** → **⋮** → **Custom repositories**.
2. Add repository URL `https://github.com/Shaffer-Softworks/Tripp-light` and category **Integration**.
3. Search for **Tripp Lite SRCOOL**, download, and restart Home Assistant.
4. Go to **Settings** → **Devices & services** → **Add integration** → **Tripp Lite SRCOOL**.

### Manual

```bash
mkdir -p config/custom_components
git clone https://github.com/Shaffer-Softworks/Tripp-light.git /tmp/tripp-light
cp -R /tmp/tripp-light/custom_components/tripp_lite_srcool config/custom_components/
```

Restart Home Assistant, then add the integration from **Settings** → **Devices & services**.

---

## Configuration

| Field | Description |
|-------|-------------|
| Host | IP address or hostname of the SRCOOLNET adapter |
| Port | Telnet port (default `23`) |
| Username | Telnet username (often `localadmin`) |
| Password | Telnet password |

Use **Reconfigure** on the integration entry if credentials change.

---

## HACS repository settings (forks)

Set on GitHub so HACS validation passes:

- **Description:** e.g. “Home Assistant custom integration for Tripp Lite SRCOOLNET Remote Cooling Management over Telnet.”
- **Topics:** `home-assistant`, `homeassistant`, `hacs`, `hacs-integration`

---

## Support

- [Documentation](https://github.com/Shaffer-Softworks/Tripp-light)
- [Issues](https://github.com/Shaffer-Softworks/Tripp-light/issues)
