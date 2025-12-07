# TermGPS 🧭

Cross-platform terminal GPS navigation with turn-by-turn directions.

**Works on:** Windows, macOS, Linux

## Features

- 📍 **Location Detection** - GPS or IP-based (works everywhere)
- 🗺️ **Turn-by-Turn Routing** - Real road directions via OSRM
- 🧭 **Radar Display** - Visual compass with route overlay
- 🔵 **Blue Route Line** - Clear path visualization
- 🇮🇳 **India Optimized** - Built-in Indian cities

## Installation

```bash
pip install textual rich requests

# Clone and run
git clone https://github.com/Aditya-Giri-4356/termgps.git
cd termgps
python -m src.termgps.app
```

### Optional: Platform GPS

```bash
# macOS (for real GPS)
pip install pyobjc-framework-CoreLocation

# Windows (for real GPS)
pip install winrt-Windows.Devices.Geolocation

# Linux (requires gpsd running)
pip install gps
```

## Usage

```bash
python -m src.termgps.app
```

### Controls

| Key | Action |
|-----|--------|
| `r` | Get location |
| `d` | Search destination |
| `n/p` | Next/Prev direction |
| `c` | Clear route |
| `q` | Quit |
| Mouse | Drag to pan |

## How It Works

1. Press `r` to get your location
2. Press `d` and search for a destination
3. Follow the blue route and directions

## Requirements

- Python 3.9+
- textual, rich, requests (auto-installed)
- Internet connection (for routing)

## License

MIT - Aditya Giri
