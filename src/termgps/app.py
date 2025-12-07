#!/usr/bin/env python3
"""
TermGPS - Cross-Platform Terminal GPS Navigation

Works on: Windows, macOS, Linux, and any system with Python 3.9+
Lightweight and fast.
"""

import os
import sys
import math
import platform
from typing import Optional, List, Dict, Tuple

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input
from textual.containers import Container
from textual.binding import Binding
from textual import events
from rich.text import Text
from rich.style import Style

# Lazy imports
_requests = None

def _get_requests():
    global _requests
    if _requests is None:
        import requests
        _requests = requests
    return _requests


# =============================================================================
# CROSS-PLATFORM GPS
# =============================================================================

def get_location() -> Tuple[Optional[float], Optional[float], str]:
    """
    Get location - works on all platforms.
    Priority: Platform GPS > IP Geolocation
    """
    system = platform.system()
    
    # Try platform-specific GPS first
    if system == "Darwin":  # macOS
        result = _get_macos_location()
        if result[0]:
            return result
    elif system == "Windows":
        result = _get_windows_location()
        if result[0]:
            return result
    elif system == "Linux":
        result = _get_linux_location()
        if result[0]:
            return result
    
    # Fallback: IP geolocation (works everywhere)
    return _get_ip_location()


def _get_macos_location() -> Tuple[Optional[float], Optional[float], str]:
    """macOS CoreLocation."""
    try:
        import CoreLocation
        from Foundation import NSRunLoop, NSDate
        
        mgr = CoreLocation.CLLocationManager.alloc().init()
        status = CoreLocation.CLLocationManager.authorizationStatus()
        
        if status == CoreLocation.kCLAuthorizationStatusDenied:
            return None, None, "Location denied"
        
        mgr.requestWhenInUseAuthorization()
        mgr.setDesiredAccuracy_(CoreLocation.kCLLocationAccuracyBest)
        mgr.startUpdatingLocation()
        
        for _ in range(30):
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
            loc = mgr.location()
            if loc and loc.horizontalAccuracy() > 0:
                mgr.stopUpdatingLocation()
                return (loc.coordinate().latitude, loc.coordinate().longitude, 
                        f"GPS ±{loc.horizontalAccuracy():.0f}m")
        
        mgr.stopUpdatingLocation()
    except:
        pass
    return None, None, ""


def _get_windows_location() -> Tuple[Optional[float], Optional[float], str]:
    """Windows Location API."""
    try:
        # Try Windows Location API via wmi/winrt
        import asyncio
        from winrt.windows.devices.geolocation import Geolocator
        
        async def get_pos():
            loc = Geolocator()
            pos = await loc.get_geoposition_async()
            return pos.coordinate.latitude, pos.coordinate.longitude, pos.coordinate.accuracy
        
        lat, lon, acc = asyncio.run(get_pos())
        return lat, lon, f"GPS ±{acc:.0f}m"
    except:
        pass
    return None, None, ""


def _get_linux_location() -> Tuple[Optional[float], Optional[float], str]:
    """Linux gpsd or GeoClue."""
    try:
        # Try gpsd
        import gps
        session = gps.gps(mode=gps.WATCH_ENABLE)
        for _ in range(10):
            report = session.next()
            if report['class'] == 'TPV' and hasattr(report, 'lat'):
                return report.lat, report.lon, "GPS"
    except:
        pass
    return None, None, ""


def _get_ip_location() -> Tuple[Optional[float], Optional[float], str]:
    """IP geolocation - works on ALL platforms."""
    try:
        # Try multiple free IP geolocation services
        services = [
            ("http://ip-api.com/json/", lambda d: (d.get("lat"), d.get("lon"))),
            ("https://ipapi.co/json/", lambda d: (d.get("latitude"), d.get("longitude"))),
        ]
        
        for url, parser in services:
            try:
                r = _get_requests().get(url, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    lat, lon = parser(data)
                    if lat and lon:
                        return float(lat), float(lon), "IP (~10km)"
            except:
                continue
    except:
        pass
    return None, None, "No location"


# =============================================================================
# ROUTING (OSRM - works everywhere)
# =============================================================================

def get_route(lat1: float, lon1: float, lat2: float, lon2: float) -> Optional[Dict]:
    """Get driving route from OSRM."""
    try:
        r = _get_requests().get(
            f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}",
            params={"overview": "simplified", "geometries": "geojson", "steps": "true"},
            timeout=10
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


def search_places(q: str, user_lat: float = None, user_lon: float = None) -> List[Dict]:
    """Search places with India bias."""
    if len(q) < 2:
        return []
    
    search_q = f"{q}, India" if 'india' not in q.lower() else q
    
    try:
        params = {"q": search_q, "format": "json", "limit": 6, "countrycodes": "in"}
        if user_lat and user_lon:
            params["viewbox"] = f"{user_lon-2},{user_lat+2},{user_lon+2},{user_lat-2}"
        
        r = _get_requests().get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            headers={"User-Agent": "TermGPS/1.0"},
            timeout=5
        )
        results = [{"name": x["display_name"][:55], "lat": float(x["lat"]), "lon": float(x["lon"])} 
                   for x in r.json()]
        
        if not results:  # Try without India bias
            r = _get_requests().get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 5},
                headers={"User-Agent": "TermGPS/1.0"},
                timeout=5
            )
            results = [{"name": x["display_name"][:55], "lat": float(x["lat"]), "lon": float(x["lon"])} 
                       for x in r.json()]
        
        return results
    except:
        return []


# Quick places
PLACES = [
    {"name": "Chennai", "lat": 13.0827, "lon": 80.2707},
    {"name": "Coimbatore", "lat": 11.0168, "lon": 76.9558},
    {"name": "Madurai", "lat": 9.9252, "lon": 78.1198},
    {"name": "Bangalore", "lat": 12.9716, "lon": 77.5946},
    {"name": "Hyderabad", "lat": 17.3850, "lon": 78.4867},
    {"name": "Mumbai", "lat": 19.0760, "lon": 72.8777},
    {"name": "Delhi", "lat": 28.6139, "lon": 77.2090},
    {"name": "Kolkata", "lat": 22.5726, "lon": 88.3639},
]


# =============================================================================
# MATH
# =============================================================================

def dist_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def bearing(lat1, lon1, lat2, lon2):
    dlon = math.radians(lon2-lon1)
    x = math.sin(dlon)*math.cos(math.radians(lat2))
    y = math.cos(math.radians(lat1))*math.sin(math.radians(lat2)) - math.sin(math.radians(lat1))*math.cos(math.radians(lat2))*math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


# =============================================================================
# UI WIDGETS
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
        self._w, self._h = 60, 20
    
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
        
        # Route
        if self.route and self.lat:
            for i,(lo,la) in enumerate(self.route):
                x, y = cx+int((lo-self.lon)*400), cy-int((la-self.lat)*800)
                if 0<=x<w and 0<=y<h:
                    buf[y][x] = '━' if 0<i<len(self.route)-1 else ('●' if i==0 else '◆')
                    col[y][x] = 'blue' if 0<i<len(self.route)-1 else ('cyan' if i==0 else 'red')
        
        # Crosshairs
        for x in range(w):
            if 0<=cy<h and buf[cy][x]==' ': buf[cy][x]='─'
        for y in range(h):
            if 0<=cx<w and buf[y][cx]==' ': buf[y][cx]='│'
        if 0<=cx<w and 0<=cy<h: buf[cy][cx]='╋'; col[cy][cx]='white'
        
        # Compass
        if 0<=cx<w:
            if cy>0: buf[0][cx]='N'; col[0][cx]='white'
            if cy<h-1: buf[h-1][cx]='S'; col[h-1][cx]='white'
        if 0<=cy<h: buf[cy][0]='W'; col[cy][0]='white'; buf[cy][w-1]='E'; col[cy][w-1]='white'
        
        # YOU
        if self.lat:
            for i,c in enumerate("◉YOU"):
                if 0<=cx+2+i<w: buf[cy][cx+2+i]=c; col[cy][cx+2+i]='yellow'
        
        # Direction arrow
        if self.dlat and self.lat:
            b = bearing(self.lat,self.lon,self.dlat,self.dlon)
            d = dist_km(self.lat,self.lon,self.dlat,self.dlon)
            al = min(5, min(cx,w-cx,cy,h-cy)-2)
            if al>1:
                ex,ey = int(cx+al*math.sin(math.radians(b))), int(cy-al*math.cos(math.radians(b))*0.5)
                if 0<=ex<w and 0<=ey<h:
                    buf[ey][ex]='▲◥▶◢▼◣◀◤'[int((b+22.5)/45)%8]; col[ey][ex]='red'
                    ds = f"{d:.0f}km" if d>=1 else f"{int(d*1000)}m"
                    lbl = f" {self.dname[:6]}({ds})"
                    for i,c in enumerate(lbl):
                        if 0<=ex+1+i<w: buf[ey][ex+1+i]=c; col[ey][ex+1+i]='white'
        
        txt = Text()
        for y in range(h):
            for x in range(w): txt.append(buf[y][x], style=Style(color=col[y][x]))
            txt.append('\n')
        return txt


class Dirs(Static):
    def __init__(self): super().__init__(); self.steps=[]; self.idx=0
    def render(self) -> Text:
        txt = Text()
        if not self.steps: return txt
        txt.append(f"─ DIRECTIONS ({self.idx+1}/{len(self.steps)}) ─\n", style="cyan bold")
        icons = {'left':'←','right':'→','straight':'↑'}
        for i in range(self.idx, min(self.idx+3,len(self.steps))):
            s = self.steps[i]
            icon = icons.get(s['mod'].split('-')[-1] if s['mod'] else '','→')
            ds = f"{s['dist']:.1f}km" if s['dist']>=1 else f"{int(s['dist']*1000)}m"
            txt.append(f" {icon} {s['name'][:32]:<32} {ds:>6}\n", style="green bold" if i==self.idx else "dim")
        txt.append(" [n]ext [p]rev\n", style="dim")
        return txt


class Info(Static):
    def __init__(self): super().__init__(); self.gps="Press r"; self.lat=self.lon=None; self.dest=None; self.dist=self.time=0
    def render(self) -> Text:
        txt = Text()
        txt.append(f"─ GPS: {self.gps} ─\n", style="cyan")
        if self.lat: txt.append(f" YOU: {self.lat:.4f}, {self.lon:.4f}\n", style="white")
        if self.dest:
            h,m = int(self.time//60), int(self.time%60)
            txt.append(f" TO: {self.dest} ({self.dist:.0f}km, {h}h{m}m)\n", style="green")
        return txt


class Sugs(Static):
    def __init__(self): super().__init__(); self.items=[]; self.sel=0
    def render(self) -> Text:
        txt = Text()
        for i,item in enumerate(self.items[:6]):
            txt.append(f"{'▶' if i==self.sel else ' '} {item['name'][:50]}\n", style="green bold" if i==self.sel else "white")
        return txt


# =============================================================================
# APP
# =============================================================================

class TermGPS(App):
    CSS = """
    Screen { background: #000; }
    #radar { height: 50%; border: solid green; }
    #dirs { height: 22%; }
    #info { height: 13%; }
    #search { display: none; border: solid yellow; padding: 1; }
    #search.show { display: block; }
    Input { background: #111; color: green; }
    Static { color: green; }
    """
    
    BINDINGS = [
        Binding("q","quit","Quit"), Binding("d","search","Search"), Binding("r","gps","GPS"),
        Binding("c","clear","Clear"), Binding("n","next","Next"), Binding("p","prev","Prev"),
        Binding("escape","cancel",show=False), Binding("enter","confirm",show=False),
        Binding("up","up",show=False), Binding("down","down",show=False),
    ]
    
    def __init__(self):
        super().__init__()
        self.lat=self.lon=None; self.dlat=self.dlon=None; self.dname=None
        self.route=None; self._search=False; self._q=""
    
    def compose(self) -> ComposeResult:
        yield Header()
        self.radar=Radar(); self.dirs=Dirs(); self.info=Info()
        self.sugs=Sugs(); self.inp=Input(placeholder="Search...")
        with Container(id="search"): yield self.inp; yield self.sugs
        with Container(id="radar"): yield self.radar
        yield self.dirs; yield self.info; yield Footer()
    
    def _refresh(self):
        self.radar.lat,self.radar.lon = self.lat,self.lon
        self.radar.dlat,self.radar.dlon = self.dlat,self.dlon
        self.radar.dname = self.dname or ""
        self.radar.route = self.route["pts"] if self.route else []
        self.dirs.steps = self.route["steps"] if self.route else []
        self.info.lat,self.info.lon = self.lat,self.lon
        self.info.dest = self.dname
        self.info.dist = self.route["dist"] if self.route else 0
        self.info.time = self.route["time"] if self.route else 0
        self.radar.refresh(); self.dirs.refresh(); self.info.refresh()
    
    def action_gps(self):
        self.notify("📍 Getting location...")
        self.lat, self.lon, self.info.gps = get_location()
        self._refresh()
        if self.lat and self.dlat: self._calc_route()
    
    def action_search(self):
        self._search=True; self.query_one("#search").add_class("show")
        self.inp.value=""; self.sugs.items=[]; self.inp.focus()
    
    def action_cancel(self):
        self._search=False; self.query_one("#search").remove_class("show")
    
    def action_confirm(self):
        if self._search and self.sugs.items:
            s = self.sugs.items[self.sugs.sel]
            self.dlat,self.dlon = s["lat"],s["lon"]
            self.dname = s["name"].split(",")[0][:15]
            self.action_cancel(); self._calc_route()
    
    def _calc_route(self):
        if self.lat and self.dlat:
            self.notify("🗺️ Routing...")
            self.route = get_route(self.lat,self.lon,self.dlat,self.dlon)
            self._refresh()
            if self.route: self.notify(f"✅ {self.route['dist']:.0f}km")
    
    def action_clear(self): self.dlat=self.dlon=self.dname=self.route=None; self._refresh()
    def action_next(self):
        if self.dirs.steps and self.dirs.idx<len(self.dirs.steps)-1: self.dirs.idx+=1; self.dirs.refresh()
    def action_prev(self):
        if self.dirs.idx>0: self.dirs.idx-=1; self.dirs.refresh()
    def action_up(self):
        if self._search and self.sugs.items: self.sugs.sel=(self.sugs.sel-1)%len(self.sugs.items); self.sugs.refresh()
    def action_down(self):
        if self._search and self.sugs.items: self.sugs.sel=(self.sugs.sel+1)%len(self.sugs.items); self.sugs.refresh()
    
    def on_input_changed(self, e):
        q = e.value.strip()
        if len(q)>=2 and q!=self._q:
            self._q = q
            local = [p for p in PLACES if q.lower() in p["name"].lower()]
            online = search_places(q, self.lat, self.lon)
            self.sugs.items = (local + online)[:8]
            self.sugs.sel = 0; self.sugs.refresh()
    
    def on_input_submitted(self, e): self.action_confirm()


def run():
    print(f"TermGPS - {platform.system()}")
    TermGPS().run()

if __name__ == "__main__":
    run()
