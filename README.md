# TermGPS 🧭

A terminal-based GPS navigation app with radar display for macOS.

![Python](https://img.shields.io/badge/python-3.9+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-macOS-lightgrey)

## Features

- 📍 **Real GPS Location** - Uses macOS Location Services for accurate positioning
- 🎯 **Destination Search** - Search any place with auto-suggestions
- 🧭 **Radar Display** - Visual compass with direction arrow
- 📏 **Distance Tracking** - Real-time distance to destination
- 🔔 **Arrival Detection** - Notifies when you reach your destination
- 🖱️ **Mouse Support** - Drag to pan the radar view
- ⚡ **Static Display** - No automatic movement, updates only on user action

## Screenshot

```
                        N
                        │
                   ·  · │ ·  ·
                  ·     │     ·
                 ·      │      ·
         W──────────────╋◉YOU───●●●▶ Taj Mahal (150km)
                 ·      │      ·
                  ·     │     ·
                   ·  · │ ·  ·
                        │
                        S

┌─ NAVIGATION ─────────────────────────────────────────┐
│ 📍 GPS: Excellent (±5m)                              │
│ YOUR LOCATION: 28.613901, 77.209023                  │
│ DESTINATION: Taj Mahal                               │
│ DISTANCE: 150.25 km  |  DIRECTION: 85° (E)           │
└───────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.9 or higher
- macOS (for real GPS via Location Services)

### Install from source

```bash
# Clone the repository
git clone https://github.com/Aditya-Giri-4356/termgps.git
cd termgps

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .

# Install GPS support (recommended)
pip install pyobjc-framework-CoreLocation
```

## Usage

```bash
# Run the app
python -m termgps.app

# Or if installed
termgps
```

### Controls

| Key | Action |
|-----|--------|
| `r` | **Refresh GPS** - Get your current location |
| `d` | **Search** - Open destination search |
| `c` | **Clear** - Clear destination |
| `↑` `↓` | Select suggestion |
| `Enter` | Confirm selection |
| `Escape` | Cancel search |
| `q` | Quit |

| Mouse | Action |
|-------|--------|
| Drag | Pan the radar view |

### Location Permission

When you first run the app and press `r` for GPS:

1. macOS will show a **location permission popup**
2. Click **"Allow"** to grant access
3. Your real GPS coordinates will be displayed

If you denied permission:
1. Open **System Preferences** → **Security & Privacy** → **Privacy** → **Location Services**
2. Find **Terminal** or **Python** and enable it
3. Restart the app

### GPS Accuracy Levels

| Status | Accuracy | Description |
|--------|----------|-------------|
| Excellent | ≤10m | GPS hardware (outdoor) |
| Good | ≤50m | WiFi positioning |
| Fair | ≤100m | Cell tower positioning |
| IP Location | ~10km | Fallback (city-level) |

## How It Works

1. **Your Position (╋)**: The crosshair at center represents your location
2. **Direction Arrow (●●●▶)**: Points toward your destination
3. **Range Circles**: Visual reference for distance scale
4. **Compass (N/S/E/W)**: Cardinal directions

The display is **completely static** - it only updates when you:
- Press `r` to refresh GPS
- Set a new destination
- Clear the destination

## API Usage

The app uses **OpenStreetMap Nominatim** for destination search (free, no API key required).

For Google Maps integration (optional):
```bash
export GOOGLE_MAPS_API_KEY="your-api-key"
termgps
```

## Project Structure

```
termgps/
├── src/
│   └── termgps/
│       ├── __init__.py
│       └── app.py          # Main application
├── pyproject.toml          # Package configuration
├── README.md
├── LICENSE
└── .gitignore
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Format code
black src/
isort src/

# Run tests
pytest
```

## Requirements

- **textual** - TUI framework
- **rich** - Terminal formatting
- **requests** - HTTP client
- **geocoder** - IP geolocation fallback
- **pyobjc-framework-CoreLocation** - macOS GPS (optional but recommended)

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

Aditya Giri ([@Aditya-Giri-4356](https://github.com/Aditya-Giri-4356))

## Acknowledgments

- Inspired by [rsadsb/adsb_deku](https://github.com/rsadsb/adsb_deku) radar display
- Built with [Textual](https://textual.textualize.io/)
- Location search powered by [OpenStreetMap Nominatim](https://nominatim.openstreetmap.org/)
