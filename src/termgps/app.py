#!/usr/bin/env python3
"""
TermGPS - Fast Navigation with Themes & Co-Pilot

Features:
- Live Turn-by-Turn Navigation
- Co-Pilot Commentary & Movement Detection
- GPS Radar & Signal Meter
- Programmer Themes
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

_req = None
def req():
    global _req
    if not _req: import requests; _req = requests
    return _req

# Programmer-focused themes (like IDE themes)
THEMES_LIST = ["matrix", "dracula", "monokai", "nord", "gruvbox", "solarized"]
THEMES = {
    "matrix": {"name": "Matrix", "fg": "green", "bg": "#000", "hl": "bright_green", "rt": "green", "err": "red"},
    "dracula": {"name": "Dracula", "fg": "#f8f8f2", "bg": "#282a36", "hl": "#ff79c6", "rt": "#8be9fd", "err": "#ff5555"},
    "monokai": {"name": "Monokai", "fg": "#f8f8f2", "bg": "#272822", "hl": "#f92672", "rt": "#66d9ef", "err": "#f92672"},
    "nord": {"name": "Nord", "fg": "#eceff4", "bg": "#2e3440", "hl": "#88c0d0", "rt": "#81a1c1", "err": "#bf616a"},
    "gruvbox": {"name": "Gruvbox", "fg": "#ebdbb2", "bg": "#282828", "hl": "#fabd2f", "rt": "#83a598", "err": "#fb4934"},
    "solarized": {"name": "Solarized", "fg": "#839496", "bg": "#002b36", "hl": "#b58900", "rt": "#268bd2", "err": "#dc322f"},
}
theme = "matrix"
theme_idx = 0

def get_gps():
    if platform.system() == "Darwin":
        try:
            import CoreLocation
            from Foundation import NSRunLoop, NSDate
            m = CoreLocation.CLLocationManager.alloc().init()
            m.requestWhenInUseAuthorization()
            m.setDesiredAccuracy_(CoreLocation.kCLLocationAccuracyBest)
            m.startUpdatingLocation()
            for _ in range(15):
                NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
                l = m.location()
                if l and l.horizontalAccuracy() > 0:
                    m.stopUpdatingLocation()
                    return l.coordinate().latitude, l.coordinate().longitude, f"±{l.horizontalAccuracy():.0f}m"
            m.stopUpdatingLocation()
        except: pass
    try:
        r = req().get("http://ip-api.com/json/", timeout=3)
        if r.ok: d = r.json(); return d.get("lat"), d.get("lon"), "~10km"
    except: pass
    return None, None, "N/A"

def get_route(lat1, lon1, lat2, lon2):
    try:
        r = req().get(f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}",
                      params={"overview": "simplified", "geometries": "geojson", "steps": "true"}, timeout=8)
        d = r.json()
        if d.get("code") != "Ok": return None
        rt = d["routes"][0]
        steps = []
        for leg in rt.get("legs", []):
            for s in leg.get("steps", []):
                m = s.get("maneuver", {})
                steps.append({"name": s.get("name") or "Road", "mod": m.get("modifier", ""),
                              "type": m.get("type", ""), "dist": s.get("distance", 0),
                              "loc": m.get("location", [0, 0])})
        return {"dist": rt["distance"], "time": rt["duration"], "pts": rt["geometry"]["coordinates"], "steps": steps}
    except: return None

def search(q, lat=None, lon=None):
    if len(q) < 2: return []
    try:
        p = {"q": f"{q}, India" if 'india' not in q.lower() else q, "format": "json", "limit": 5}
        r = req().get("https://nominatim.openstreetmap.org/search", params=p, headers={"User-Agent": "TermGPS"}, timeout=4)
        return [{"name": x["display_name"][:45], "lat": float(x["lat"]), "lon": float(x["lon"])} for x in r.json()]
    except: return []

PLACES = [{"name": "Chennai", "lat": 13.08, "lon": 80.27}, {"name": "Coimbatore", "lat": 11.01, "lon": 76.95},
          {"name": "Madurai", "lat": 9.92, "lon": 78.11}, {"name": "Bangalore", "lat": 12.97, "lon": 77.59}]

def dist_m(lat1, lon1, lat2, lon2):
    R = 6371000; dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def fmt_d(m): return f"{m/1000:.1f}km" if m >= 1000 else f"{int(m)}m"
def fmt_t(s): h, m = int(s//3600), int((s%3600)//60); return f"{h}h{m}m" if h else f"{m}min"
def turn_icon(mod, typ):
    if typ == "arrive": return "🏁"
    if "left" in mod: return "⬅"
    if "right" in mod: return "➡"
    return "⬆"

class Radar(Static):
    can_focus = True
    def __init__(self): super().__init__(); self.lat=self.lon=None; self.route=[]; self.steps=[]; self.cur=0; self.px=self.py=0; self._d=False; self._x=self._y=0; self._w=50; self._h=18
    def on_resize(self, e): self._w, self._h = e.size.width, e.size.height
    def on_mouse_down(self, e): self._d, self._x, self._y = True, e.x, e.y; self.capture_mouse()
    def on_mouse_up(self, e): self._d = False; self.release_mouse()
    def on_mouse_move(self, e):
        if self._d: self.px += e.x-self._x; self.py += e.y-self._y; self._x, self._y = e.x, e.y; self.refresh()
    
    def render(self):
        t = THEMES[theme]; w, h = self._w, self._h
        buf = [[' ']*w for _ in range(h)]
        col = [[t["fg"]]*w for _ in range(h)]
        cx, cy = max(2,min(w-2,w//2+self.px)), max(2,min(h-2,h//2+self.py))
        
        # Draw route in BLUE
        if self.route and self.lat:
            for i,(lo,la) in enumerate(self.route):
                x, y = cx+int((lo-self.lon)*500), cy-int((la-self.lat)*1000)
                if 0<=x<w and 0<=y<h:
                    if i == 0:
                        buf[y][x] = '●'; col[y][x] = 'cyan'  # Start
                    elif i == len(self.route)-1:
                        buf[y][x] = '◆'; col[y][x] = 'red'   # Destination RED
                    else:
                        buf[y][x] = '━'; col[y][x] = 'blue'  # Route BLUE
        
        # Draw range circles (optional visual)
        for r in [6, 12]:
            for a in range(0, 360, 15):
                x = int(cx + r * math.cos(math.radians(a)))
                y = int(cy - r * math.sin(math.radians(a)) * 0.5)
                if 0<=x<w and 0<=y<h and buf[y][x] == ' ':
                    buf[y][x] = '·'; col[y][x] = t["fg"]
        
        # Draw crosshairs in GREEN
        for x in range(w):
            if 0<=cy<h and buf[cy][x]==' ': buf[cy][x]='─'; col[cy][x]=t["fg"]
        for y in range(h):
            if 0<=cx<w and buf[y][cx]==' ': buf[y][cx]='│'; col[y][cx]=t["fg"]
        
        # Center crosshair - RED/YELLOW
        if 0<=cx<w and 0<=cy<h:
            buf[cy][cx] = '╋'
            col[cy][cx] = 'red' if self.lat else 'yellow'
        
        # Compass in WHITE
        if 0<=cx<w:
            if cy>0: buf[0][cx]='N'; col[0][cx]='white'
            if cy<h-1: buf[h-1][cx]='S'; col[h-1][cx]='white'
        if 0<=cy<h:
            buf[cy][0]='W'; col[cy][0]='white'
            buf[cy][w-1]='E'; col[cy][w-1]='white'
        
        # YOU marker in RED/YELLOW
        if self.lat:
            label = " ◉ YOU"
            for i,c in enumerate(label):
                if 0<=cx+1+i<w:
                    buf[cy][cx+1+i]=c
                    col[cy][cx+1+i]='yellow'
        
        # Direction arrow pointing to destination
        if self.route and self.lat and len(self.route) > 1:
            # Get destination (last point of route)
            dest_lon, dest_lat = self.route[-1]
            # Calculate bearing
            dlon = math.radians(dest_lon - self.lon)
            lat1_r, lat2_r = math.radians(self.lat), math.radians(dest_lat)
            x = math.sin(dlon) * math.cos(lat2_r)
            y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon)
            b = (math.degrees(math.atan2(x, y)) + 360) % 360
            
            # Draw arrow line
            arrow_len = min(8, min(cx-2, w-cx-2, cy-2, h-cy-2))
            if arrow_len > 3:
                for i in range(2, arrow_len):
                    ax = int(cx + i * math.sin(math.radians(b)))
                    ay = int(cy - i * math.cos(math.radians(b)) * 0.5)
                    if 0<=ax<w and 0<=ay<h and buf[ay][ax] == ' ':
                        buf[ay][ax] = '●'; col[ay][ax] = 'magenta'
                # Arrow head
                end_x = int(cx + arrow_len * math.sin(math.radians(b)))
                end_y = int(cy - arrow_len * math.cos(math.radians(b)) * 0.5)
                arrows = ['▲', '◥', '▶', '◢', '▼', '◣', '◀', '◤']
                arrow_char = arrows[int((b + 22.5) / 45) % 8]
                if 0<=end_x<w and 0<=end_y<h:
                    buf[end_y][end_x] = arrow_char; col[end_y][end_x] = 'red'
        
        # Next turn marker
        if self.steps and self.cur < len(self.steps) and self.lat:
            s = self.steps[self.cur]
            lo, la = s["loc"]
            tx, ty = cx+int((lo-self.lon)*500), cy-int((la-self.lat)*1000)
            if 0<=tx<w and 0<=ty<h:
                buf[ty][tx] = '▼'; col[ty][tx] = 'red'
        
        txt = Text()
        for y in range(h):
            for x in range(w): txt.append(buf[y][x], style=Style(color=col[y][x]))
            txt.append('\n')
        return txt

class DirPanel(Static):
    def __init__(self): super().__init__(); self.icon="🧭"; self.dist="---"; self.road="Set destination"; self.step=0; self.total=0
    def render(self):
        t = THEMES[theme]; txt = Text()
        txt.append("─── NEXT TURN ───\n", style=Style(color=t["hl"], bold=True))
        txt.append(f"\n   {self.icon}  {self.dist}\n\n", style=Style(color=t["hl"], bold=True))
        txt.append(f"   {self.road[:25]}\n", style=Style(color=t["fg"]))
        if self.total: txt.append(f"   Step {self.step+1}/{self.total}\n", style=Style(color=t["fg"], dim=True))
        return txt

class TurnsPanel(Static):
    def __init__(self): super().__init__(); self.steps=[]; self.cur=0
    def render(self):
        t = THEMES[theme]; txt = Text()
        txt.append("─── UPCOMING ───\n", style=Style(color=t["hl"], bold=True))
        if not self.steps: txt.append(" No route\n", style=Style(dim=True)); return txt
        for i in range(self.cur, min(self.cur+4, len(self.steps))):
            s = self.steps[i]; icon = turn_icon(s["mod"], s["type"]); d = fmt_d(s["dist"])
            style = Style(color=t["hl"], bold=True) if i==self.cur else Style(color=t["fg"], dim=True)
            txt.append(f" {icon} {s['name'][:15]:<15} {d:>6}\n", style=style)
        return txt

class InfoPanel(Static):
    def __init__(self): super().__init__(); self.dest=None; self.dist=0; self.time=0; self.lat=None; self.lon=None; self.acc="N/A"; self.tracking=False
    def render(self):
        t = THEMES[theme]; txt = Text()
        txt.append("─── INFO ───\n", style=Style(color=t["hl"], bold=True))
        
        # Signal Meter
        bars = "     "; color = "red"
        if self.lat:
            try:
                acc_val = float(''.join(c for c in self.acc if c.isdigit() or c == '.'))
                if 'km' in self.acc: acc_val *= 1000
                if acc_val <= 20: bars = "▂▃▅▆▇"; color = "green"
                elif acc_val <= 100: bars = "▂▃▅▆ "; color = "yellow"
                elif acc_val <= 500: bars = "▂▃▅  "; color = "yellow"
                else: bars = "▂    "; color = "red"
            except: pass
            txt.append(f" SIG: ", style=Style(color=t["fg"]))
            txt.append(f"{bars}", style=Style(color=color))
            txt.append(f" ({self.acc})\n", style=Style(color=t["fg"], dim=True))
            txt.append(f" LOC: {self.lat:.4f}, {self.lon:.4f}\n", style=Style(color=t["fg"]))
        else:
            txt.append(" GPS: Press 'r' to connect\n", style=Style(dim=True))
            
        if self.dest:
            txt.append(f" TO: {self.dest[:20]}\n", style=Style(color=t["fg"]))
            txt.append(f" {fmt_d(self.dist)} | {fmt_t(self.time)}\n", style=Style(color=t["hl"]))
        if self.tracking: txt.append(" 🔄 TRACKING ACTIVE\n", style=Style(color=t["hl"], bold=True))
        return txt

class ThemePanel(Static):
    def render(self):
        t = THEMES[theme]; txt = Text()
        txt.append("─── THEME ───\n", style=Style(color=t["hl"], bold=True))
        txt.append(f" {t['name']}\n", style=Style(color=t["fg"]))
        txt.append(" Press 't' then ⬅/➡\n", style=Style(color=t["fg"], dim=True))
        return txt

class PilotPanel(Static):
    """Co-Pilot Commentary & Status"""
    def __init__(self): 
        super().__init__()
        self.commentary = "Waiting for journey to start..."
        self.speed = 0.0
        self.moving = False
        self.eta = "N/A"
    
    def render(self) -> Text:
        t = THEMES[theme]; txt = Text()
        txt.append("─── CO-PILOT ───\n", style=Style(color=t["hl"], bold=True))
        
        # Movement Status
        status = "MOVING" if self.moving else "STATIONARY"
        color = t["hl"] if self.moving else t["fg"]
        txt.append(f" STATUS: {status} ", style=Style(color=color, bold=True))
        if self.moving:
            txt.append(f"({int(self.speed)} km/h)\n", style=Style(color=t["accent"] if "accent" in t else t["fg"]))
        else:
            txt.append("\n")
            
        # Commentary Box
        txt.append(" 💬 ", style=Style(color=t["rt"]))
        # Wrap commentary nicely
        words = self.commentary.split()
        line = ""
        for w in words:
            if len(line) + len(w) + 1 > 26:
                txt.append(line + "\n    ", style=Style(color=t["fg"], italic=True))
                line = w + " "
            else:
                line += w + " "
        txt.append(line + "\n", style=Style(color=t["fg"], italic=True))
        
        # ETA
        txt.append(f"\n ETA: {self.eta}", style=Style(color=t["hl"]))
        return txt

class Sugs(Static):
    def __init__(self): super().__init__(); self.items=[]; self.sel=0
    def render(self):
        t = THEMES[theme]; txt = Text()
        for i, item in enumerate(self.items[:5]):
            style = Style(color=t["hl"], bold=True) if i==self.sel else Style(color=t["fg"])
            txt.append(f"{'▶' if i==self.sel else ' '} {item['name'][:40]}\n", style=style)
        return txt

class TermGPS(App):
    CSS = """
    Screen { background: #000; }
    #left { width: 30; }
    #right { width: 1fr; }
    #dir { height: 8; border: solid green; }
    #turns { height: 7; border: solid green; }
    #info { height: 7; border: solid green; }
    #theme { height: 4; border: solid green; }
    #pilot { height: 8; border: solid green; }
    #radar { height: 100%; border: heavy green; }
    #search { display: none; border: solid yellow; padding: 1; }
    #search.show { display: block; }
    Input { background: #111; color: green; }
    Static { color: green; }
    """
    
    BINDINGS = [
        Binding("q","quit","Quit"), Binding("d","search","Dest"), Binding("r","gps","GPS"),
        Binding("x","track","Track"), Binding("c","clear","Clear"), Binding("n","next","Next"), Binding("p","prev","Prev"),
        Binding("t","theme_mode","Theme Mode"),
        Binding("escape","cancel",show=False), Binding("enter","confirm",show=False),
        Binding("up","up",show=False), Binding("down","down",show=False),
        Binding("left","left",show=False), Binding("right","right",show=False),
    ]
    
    def __init__(self):
        super().__init__()
        self.lat=self.lon=None; self.route=None; self.dest=None; self.cur=0
        self.tracking=False; self._sa=False; self._q=""; self._timer=None; self.theme_mode=False
        # Pilot data
        self.last_lat = None; self.last_lon = None; self.last_time = None
    
    def compose(self):
        yield Header()
        self.radar=Radar(); self.dir=DirPanel(); self.turns=TurnsPanel(); self.info=InfoPanel()
        self.thm=ThemePanel(); self.pilot=PilotPanel(); self.sugs=Sugs(); self.inp=Input(placeholder="Search...")
        with Container(id="search"): yield self.inp; yield self.sugs
        with Horizontal():
            with Vertical(id="left"):
                yield Container(self.dir, id="dir")
                yield Container(self.turns, id="turns")
                yield Container(self.info, id="info")
                yield Container(self.thm, id="theme")
                yield Container(self.pilot, id="pilot")
            yield Container(self.radar, id="radar")
        yield Footer()
    
    def _refresh(self):
        self.radar.lat, self.radar.lon = self.lat, self.lon
        self.radar.route = self.route["pts"] if self.route else []
        self.radar.steps = self.route["steps"] if self.route else []
        self.radar.cur = self.cur
        
        if self.route and self.cur < len(self.route["steps"]):
            s = self.route["steps"][self.cur]
            self.dir.icon = turn_icon(s["mod"], s["type"])
            self.dir.road = s["name"]
            self.dir.step = self.cur
            self.dir.total = len(self.route["steps"])
            if self.lat:
                d = dist_m(self.lat, self.lon, s["loc"][1], s["loc"][0])
                self.dir.dist = fmt_d(d)
                
                # Pilot Logic
                if d < 100: self.pilot.commentary = f"Take the turn now onto {s['name']}!"
                elif d < 500: self.pilot.commentary = f"Prepare to turn {s['mod']} in {int(d)}m."
                elif d > 5000: self.pilot.commentary = f"Long stretch on {s['name']}. Relax."
                else: self.pilot.commentary = f"Continue on {s['name']}."
            else:
                self.dir.dist = fmt_d(s["dist"])
                self.pilot.commentary = "Waiting for GPS..."
        else:
            self.dir.icon = "🧭"; self.dir.road = "No destination"; self.dir.dist = "---"; self.dir.total = 0
            self.pilot.commentary = "Ready for a new adventure! Press 'd'."
        
        self.turns.steps = self.route["steps"] if self.route else []
        self.turns.cur = self.cur
        
        self.info.lat, self.info.lon = self.lat, self.lon
        self.info.dest = self.dest
        self.info.tracking = self.tracking
        if self.route:
            rem_dist = sum(s["dist"] for s in self.route["steps"][self.cur:])
            rem_time = self.route["time"] * (rem_dist / self.route["dist"]) if self.route["dist"] else 0
            self.info.dist = rem_dist
            self.info.time = rem_time
            self.pilot.eta = fmt_t(rem_time)
        else:
            self.pilot.eta = "N/A"
        
        self.radar.refresh(); self.dir.refresh(); self.turns.refresh(); self.info.refresh(); self.thm.refresh(); self.pilot.refresh()
    
    def _check(self):
        if not self.route or not self.lat or self.cur >= len(self.route["steps"]): return
        s = self.route["steps"][self.cur]
        if dist_m(self.lat, self.lon, s["loc"][1], s["loc"][0]) < 50:
            if self.cur < len(self.route["steps"])-1:
                self.cur += 1; self.notify(f"🔔 {self.route['steps'][self.cur]['name']}", timeout=2)
            else:
                self.notify("🏁 Arrived!", timeout=3); self.tracking = False
                if self._timer: self._timer.stop()
    
    def action_gps(self):
        self.notify("📍...", timeout=1); self.lat, self.lon, self.info.acc = get_gps()
        # Speed calc
        now = time.time()
        if self.last_lat and self.last_time:
            dist = dist_m(self.last_lat, self.last_lon, self.lat, self.lon)
            dt = now - self.last_time
            if dt > 0:
                speed_ms = dist / dt
                self.pilot.speed = speed_ms * 3.6
                self.pilot.moving = self.pilot.speed > 3.0 # >3km/h threshold
        self.last_lat, self.last_lon, self.last_time = self.lat, self.lon, now
        
        self._refresh(); self._check()
    
    def action_track(self):
        self.tracking = not self.tracking
        if self.tracking: 
            self._timer = self.set_interval(5, self._tick); self.notify("🔄 ON", timeout=1)
            self.last_lat = self.last_lon = self.last_time = None # Reset speed tracking
        else:
            if self._timer: self._timer.stop(); self._timer = None
            self.notify("⏹ OFF", timeout=1)
            self.pilot.moving = False # Reset status
        self._refresh()
    
    def _tick(self):
        if self.tracking: self.action_gps()
    
    def action_search(self):
        self._sa = True; self.query_one("#search").add_class("show"); self.inp.value = ""; self.sugs.items = []; self.inp.focus()
    
    def action_cancel(self): self._sa = False; self.query_one("#search").remove_class("show")
    
    def action_confirm(self):
        if self._sa and self.sugs.items:
            s = self.sugs.items[self.sugs.sel]; self.dest = s["name"].split(",")[0][:15]
            self.action_cancel(); self._calc(s["lat"], s["lon"])
    
    def _calc(self, dlat, dlon):
        if not self.lat: self.notify("⚠ Get GPS first", timeout=2); return
        self.notify("🗺️...", timeout=1); self.route = get_route(self.lat, self.lon, dlat, dlon); self.cur = 0
        if self.route: self.notify(f"✅ {fmt_d(self.route['dist'])}", timeout=2)
        self._refresh()
    
    def action_clear(self):
        self.route = self.dest = None; self.cur = 0; self.tracking = False
        if self._timer: self._timer.stop(); self._timer = None
        self._refresh()
    
    def action_next(self):
        if self.route and self.cur < len(self.route["steps"])-1: self.cur += 1; self._refresh()
    def action_prev(self):
        if self.cur > 0: self.cur -= 1; self._refresh()
    
    def action_theme_mode(self):
        self.theme_mode = not self.theme_mode
        if self.theme_mode: self.notify("🎨 Theme Mode: Use ⬅/➡")
        else: self.notify("Theme Mode OFF")
    
    def action_left(self):
        global theme, theme_idx
        if self.theme_mode:
            theme_idx = (theme_idx - 1) % len(THEMES_LIST)
            theme = THEMES_LIST[theme_idx]
            self._refresh(); self.notify(f"Theme: {THEMES[theme]['name']}", timeout=1)
    
    def action_right(self):
        global theme, theme_idx
        if self.theme_mode:
            theme_idx = (theme_idx + 1) % len(THEMES_LIST)
            theme = THEMES_LIST[theme_idx]
            self._refresh(); self.notify(f"Theme: {THEMES[theme]['name']}", timeout=1)
    
    def action_up(self):
        if self._sa and self.sugs.items: self.sugs.sel = (self.sugs.sel-1) % len(self.sugs.items); self.sugs.refresh()
    def action_down(self):
        if self._sa and self.sugs.items: self.sugs.sel = (self.sugs.sel+1) % len(self.sugs.items); self.sugs.refresh()
    
    def on_input_changed(self, e):
        q = e.value.strip()
        if len(q) >= 2 and q != self._q:
            self._q = q
            local = [p for p in PLACES if q.lower() in p["name"].lower()]
            self.sugs.items = (local + search(q, self.lat, self.lon))[:6]
            self.sugs.sel = 0; self.sugs.refresh()
    
    def on_input_submitted(self, e): self.action_confirm()

def run(): TermGPS().run()
if __name__ == "__main__": run()
