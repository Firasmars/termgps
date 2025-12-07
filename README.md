# TermGPS 🧭

**Terminal-based turn-by-turn navigation with a live Co-Pilot.**

A high-performance, cross-platform terminal GPS app featuring real-time tracking, a smart co-pilot, visual signal meters, and theme support.

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

- **🗣️ Live Co-Pilot** - Friendly commentary guiding your journey ("Turn coming up!", "Long stretch ahead").
- **🏃 Movement Detection** - Detects if you are moving or stationary with real-time speed (km/h).
- **📶 Signal Meter** - Visual bars (`▂▃▅▆▇`) showing GPS accuracy/strength.
- **🗺️ Radar Map** - Live radar with blue route line, red markers, and direction arrows.
- **🧭 Turn-by-Turn** - Step-by-step navigation list with auto-advance.
- **🎨 6 Programmer Themes** - Matrix, Dracula, Monokai, Nord, Gruvbox, Solarized.
- **🌍 Cross-Platform** - Works on macOS (Native GPS), Windows/Linux (IP Geolocation fallback).

---

## 📸 Interface

```
┌─ NEXT TURN ─┐ ┌────────────────────────────────────────────────┐
│             │ │              N                                 │
│   ⬅  250m   │ │              │                                 │
│             │ │     ·    ·   │   ·    ·                        │
│  Main Road  │ │    ·         │     ●●●▶                        │
│  Step 2/15  │ │   W──────────╋ ◉ YOU──━━━━━◆──E                │
├─ UPCOMING ──┤ │    ·         │         ·                       │
│ ⬅ Main Rd  │  │     ·    ·   │   ·    ·                        │
│ ➡ NH 44    │  │              S                                 │
├─ INFO ──────┤ │                                                │
│ SIG: ▂▃▅▆▇  │ │                MAP                             │
│ LOC: 13.08..│ │                                                │
│ 🔄 TRACKING │ └────────────────────────────────────────────────┘
├─ THEME ─────┤
│ [Dracula]   │
├─ CO-PILOT ──┤
│ STATUS: MOVING (45 km/h)
│ 💬 Prepare to turn left 
│    in a few seconds!
│ ETA: 12 min
└─────────────┘
```

---

## 🚀 Installation

### Quick Install

**Linux & macOS:**
```bash
git clone https://github.com/Aditya-Giri-4356/termgps.git
cd termgps
pip install -e .
termgps
```

**Windows:**
```powershell
git clone https://github.com/Aditya-Giri-4356/termgps.git
cd termgps
pip install -e .

# Run directly (Recommended if 'termgps' command not found):
python -m src.termgps.app
```

### Optional: Real GPS (macOS Only)
For native GPS support on macOS:
```bash
pip install pyobjc-framework-CoreLocation
```

---

## 🎮 Controls

| Key | Action |
|-----|--------|
| `r` | Refresh GPS location |
| `x` | Toggle **Live Tracking** |
| `d` | Search destination |
| `t` | Toggle **Theme Mode** (Use `⬅`/`➡` to switch) |
| `n` | Next turn (Manual override) |
| `p` | Previous turn |
| `c` | Clear current route |
| `q` | Quit application |

| Key | Theme Mode Active |
|-----|-------------------|
| `⬅` | Previous Theme |
| `➡` | Next Theme |

---

## 🎨 Themes

Press `t` to enter selection mode, then cycle through:

- **Matrix** (Green/Black)
- **Dracula** (Pink/Purple)
- **Monokai** (Yellow/Pink)
- **Nord** (Ice Blue)
- **Gruvbox** (Retro Brown)
- **Solarized** (Cyan/Beige)

---

## 🛠️ Project Structure

```
termgps/
├── src/
│   └── termgps/
│       ├── __init__.py
│       └── app.py          # Main application logic
├── pyproject.toml          # Project configuration
├── README.md               # Documentation
├── LICENSE                 # MIT License
└── .gitignore
```

---

## 🤝 Contributions

Contributions are welcome! If you have ideas for new features (like voice support, offline maps, etc.), please open an issue or pull request.

---

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

## 👨‍💻 Author

**Aditya Giri** - [@Aditya-Giri-4356](https://github.com/Aditya-Giri-4356)
