# Display Reference

Each display driver receives pre-formatted content from `OutputManager` and renders it to pixels or text. This
document covers wiring, config fields, and notes for each supported display type.

---

## Common Config Fields

All display entries share these fields regardless of type:

| Field            | Type    | Required | Description                                                                      |
|------------------|---------|----------|----------------------------------------------------------------------------------|
| `type`           | string  | Yes      | Display type identifier (e.g. `ssd1306_i2c`)                                    |
| `enabled`        | bool    | Yes      | Whether the display is active                                                    |
| `show_startup`   | bool    | Yes      | Opts the display into bootstrap/status messages                                  |
| `system_screen`  | bool    | Yes      | Dedicates the display to the persistent system-status layout (implies `show_startup: true`) |
| `refresh_period` | int     | No       | Minimum seconds between renders (default: no throttle)                           |

> `system_screen: true` disables telemetry rendering and instead shows a fixed version header on row 1 with a
> rolling 2-message log beneath it. Intended for a small secondary OLED when a second display is connected.

---

## SSD1306 I2C — OLED Display

**Protocol:** I2C | **Resolution:** 128×32 (default)

### Wiring

| Display Pin | Pi Connection | Notes                  |
|-------------|---------------|------------------------|
| VCC         | 3.3V          | Power                  |
| GND         | GND           | Ground                 |
| SDA         | GPIO2 (SDA)   | I2C data               |
| SCL         | GPIO3 (SCL)   | I2C clock              |

Enable I2C via `raspi-config`. Verify the display is detected with `i2cdetect -y 1`.

### Config example

```json
{
  "type": "ssd1306_i2c",
  "enabled": true,
  "show_startup": true,
  "system_screen": true,
  "refresh_period": 5,
  "width": 128,
  "height": 32,
  "address": 60
}
```

### Driver-specific fields

| Field     | Type | Required | Description                                           |
|-----------|------|----------|-------------------------------------------------------|
| `width`   | int  | No       | Display width in pixels (default: 128)                |
| `height`  | int  | No       | Display height in pixels (default: 32)                |
| `address` | int  | No       | I2C address as decimal integer (default: 60 / 0x3C)  |

### Render behaviour

**Normal mode** (`system_screen: false`): renders up to 3 content lines in a column layout on the upper portion
of the display, with the telemetry timestamp on the lower row.

**System-screen mode** (`system_screen: true`): `render()` is a no-op. Updates arrive via `render_startup()`,
which maintains a 3-row layout — fixed version header on row 1, second-most-recent message on row 2, most recent
message on row 3.

---

## Waveshare 1.47" LCD — ST7789

**Protocol:** SPI (4-wire) | **Resolution:** 172×320

### Wiring

| Display Pin | Pi Connection       | Notes                         |
|-------------|---------------------|-------------------------------|
| VCC         | 3.3V                | Power                         |
| GND         | GND                 | Ground                        |
| DIN (MOSI)  | GPIO10 (SPI0 MOSI)  | SPI data                      |
| SCLK        | GPIO11 (SPI0 SCLK)  | SPI clock                     |
| CS          | GPIO8 (SPI0 CE0)    | Chip select (when device=0)   |
| DC          | Configurable GPIO   | Data/command select           |
| RST         | Configurable GPIO   | Hardware reset                |
| BL          | Configurable GPIO   | Backlight enable              |

Enable SPI via `raspi-config`.

### Config example

```json
{
  "type": "waveshare_147_st7789",
  "enabled": true,
  "show_startup": false,
  "system_screen": false,
  "refresh_period": 5,
  "spi": {
    "bus": 0,
    "device": 0,
    "mode": 0,
    "max_speed_hz": 40000000
  },
  "pins": {
    "dc": 25,
    "reset": 27,
    "backlight": 18
  }
}
```

### Driver-specific fields

| Field               | Type | Required | Description                                         |
|---------------------|------|----------|-----------------------------------------------------|
| `spi.bus`           | int  | Yes      | SPI bus number                                      |
| `spi.device`        | int  | Yes      | SPI device (chip select) number                     |
| `spi.mode`          | int  | No       | SPI mode (default: 0)                               |
| `spi.max_speed_hz`  | int  | No       | SPI clock speed in Hz (default: 10000000)           |
| `pins.dc`           | int  | Yes      | BCM GPIO pin for data/command select                |
| `pins.reset`        | int  | Yes      | BCM GPIO pin for hardware reset                     |
| `pins.backlight`    | int  | Yes      | BCM GPIO pin for backlight enable                   |

### Render behaviour

Content lines are rendered in white on a black background, evenly spaced within a 10% vertical margin on each
side. Text is centred horizontally. Both `render()` and `render_startup()` use the same framebuffer-flush
approach via SPI.

---

## Logging — Development Display

**Protocol:** None (software only)

No wiring required. Outputs pre-formatted content lines to the service log at `INFO` level instead of rendering
to hardware. Useful for development and testing on a machine without attached displays.

### Config example

```json
{
  "type": "logging",
  "enabled": true,
  "show_startup": false,
  "system_screen": false,
  "refresh_period": 5
}
```

No driver-specific fields beyond the common set.

---

## Adding a new display

1. Implement `BaseDisplay` from `outputs/display/base.py` — provide `render()`, `render_startup()`, and `close()`
2. Register the new type in `outputs/display/factory.py`
3. Add an entry to `config.json` following the schema above