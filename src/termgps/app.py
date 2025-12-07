#!/usr/bin/env python3
"""
TermGPS - Active Turn-by-Turn Navigation

Features:
- LIVE GPS tracking with auto-refresh
- Distance to next turn
- Auto-advance through navigation steps
- Large, elaborate display
"""

import os
import math
import platform
import time
from typing import Optional, List, Dict, Tuple

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding
from textual import events
from rich.text import Text
from rich.style import Style
from rich.panel import Panel

_requests = None
def _req():
    global _requests
    if not _requests: import requests; _requests = requests
    return _requests


# =============================================================================
# GPS
# =============================================================================

def get_gps() -> Tuple[Optional[float], Optional[float], str]:
    """Get location - tries platform GPS then IP."""
    # macOS
    if platform.system() == "Darwin":
        try:
            import CoreLocation
            from Foundation import NSRunLoop, NSDate
            mgr = CoreLocation.CLLocationManager.alloc().init()
            mgr.requestWhenInUseAuthorization()
            mgr.setDesiredAccuracy_(CoreLocation.kCLLocationAccuracyBest)
            mgr.startUpdatingLocation()
            for _ in range(20):
                NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
                loc = mgr.location()
                if loc and loc.horizontalAccuracy() > 0:
                    mgr.stopUpdatingLocation()
                    return loc.coordinate().latitude, loc.coordinate().longitude, f"±{loc.horizontalAccuracy():.0f}m"
            mgr.stopUpdatingLocation()
        except: pass
    
    # IP fallback
    try:
        r = _req().get("http://ip-api.com/json/", timeout=4)
        if r.ok:
            d = r.json()
            return d.get("lat"), d.get("lon"), "~10km"
    except: pass
    return None, None, "N/A"


# =============================================================================
# ROUTING
# =============================================================================

def get_route(lat1, lon1, lat2, lon2) -> Optional[Dict]:
    """Get detailed route with turn-by-turn."""
    try:
        r = _req().get(
            f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}",
            params={"overview": "full", "geometries": "geojson", "steps": "true"},
            timeout=10
        )
        d = r.json()
        if d.get("code") != "Ok": return None
        
        route = d["routes"][0]
        steps = []
        for leg in route.get("legs", []):
            for s in leg.get("steps", []):
                m = s.get("maneuver", {})
                steps.append({
                    "name": s.get("name") or "Road",
                    "instruction": s.get("instruction", "Continue"),
                    "type": m.get("type", ""),
                    "modifier": m.get("modifier", ""),
                    "dist": s.get("distance", 0),  # meters
                    "time": s.get("duration", 0),   # seconds
                    "loc": m.get("location", [0, 0])  # [lon, lat]
                })
        
        return {
            "dist": route["distance"],  # meters
            "time": route["duration"],   # seconds
            "pts": route["geometry"]["coordinates"],
            "steps": steps
        }
    except: return None


def search_places(q: str, lat=None, lon=None) -> List[Dict]:
    if len(q) < 2: return []
    try:
        params = {"q": f"{q}, India" if 'india' not in q.lower() else q, 
                  "format": "json", "limit": 6, "countrycodes": "in"}
        if lat: params["viewbox"] = f"{lon-2},{lat+2},{lon+2},{lat-2}"
        r = _req().get("https://nominatim.openstreetmap.org/search", 
                       params=params, headers={"User-Agent": "TermGPS"}, timeout=5)
        return [{"name": x["display_name"][:50], "lat": float(x["lat"]), "lon": float(x["lon"])} for x in r.json()]
    except: return []


# Quick places
PLACES = [
    {"name": "Chennai", "lat": 13.0827, "lon": 80.2707},
    {"name": "Coimbatore", "lat": 11.0168, "lon": 76.9558},
    {"name": "Madurai", "lat": 9.9252, "lon": 78.1198},
    {"name": "Bangalore", "lat": 12.9716, "lon": 77.5946},
    {"name": "Mumbai", "lat": 19.076, "lon": 72.8777},
    {"name": "Delhi", "lat": 28.6139, "lon": 77.209},
]


# =============================================================================
# MATH
# =============================================================================

def dist_m(lat1, lon1, lat2, lon2) -> float:
    """Distance in meters."""
    R = 6371000
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def bearing(lat1, lon1, lat2, lon2) -> float:
    dlon = math.radians(lon2-lon1)
    x = math.sin(dlon)*math.cos(math.radians(lat2))
    y = math.cos(math.radians(lat1))*math.sin(math.radians(lat2)) - math.sin(math.radians(lat1))*math.cos(math.radians(lat2))*math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360

def bearing_dir(b: float) -> str:
    dirs = ["N","NE","E","SE","S","SW","W","NW"]
    return dirs[int((b + 22.5) / 45) % 8]

def fmt_dist(m: float) -> str:
    if m >= 1000: return f"{m/1000:.1f} km"
    return f"{int(m)} m"

def fmt_time(s: float) -> str:
    h, m = int(s // 3600), int((s % 3600) // 60)
    if h > 0: return f"{h}h {m}m"
    return f"{m} min"


# =============================================================================
# TURN ICONS
# =============================================================================

def turn_icon(mod: str, typ: str) -> str:
    if typ == "arrive": return "🏁"
    if typ == "depart": return "🚗"
    if "left" in mod: return "⬅️ "
    if "right" in mod: return "➡️ "
    if "straight" in mod: return "⬆️ "
    if typ == "roundabout": return "🔄"
    return "➡️ "

def turn_arrow(mod: str) -> str:
    if "left" in mod: return "◀──"
    if "right" in mod: return "──▶"
    if "straight" in mod: return " ▲ "
    return "───"


# =============================================================================
# WIDGETS
# =============================================================================

class BigDirection(Static):
    """Large current direction display."""
    
    def __init__(self):
        super().__init__()
        self.icon = "🧭"
        self.road = "Press 'd' to set destination"
        self.dist_to_turn = 0
        self.instruction = ""
    
    def render(self) -> Text:
        txt = Text()
        
        # Large icon
        txt.append("\n")
        txt.append(f"     {self.icon}\n", style=Style(color="yellow", bold=True))
        txt.append("\n")
        
        # Distance to turn
        if self.dist_to_turn > 0:
            d = fmt_dist(self.dist_to_turn)
            txt.append(f"     {d}\n", style=Style(color="white", bold=True))
        else:
            txt.append("     ---\n", style=Style(color="grey50"))
        
        txt.append("\n")
        
        # Road name
        txt.append(f"  {self.road[:25]}\n", style=Style(color="cyan"))
        
        # Instruction
        if self.instruction:
            txt.append(f"  {self.instruction[:30]}\n", style=Style(color="green"))
        
        return txt


class NextTurns(Static):
    """Upcoming turns list."""
    
    def __init__(self):
        super().__init__()
        self.steps = []
        self.current = 0
    
    def render(self) -> Text:
        txt = Text()
        txt.append("─── UPCOMING TURNS ───\n", style=Style(color="cyan", bold=True))
        
        if not self.steps:
            txt.append(" No route active\n", style=Style(color="grey50"))
            return txt
        
        # Show 5 upcoming turns
        for i in range(self.current, min(self.current + 5, len(self.steps))):
            s = self.steps[i]
            icon = turn_icon(s["modifier"], s["type"])
            dist = fmt_dist(s["dist"])
            name = s["name"][:20]
            
            if i == self.current:
                txt.append(f" {icon} ", style=Style(color="yellow", bold=True))
                txt.append(f"{name:<20} ", style=Style(color="white", bold=True))
                txt.append(f"{dist:>8}\n", style=Style(color="green", bold=True))
            else:
                txt.append(f" {icon} ", style=Style(color="grey70"))
                txt.append(f"{name:<20} ", style=Style(color="grey70"))
                txt.append(f"{dist:>8}\n", style=Style(color="grey50"))
        
        return txt


class RouteInfo(Static):
    """Route overview."""
    
    def __init__(self):
        super().__init__()
        self.dest = None
        self.total_dist = 0
        self.total_time = 0
        self.remaining_dist = 0
        self.remaining_time = 0
    
    def render(self) -> Text:
        txt = Text()
        txt.append("─── ROUTE INFO ───\n", style=Style(color="green", bold=True))
        
        if self.dest:
            txt.append(f" TO: {self.dest[:25]}\n", style=Style(color="white"))
            txt.append(f" Remaining: {fmt_dist(self.remaining_dist)}\n", style=Style(color="cyan"))
            txt.append(f" ETA: {fmt_time(self.remaining_time)}\n", style=Style(color="cyan"))
        else:
            txt.append(" No destination\n", style=Style(color="grey50"))
        
        return txt


class GPSStatus(Static):
    """GPS status display."""
    
    def __init__(self):
        super().__init__()
        self.lat = None
        self.lon = None
        self.accuracy = "N/A"
        self.tracking = False
        self.last_update = None
    
    def render(self) -> Text:
        txt = Text()
        txt.append("─── GPS ───\n", style=Style(color="magenta", bold=True))
        
        if self.lat:
            txt.append(f" {self.lat:.5f}, {self.lon:.5f}\n", style=Style(color="white"))
            txt.append(f" Accuracy: {self.accuracy}\n", style=Style(color="cyan"))
        else:
            txt.append(" No location\n", style=Style(color="yellow"))
        
        if self.tracking:
            txt.append(" 🔄 TRACKING\n", style=Style(color="green", bold=True))
        else:
            txt.append(" Press 't' to track\n", style=Style(color="grey50"))
        
        return txt


class Radar(Static):
    """Map radar display."""
    can_focus = True
    
    def __init__(self):
        super().__init__()
        self.lat = self.lon = None
        self.route = []
        self.dest = None
        self.current_step = 0
        self.steps = []
        self.px = self.py = 0
        self._drag = False
        self._dx = self._dy = 0
        self._w, self._h = 50, 15
    
    def on_resize(self, e): self._w, self._h = e.size.width, e.size.height
    def on_mouse_down(self, e):
        if e.button == 1: self._drag, self._dx, self._dy = True, e.x, e.y; self.capture_mouse()
    def on_mouse_up(self, e): self._drag = False; self.release_mouse()
    def on_mouse_move(self, e):
        if self._drag:
            self.px += e.x - self._dx; self.py += e.y - self._dy
            self._dx, self._dy = e.x, e.y; self.refresh()
    
    def render(self) -> Text:
        w, h = self._w, self._h
        buf = [[' ']*w for _ in range(h)]
        col = [['green']*w for _ in range(h)]
        
        cx, cy = max(3,min(w-3,w//2+self.px)), max(2,min(h-2,h//2+self.py))
        
        # Route line
        if self.route and self.lat:
            scale = 600
            for i, (lo, la) in enumerate(self.route):
                x = cx + int((lo - self.lon) * scale)
                y = cy - int((la - self.lat) * scale * 2)
                if 0 <= x < w and 0 <= y < h:
                    if i == 0:
                        buf[y][x] = '●'; col[y][x] = 'cyan'
                    elif i == len(self.route) - 1:
                        buf[y][x] = '◆'; col[y][x] = 'red'
                    else:
                        buf[y][x] = '━'; col[y][x] = 'blue'
        
        # Crosshairs
        for x in range(w):
            if 0 <= cy < h and buf[cy][x] == ' ': buf[cy][x] = '─'
        for y in range(h):
            if 0 <= cx < w and buf[y][cx] == ' ': buf[y][cx] = '│'
        if 0 <= cx < w and 0 <= cy < h:
            buf[cy][cx] = '╋'; col[cy][cx] = 'yellow'
        
        # Compass
        if 0 <= cx < w:
            if cy > 0: buf[0][cx] = 'N'; col[0][cx] = 'white'
            if cy < h-1: buf[h-1][cx] = 'S'; col[h-1][cx] = 'white'
        if 0 <= cy < h:
            buf[cy][0] = 'W'; col[cy][0] = 'white'
            buf[cy][w-1] = 'E'; col[cy][w-1] = 'white'
        
        # YOU marker
        if self.lat:
            for i, c in enumerate("◉YOU"):
                if 0 <= cx+2+i < w: buf[cy][cx+2+i] = c; col[cy][cx+2+i] = 'yellow'
        
        # Next turn marker
        if self.steps and self.current_step < len(self.steps) and self.lat:
            step = self.steps[self.current_step]
            lo, la = step["loc"]
            scale = 600
            tx = cx + int((lo - self.lon) * scale)
            ty = cy - int((la - self.lat) * scale * 2)
            if 0 <= tx < w and 0 <= ty < h:
                buf[ty][tx] = '▼'; col[ty][tx] = 'red'
        
        txt = Text()
        for y in range(h):
            for x in range(w):
                txt.append(buf[y][x], style=Style(color=col[y][x]))
            txt.append('\n')
        return txt


class Suggestions(Static):
    def __init__(self): super().__init__(); self.items = []; self.sel = 0
    def render(self) -> Text:
        txt = Text()
        for i, item in enumerate(self.items[:6]):
            txt.append(f"{'▶' if i == self.sel else ' '} {item['name'][:45]}\n", 
                       style="green bold" if i == self.sel else "white")
        return txt


# =============================================================================
# APP
# =============================================================================

class TermGPS(App):
    CSS = """
    Screen { background: #000; }
    
    #left-panel { width: 35; }
    #right-panel { width: 1fr; }
    
    #big-dir { height: 12; border: heavy yellow; }
    #next-turns { height: 10; border: solid cyan; }
    #route-info { height: 6; border: solid green; }
    #gps-status { height: 7; border: solid magenta; }
    
    #radar { height: 100%; border: heavy blue; }
    
    #search { display: none; border: double yellow; padding: 1; }
    #search.show { display: block; }
    
    Input { background: #111; color: #0f0; }
    Static { color: #0f0; }
    Footer { background: #010; }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "search", "Search"),
        Binding("r", "gps_once", "GPS"),
        Binding("t", "toggle_track", "Track"),
        Binding("c", "clear", "Clear"),
        Binding("n", "next", "Next"),
        Binding("p", "prev", "Prev"),
        Binding("escape", "cancel", show=False),
        Binding("enter", "confirm", show=False),
        Binding("up", "up", show=False),
        Binding("down", "down", show=False),
    ]
    
    def __init__(self):
        super().__init__()
        self.lat = self.lon = None
        self.route = None
        self.dest_name = None
        self.current_step = 0
        self.tracking = False
        self._search_active = False
        self._last_q = ""
        self._timer = None
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        self.big_dir = BigDirection()
        self.next_turns = NextTurns()
        self.route_info = RouteInfo()
        self.gps_status = GPSStatus()
        self.radar = Radar()
        self.suggestions = Suggestions()
        self.search_input = Input(placeholder="Search destination...")
        
        with Container(id="search"):
            yield self.search_input
            yield self.suggestions
        
        with Horizontal():
            with Vertical(id="left-panel"):
                yield self.big_dir
                yield self.next_turns
                yield self.route_info
                yield self.gps_status
            
            with Container(id="right-panel"):
                yield self.radar
        
        yield Footer()
    
    def on_mount(self):
        self._update_display()
        self.notify("Press 'r' for GPS, 'd' to search, 't' for tracking")
    
    def _update_display(self):
        """Update all displays."""
        # GPS status
        self.gps_status.lat = self.lat
        self.gps_status.lon = self.lon
        self.gps_status.tracking = self.tracking
        
        # Radar
        self.radar.lat = self.lat
        self.radar.lon = self.lon
        self.radar.route = self.route["pts"] if self.route else []
        self.radar.steps = self.route["steps"] if self.route else []
        self.radar.current_step = self.current_step
        
        # Route info
        if self.route:
            self.route_info.dest = self.dest_name
            self.route_info.total_dist = self.route["dist"]
            self.route_info.total_time = self.route["time"]
            
            # Calculate remaining
            remaining_dist = sum(s["dist"] for s in self.route["steps"][self.current_step:])
            remaining_time = sum(s["time"] for s in self.route["steps"][self.current_step:])
            self.route_info.remaining_dist = remaining_dist
            self.route_info.remaining_time = remaining_time
        else:
            self.route_info.dest = None
        
        # Next turns
        self.next_turns.steps = self.route["steps"] if self.route else []
        self.next_turns.current = self.current_step
        
        # Big direction
        if self.route and self.current_step < len(self.route["steps"]):
            step = self.route["steps"][self.current_step]
            self.big_dir.icon = turn_icon(step["modifier"], step["type"])
            self.big_dir.road = step["name"]
            self.big_dir.instruction = step.get("instruction", "")
            
            # Calculate distance to next turn
            if self.lat:
                step_loc = step["loc"]
                self.big_dir.dist_to_turn = dist_m(self.lat, self.lon, step_loc[1], step_loc[0])
            else:
                self.big_dir.dist_to_turn = step["dist"]
        else:
            self.big_dir.icon = "🧭"
            self.big_dir.road = "No active navigation"
            self.big_dir.instruction = ""
            self.big_dir.dist_to_turn = 0
        
        # Refresh all
        self.big_dir.refresh()
        self.next_turns.refresh()
        self.route_info.refresh()
        self.gps_status.refresh()
        self.radar.refresh()
    
    def _check_next_turn(self):
        """Check if we should advance to next turn."""
        if not self.route or not self.lat:
            return
        
        if self.current_step >= len(self.route["steps"]):
            return
        
        step = self.route["steps"][self.current_step]
        step_loc = step["loc"]
        dist = dist_m(self.lat, self.lon, step_loc[1], step_loc[0])
        
        # If within 50m of turn, advance
        if dist < 50:
            if self.current_step < len(self.route["steps"]) - 1:
                self.current_step += 1
                self.notify(f"🔔 {self.route['steps'][self.current_step]['name']}")
            else:
                self.notify("🏁 You have arrived!")
                self.tracking = False
                if self._timer:
                    self._timer.stop()
    
    def action_gps_once(self):
        """Get GPS once."""
        self.notify("📍 Getting location...")
        self.lat, self.lon, acc = get_gps()
        self.gps_status.accuracy = acc
        self._update_display()
        self._check_next_turn()
        
        if self.lat:
            self.notify(f"Location: {self.lat:.4f}, {self.lon:.4f}")
    
    def action_toggle_track(self):
        """Toggle GPS tracking."""
        self.tracking = not self.tracking
        
        if self.tracking:
            self.notify("🔄 GPS tracking ON (updates every 5s)")
            self._timer = self.set_interval(5, self._track_update)
        else:
            self.notify("⏹️ GPS tracking OFF")
            if self._timer:
                self._timer.stop()
                self._timer = None
        
        self._update_display()
    
    def _track_update(self):
        """Periodic GPS update."""
        if not self.tracking:
            return
        
        self.lat, self.lon, acc = get_gps()
        self.gps_status.accuracy = acc
        self._check_next_turn()
        self._update_display()
    
    def action_search(self):
        self._search_active = True
        self.query_one("#search").add_class("show")
        self.search_input.value = ""
        self.suggestions.items = []
        self.search_input.focus()
    
    def action_cancel(self):
        self._search_active = False
        self.query_one("#search").remove_class("show")
    
    def action_confirm(self):
        if self._search_active and self.suggestions.items:
            s = self.suggestions.items[self.suggestions.sel]
            self.dest_name = s["name"].split(",")[0][:20]
            self.action_cancel()
            self._calculate_route(s["lat"], s["lon"])
    
    def _calculate_route(self, dlat, dlon):
        if not self.lat:
            self.notify("⚠️ Get GPS first (press 'r')")
            return
        
        self.notify("🗺️ Calculating route...")
        self.route = get_route(self.lat, self.lon, dlat, dlon)
        self.current_step = 0
        
        if self.route:
            self.notify(f"✅ Route: {fmt_dist(self.route['dist'])}, {fmt_time(self.route['time'])}")
        else:
            self.notify("❌ No route found")
        
        self._update_display()
    
    def action_clear(self):
        self.route = None
        self.dest_name = None
        self.current_step = 0
        self.tracking = False
        if self._timer:
            self._timer.stop()
            self._timer = None
        self._update_display()
        self.notify("Route cleared")
    
    def action_next(self):
        if self.route and self.current_step < len(self.route["steps"]) - 1:
            self.current_step += 1
            self._update_display()
    
    def action_prev(self):
        if self.current_step > 0:
            self.current_step -= 1
            self._update_display()
    
    def action_up(self):
        if self._search_active and self.suggestions.items:
            self.suggestions.sel = (self.suggestions.sel - 1) % len(self.suggestions.items)
            self.suggestions.refresh()
    
    def action_down(self):
        if self._search_active and self.suggestions.items:
            self.suggestions.sel = (self.suggestions.sel + 1) % len(self.suggestions.items)
            self.suggestions.refresh()
    
    def on_input_changed(self, e):
        q = e.value.strip()
        if len(q) >= 2 and q != self._last_q:
            self._last_q = q
            local = [p for p in PLACES if q.lower() in p["name"].lower()]
            online = search_places(q, self.lat, self.lon)
            self.suggestions.items = (local + online)[:8]
            self.suggestions.sel = 0
            self.suggestions.refresh()
    
    def on_input_submitted(self, e):
        self.action_confirm()


def run():
    print("TermGPS - Active Navigation")
    TermGPS().run()

if __name__ == "__main__":
    run()
