#!/usr/bin/env python3
"""
TermGPS - Fast & Lightweight Terminal GPS Navigation

Optimized for speed and low resource usage.
"""

import os
import math
from typing import Optional, List, Dict, Tuple

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input
from textual.containers import Container
from textual.binding import Binding
from textual import events
from rich.text import Text
from rich.style import Style

# Lazy imports for faster startup
_requests = None
_geocoder = None

def _get_requests():
    global _requests
    if _requests is None:
        import requests
        _requests = requests
    return _requests

def _get_geocoder():
    global _geocoder
    if _geocoder is None:
        import geocoder
        _geocoder = geocoder
    return _geocoder


# =============================================================================
# GPS - Lightweight version
# =============================================================================

def get_location() -> Tuple[Optional[float], Optional[float], str]:
    """Get GPS location - tries CoreLocation first, falls back to IP."""
    # Try macOS CoreLocation
    try:
        import CoreLocation
        from Foundation import NSRunLoop, NSDate
        
        mgr = CoreLocation.CLLocationManager.alloc().init()
        if CoreLocation.CLLocationManager.authorizationStatus() == CoreLocation.kCLAuthorizationStatusDenied:
            raise Exception("Denied")
        
        mgr.requestWhenInUseAuthorization()
        mgr.setDesiredAccuracy_(CoreLocation.kCLLocationAccuracyBest)
        mgr.startUpdatingLocation()
        
        for _ in range(50):
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
            loc = mgr.location()
            if loc and loc.horizontalAccuracy() > 0:
                mgr.stopUpdatingLocation()
                acc = loc.horizontalAccuracy()
                status = f"GPS ±{acc:.0f}m" if acc <= 100 else "GPS (low)"
                return loc.coordinate().latitude, loc.coordinate().longitude, status
        mgr.stopUpdatingLocation()
    except:
        pass
    
    # Fallback to IP
    try:
        g = _get_geocoder().ip('me')
        if g.ok:
            return g.lat, g.lng, "IP (~10km)"
    except:
        pass
    
    return None, None, "No location"


# =============================================================================
# ROUTING - Lightweight OSRM
# =============================================================================

def get_route(lat1: float, lon1: float, lat2: float, lon2: float) -> Optional[Dict]:
    """Get route from OSRM - returns simplified data."""
    try:
        r = _get_requests().get(
            f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}",
            params={"overview": "simplified", "geometries": "geojson", "steps": "true"},
            timeout=8
        )
        data = r.json()
        if data.get("code") != "Ok":
            return None
        
        route = data["routes"][0]
        steps = []
        for leg in route.get("legs", []):
            for s in leg.get("steps", []):
                m = s.get("maneuver", {})
                steps.append({
                    "name": s.get("name") or "Continue",
                    "type": m.get("type", ""),
                    "mod": m.get("modifier", ""),
                    "dist": s.get("distance", 0) / 1000
                })
        
        return {
            "dist": route["distance"] / 1000,
            "time": route["duration"] / 60,
            "pts": route["geometry"]["coordinates"],
            "steps": steps
        }
    except:
        return None


def search_places(q: str) -> List[Dict]:
    """Search places - lightweight."""
    if len(q) < 2:
        return []
    try:
        r = _get_requests().get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "limit": 5},
            headers={"User-Agent": "TermGPS/1.0"},
            timeout=4
        )
        return [{"name": x["display_name"][:50], "lat": float(x["lat"]), "lon": float(x["lon"])} for x in r.json()]
    except:
        return []


# =============================================================================
# MATH - Inline for speed
# =============================================================================

def dist_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def bearing(lat1, lon1, lat2, lon2):
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(math.radians(lat2))
    y = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


# =============================================================================
# RADAR WIDGET - Optimized
# =============================================================================

class Radar(Static):
    can_focus = True
    
    def __init__(self):
        super().__init__()
        self.lat = self.lon = None
        self.dlat = self.dlon = None
        self.dname = ""
        self.route = []
        self.px = self.py = 0
        self._drag = False
        self._dx = self._dy = 0
        self._w = 60
        self._h = 20
    
    def on_resize(self, e): self._w, self._h = e.size.width, e.size.height
    
    def on_mouse_down(self, e):
        if e.button == 1:
            self._drag = True
            self._dx, self._dy = e.x, e.y
            self.capture_mouse()
    
    def on_mouse_up(self, e):
        self._drag = False
        self.release_mouse()
    
    def on_mouse_move(self, e):
        if self._drag:
            self.px += e.x - self._dx
            self.py += e.y - self._dy
            self._dx, self._dy = e.x, e.y
            self.refresh()
    
    def render(self) -> Text:
        w, h = self._w, self._h
        buf = [[' ']*w for _ in range(h)]
        col = [['green']*w for _ in range(h)]
        
        cx = max(3, min(w-3, w//2 + self.px))
        cy = max(2, min(h-2, h//2 + self.py))
        
        # Route (blue)
        if self.route and self.lat:
            scale = 400
            for i, (lo, la) in enumerate(self.route):
                x = cx + int((lo - self.lon) * scale)
                y = cy - int((la - self.lat) * scale * 2)
                if 0 <= x < w and 0 <= y < h:
                    buf[y][x] = '━' if i > 0 and i < len(self.route)-1 else ('●' if i == 0 else '◆')
                    col[y][x] = 'blue' if i > 0 and i < len(self.route)-1 else ('cyan' if i == 0 else 'red')
        
        # Crosshairs
        for x in range(w):
            if 0 <= cy < h and buf[cy][x] == ' ': buf[cy][x] = '─'
        for y in range(h):
            if 0 <= cx < w and buf[y][cx] == ' ': buf[y][cx] = '│'
        if 0 <= cx < w and 0 <= cy < h: buf[cy][cx] = '╋'; col[cy][cx] = 'white'
        
        # Compass
        if 0 <= cx < w:
            if cy > 0: buf[0][cx] = 'N'; col[0][cx] = 'white'
            if cy < h-1: buf[h-1][cx] = 'S'; col[h-1][cx] = 'white'
        if 0 <= cy < h:
            buf[cy][0] = 'W'; col[cy][0] = 'white'
            buf[cy][w-1] = 'E'; col[cy][w-1] = 'white'
        
        # YOU label
        if self.lat:
            for i, c in enumerate("◉YOU"):
                if 0 <= cx+2+i < w: buf[cy][cx+2+i] = c; col[cy][cx+2+i] = 'yellow'
        
        # Destination arrow
        if self.dlat and self.lat:
            b = bearing(self.lat, self.lon, self.dlat, self.dlon)
            d = dist_km(self.lat, self.lon, self.dlat, self.dlon)
            al = min(5, min(cx, w-cx, cy, h-cy) - 2)
            if al > 1:
                ex = int(cx + al * math.sin(math.radians(b)))
                ey = int(cy - al * math.cos(math.radians(b)) * 0.5)
                arrows = '▲◥▶◢▼◣◀◤'
                if 0 <= ex < w and 0 <= ey < h:
                    buf[ey][ex] = arrows[int((b+22.5)/45)%8]
                    col[ey][ex] = 'red'
                    # Label
                    ds = f"{d:.0f}km" if d >= 1 else f"{int(d*1000)}m"
                    lbl = f" {self.dname[:6]}({ds})"
                    lx = min(ex+1, w-len(lbl)-1)
                    for i, c in enumerate(lbl):
                        if 0 <= lx+i < w: buf[ey][lx+i] = c; col[ey][lx+i] = 'white'
        
        # Build text
        txt = Text()
        for y in range(h):
            for x in range(w):
                txt.append(buf[y][x], style=Style(color=col[y][x]))
            txt.append('\n')
        return txt


class Directions(Static):
    def __init__(self):
        super().__init__()
        self.steps = []
        self.idx = 0
    
    def render(self) -> Text:
        txt = Text()
        if not self.steps:
            txt.append("No route. Press 'd' to search.\n", style="dim")
            return txt
        
        txt.append("─ DIRECTIONS ", style="cyan bold")
        txt.append(f"({self.idx+1}/{len(self.steps)})\n", style="cyan")
        
        icons = {'left': '←', 'right': '→', 'straight': '↑', 'arrive': '🏁', 'depart': '🚗'}
        for i in range(self.idx, min(self.idx+3, len(self.steps))):
            s = self.steps[i]
            icon = icons.get(s['mod'].split('-')[-1] if s['mod'] else '', '→')
            ds = f"{s['dist']:.1f}km" if s['dist'] >= 1 else f"{int(s['dist']*1000)}m"
            style = "green bold" if i == self.idx else "dim"
            txt.append(f" {icon} {s['name'][:35]:<35} {ds:>6}\n", style=style)
        
        txt.append(" [n]ext [p]rev\n", style="dim")
        return txt


class Info(Static):
    def __init__(self):
        super().__init__()
        self.gps = "Press 'r'"
        self.lat = self.lon = None
        self.dest = None
        self.dist = self.time = 0
    
    def render(self) -> Text:
        txt = Text()
        txt.append("─ NAV ─\n", style="green bold")
        txt.append(f" GPS: {self.gps}\n", style="cyan")
        if self.lat:
            txt.append(f" YOU: {self.lat:.4f},{self.lon:.4f}\n", style="white")
        if self.dest:
            h, m = int(self.time//60), int(self.time%60)
            eta = f"{h}h{m}m" if h else f"{m}min"
            txt.append(f" TO: {self.dest} | {self.dist:.1f}km | {eta}\n", style="green")
        return txt


class Suggestions(Static):
    def __init__(self):
        super().__init__()
        self.items = []
        self.sel = 0
    
    def render(self) -> Text:
        txt = Text()
        for i, item in enumerate(self.items[:5]):
            style = "green bold" if i == self.sel else "white"
            txt.append(f"{'▶' if i == self.sel else ' '} {item['name'][:50]}\n", style=style)
        return txt


# =============================================================================
# APP - Lightweight
# =============================================================================

class TermGPS(App):
    CSS = """
    Screen { background: black; }
    #radar { height: 50%; border: solid green; }
    #dirs { height: 25%; }
    #info { height: 15%; }
    #search { display: none; border: solid yellow; }
    #search.show { display: block; }
    Input { background: #111; color: green; }
    Static { color: green; }
    Footer { background: #010; }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "search", "Search"),
        Binding("r", "gps", "GPS"),
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
        self.dlat = self.dlon = None
        self.dname = None
        self.route = None
        self._search = False
        self._q = ""
    
    def compose(self) -> ComposeResult:
        yield Header()
        self.radar = Radar()
        self.dirs = Directions()
        self.info = Info()
        self.sugs = Suggestions()
        self.inp = Input(placeholder="Type destination...")
        
        with Container(id="search"):
            yield self.inp
            yield self.sugs
        
        with Container(id="radar"):
            yield self.radar
        yield self.dirs
        yield self.info
        yield Footer()
    
    def _refresh(self):
        self.radar.lat, self.radar.lon = self.lat, self.lon
        self.radar.dlat, self.radar.dlon = self.dlat, self.dlon
        self.radar.dname = self.dname or ""
        self.radar.route = self.route["pts"] if self.route else []
        self.dirs.steps = self.route["steps"] if self.route else []
        self.info.lat, self.info.lon = self.lat, self.lon
        self.info.dest = self.dname
        self.info.dist = self.route["dist"] if self.route else 0
        self.info.time = self.route["time"] if self.route else 0
        self.radar.refresh()
        self.dirs.refresh()
        self.info.refresh()
    
    def action_gps(self):
        self.notify("📍 Getting GPS...")
        self.lat, self.lon, self.info.gps = get_location()
        self._refresh()
        if self.lat and self.dlat:
            self._calc_route()
    
    def action_search(self):
        self._search = True
        self.query_one("#search").add_class("show")
        self.inp.value = ""
        self.sugs.items = []
        self.inp.focus()
    
    def action_cancel(self):
        self._search = False
        self.query_one("#search").remove_class("show")
    
    def action_confirm(self):
        if self._search and self.sugs.items:
            s = self.sugs.items[self.sugs.sel]
            self.dlat, self.dlon = s["lat"], s["lon"]
            self.dname = s["name"].split(",")[0][:15]
            self.action_cancel()
            self._calc_route()
    
    def _calc_route(self):
        if self.lat and self.dlat:
            self.notify("🗺️ Routing...")
            self.route = get_route(self.lat, self.lon, self.dlat, self.dlon)
            self._refresh()
            if self.route:
                self.notify(f"✅ {self.route['dist']:.0f}km")
    
    def action_clear(self):
        self.dlat = self.dlon = self.dname = self.route = None
        self._refresh()
    
    def action_next(self):
        if self.dirs.steps and self.dirs.idx < len(self.dirs.steps)-1:
            self.dirs.idx += 1
            self.dirs.refresh()
    
    def action_prev(self):
        if self.dirs.idx > 0:
            self.dirs.idx -= 1
            self.dirs.refresh()
    
    def action_up(self):
        if self._search and self.sugs.items:
            self.sugs.sel = (self.sugs.sel - 1) % len(self.sugs.items)
            self.sugs.refresh()
    
    def action_down(self):
        if self._search and self.sugs.items:
            self.sugs.sel = (self.sugs.sel + 1) % len(self.sugs.items)
            self.sugs.refresh()
    
    def on_input_changed(self, e):
        q = e.value.strip()
        if len(q) >= 3 and q != self._q:
            self._q = q
            self.sugs.items = search_places(q)
            self.sugs.sel = 0
            self.sugs.refresh()
    
    def on_input_submitted(self, e):
        self.action_confirm()


def run():
    TermGPS().run()

if __name__ == "__main__":
    run()
