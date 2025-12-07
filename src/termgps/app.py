#!/usr/bin/env python3
"""
TermGPS - Terminal GPS Navigation with Radar Display

FEATURES:
- Real GPS location using macOS Location Services
- Destination search with auto-suggestions
- TURN-BY-TURN NAVIGATION with actual road paths
- Route display showing all roads to destination
- Step-by-step directions
- Distance and ETA calculation

CONTROLS:
- d: Search destination
- r: Refresh GPS location
- c: Clear destination
- n: Next navigation step
- p: Previous navigation step
- Mouse drag: Pan the view
- q: Quit
"""

import os
import sys
import math
from typing import Optional, Tuple, List, Dict, Any

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input, Label
from textual.containers import Container, Vertical
from textual.binding import Binding
from textual import events
from rich.text import Text
from rich.style import Style


# =============================================================================
# GPS LOCATION
# =============================================================================

def get_macos_location() -> Tuple[Optional[float], Optional[float], str]:
    """Get GPS location using macOS CoreLocation."""
    try:
        import CoreLocation
        from Foundation import NSRunLoop, NSDate
        
        manager = CoreLocation.CLLocationManager.alloc().init()
        auth_status = CoreLocation.CLLocationManager.authorizationStatus()
        
        if auth_status == CoreLocation.kCLAuthorizationStatusDenied:
            return None, None, "❌ Location DENIED - Enable in System Preferences"
        
        if auth_status == CoreLocation.kCLAuthorizationStatusNotDetermined:
            manager.requestWhenInUseAuthorization()
            for _ in range(30):
                NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
        
        manager.setDesiredAccuracy_(CoreLocation.kCLLocationAccuracyBest)
        manager.startUpdatingLocation()
        
        for _ in range(100):
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
            loc = manager.location()
            if loc and loc.horizontalAccuracy() > 0:
                lat = loc.coordinate().latitude
                lon = loc.coordinate().longitude
                acc = loc.horizontalAccuracy()
                manager.stopUpdatingLocation()
                
                if acc <= 10:
                    return lat, lon, f"📍 GPS: Excellent (±{acc:.0f}m)"
                elif acc <= 50:
                    return lat, lon, f"📍 GPS: Good (±{acc:.0f}m)"
                else:
                    return lat, lon, f"📍 GPS: Fair (±{acc:.0f}m)"
        
        manager.stopUpdatingLocation()
        return get_ip_location()
        
    except ImportError:
        return get_ip_location()
    except Exception as e:
        return None, None, f"❌ GPS error: {str(e)[:30]}"


def get_ip_location() -> Tuple[Optional[float], Optional[float], str]:
    """Fallback: Get location via IP."""
    try:
        import geocoder
        g = geocoder.ip('me')
        if g.ok:
            return g.lat, g.lng, "🌐 IP Location (~10km accuracy)"
    except:
        pass
    return None, None, "❌ Could not determine location"


# =============================================================================
# ROUTING - Uses OSRM (Free, OpenStreetMap-based routing)
# =============================================================================

def get_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> Optional[Dict]:
    """
    Get driving route from OSRM (Open Source Routing Machine).
    Returns route with geometry, steps, distance, and duration.
    """
    try:
        import requests
        
        # OSRM public API (free, no key needed)
        url = f"https://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}"
        params = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "true",
            "annotations": "true"
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        
        route = data["routes"][0]
        
        # Extract route information
        result = {
            "distance": route["distance"] / 1000,  # km
            "duration": route["duration"] / 60,     # minutes
            "geometry": route["geometry"]["coordinates"],  # [[lon, lat], ...]
            "steps": []
        }
        
        # Extract turn-by-turn steps
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                maneuver = step.get("maneuver", {})
                result["steps"].append({
                    "instruction": step.get("name", "Continue"),
                    "type": maneuver.get("type", ""),
                    "modifier": maneuver.get("modifier", ""),
                    "distance": step.get("distance", 0) / 1000,  # km
                    "duration": step.get("duration", 0) / 60,    # minutes
                    "location": maneuver.get("location", [0, 0])  # [lon, lat]
                })
        
        return result
        
    except Exception as e:
        return None


def search_places(query: str) -> List[Dict]:
    """Search for places using Nominatim API."""
    if len(query) < 2:
        return []
    
    try:
        import requests
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "json", "limit": 5}
        headers = {"User-Agent": "TermGPS/1.0"}
        response = requests.get(url, params=params, headers=headers, timeout=5)
        
        results = []
        for item in response.json():
            results.append({
                "name": item.get("display_name", "")[:60],
                "lat": float(item["lat"]),
                "lon": float(item["lon"])
            })
        return results
    except:
        return []


# =============================================================================
# MATH UTILITIES
# =============================================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers."""
    R = 6371
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate bearing from point 1 to point 2."""
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    x = math.sin(delta_lon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def bearing_to_direction(bearing: float) -> str:
    """Convert bearing to compass direction."""
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return directions[int((bearing + 11.25) / 22.5) % 16]


def get_turn_icon(maneuver_type: str, modifier: str) -> str:
    """Get icon for turn type."""
    if maneuver_type == "arrive":
        return "🏁"
    elif maneuver_type == "depart":
        return "🚗"
    elif "left" in modifier:
        return "⬅️"
    elif "right" in modifier:
        return "➡️"
    elif "straight" in modifier:
        return "⬆️"
    elif maneuver_type == "roundabout":
        return "🔄"
    elif maneuver_type == "merge":
        return "↗️"
    else:
        return "➡️"


# =============================================================================
# UI COMPONENTS
# =============================================================================

class RadarWidget(Static):
    """Radar display with route visualization."""
    
    can_focus = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.my_lat: Optional[float] = None
        self.my_lon: Optional[float] = None
        self.dest_lat: Optional[float] = None
        self.dest_lon: Optional[float] = None
        self.dest_name: str = ""
        self.route_points: List[Tuple[float, float]] = []  # [(lat, lon), ...]
        self.pan_x: int = 0
        self.pan_y: int = 0
        self.zoom: float = 1.0
        self._dragging: bool = False
        self._drag_x: int = 0
        self._drag_y: int = 0
        self._width: int = 60
        self._height: int = 20
    
    def on_resize(self, event: events.Resize) -> None:
        self._width = event.size.width
        self._height = event.size.height
    
    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 1:
            self._dragging = True
            self._drag_x = event.x
            self._drag_y = event.y
            self.capture_mouse()
    
    def on_mouse_up(self, event: events.MouseUp) -> None:
        self._dragging = False
        self.release_mouse()
    
    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._dragging:
            self.pan_x += event.x - self._drag_x
            self.pan_y += event.y - self._drag_y
            self._drag_x = event.x
            self._drag_y = event.y
            self.refresh()
    
    def set_my_position(self, lat: Optional[float], lon: Optional[float]) -> None:
        self.my_lat = lat
        self.my_lon = lon
    
    def set_destination(self, lat: float, lon: float, name: str) -> None:
        self.dest_lat = lat
        self.dest_lon = lon
        self.dest_name = name
    
    def set_route(self, route_points: List[Tuple[float, float]]) -> None:
        """Set the route path to display."""
        self.route_points = route_points
    
    def clear_destination(self) -> None:
        self.dest_lat = None
        self.dest_lon = None
        self.dest_name = ""
        self.route_points = []
    
    def _latlon_to_screen(self, lat: float, lon: float, center_lat: float, center_lon: float) -> Tuple[int, int]:
        """Convert lat/lon to screen coordinates."""
        # Scale factor (degrees to screen units)
        scale = 500 * self.zoom
        
        # Center of screen
        cx = self._width // 2 + self.pan_x
        cy = self._height // 2 + self.pan_y
        
        # Convert to screen coordinates
        x = cx + int((lon - center_lon) * scale)
        y = cy - int((lat - center_lat) * scale * 2)  # *2 for aspect ratio
        
        return x, y
    
    def render(self) -> Text:
        text = Text()
        w, h = self._width, self._height
        buffer = [[' ' for _ in range(w)] for _ in range(h)]
        
        # Center position (with pan offset)
        cx = w // 2 + self.pan_x
        cy = h // 2 + self.pan_y
        cx = max(3, min(w - 3, cx))
        cy = max(2, min(h - 2, cy))
        
        # Draw route path if available
        if self.route_points and self.my_lat and self.my_lon:
            prev_x, prev_y = None, None
            for i, (lon, lat) in enumerate(self.route_points):
                x, y = self._latlon_to_screen(lat, lon, self.my_lat, self.my_lon)
                
                # Draw route point
                if 0 <= x < w and 0 <= y < h:
                    # Use different characters for the route
                    if i == 0:
                        buffer[y][x] = '●'  # Start
                    elif i == len(self.route_points) - 1:
                        buffer[y][x] = '◆'  # End (destination)
                    else:
                        buffer[y][x] = '·'  # Route path
                
                # Draw line between points
                if prev_x is not None and prev_y is not None:
                    self._draw_line(buffer, prev_x, prev_y, x, y, '·')
                
                prev_x, prev_y = x, y
        
        # Draw range circles around my position
        for radius in [4, 8, 12]:
            for angle in range(0, 360, 10):
                x = int(cx + radius * math.cos(math.radians(angle)))
                y = int(cy - radius * math.sin(math.radians(angle)) * 0.5)
                if 0 <= x < w and 0 <= y < h and buffer[y][x] == ' ':
                    buffer[y][x] = '·'
        
        # Draw crosshairs
        for x in range(w):
            if 0 <= cy < h and buffer[cy][x] == ' ':
                buffer[cy][x] = '─'
        for y in range(h):
            if 0 <= cx < w and buffer[y][cx] == ' ':
                buffer[y][cx] = '│'
        if 0 <= cx < w and 0 <= cy < h:
            buffer[cy][cx] = '╋'
        
        # Draw compass points
        if 0 <= cx < w:
            if cy > 0: buffer[0][cx] = 'N'
            if cy < h - 1: buffer[h - 1][cx] = 'S'
        if 0 <= cy < h:
            buffer[cy][0] = 'W'
            buffer[cy][w - 1] = 'E'
        
        # Draw "YOU" label
        if self.my_lat is not None:
            label = " ◉ YOU"
            for i, c in enumerate(label):
                if 0 <= cx + 2 + i < w and 0 <= cy < h:
                    buffer[cy][cx + 2 + i] = c
        
        # Draw destination marker and arrow
        if self.dest_lat and self.dest_lon and self.my_lat and self.my_lon:
            bearing = calculate_bearing(self.my_lat, self.my_lon, self.dest_lat, self.dest_lon)
            distance = haversine_distance(self.my_lat, self.my_lon, self.dest_lat, self.dest_lon)
            
            # Draw arrow indicating direction
            arrow_len = min(6, min(cx, w - cx, cy, h - cy) - 2)
            if arrow_len > 2:
                angle_rad = math.radians(bearing)
                end_x = int(cx + arrow_len * math.sin(angle_rad))
                end_y = int(cy - arrow_len * math.cos(angle_rad) * 0.5)
                
                arrows = ['▲', '◥', '▶', '◢', '▼', '◣', '◀', '◤']
                arrow_char = arrows[int((bearing + 22.5) / 45) % 8]
                if 0 <= end_x < w and 0 <= end_y < h:
                    buffer[end_y][end_x] = arrow_char
                
                # Destination label
                dist_str = f"{distance:.1f}km" if distance >= 1 else f"{int(distance * 1000)}m"
                label = f" {self.dest_name[:8]} ({dist_str})"
                label_x = min(end_x + 1, w - len(label))
                if 0 <= end_y < h:
                    for i, c in enumerate(label):
                        if 0 <= label_x + i < w:
                            buffer[end_y][label_x + i] = c
        
        # Route indicator
        if self.route_points:
            label = f"📍 Route: {len(self.route_points)} points"
            for i, c in enumerate(label):
                if 0 <= i < w and 0 <= 1 < h:
                    buffer[1][i] = c
        
        # Convert to Rich Text
        for row in buffer:
            text.append(''.join(row) + '\n', style=Style(color="green"))
        
        return text
    
    def _draw_line(self, buffer: List[List[str]], x1: int, y1: int, x2: int, y2: int, char: str) -> None:
        """Draw a line between two points using Bresenham's algorithm."""
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        
        w, h = len(buffer[0]), len(buffer)
        steps = 0
        max_steps = max(dx, dy) + 1
        
        while steps < max_steps:
            if 0 <= x1 < w and 0 <= y1 < h and buffer[y1][x1] == ' ':
                buffer[y1][x1] = char
            
            if x1 == x2 and y1 == y2:
                break
            
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy
            
            steps += 1


class DirectionsWidget(Static):
    """Shows turn-by-turn directions."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.steps: List[Dict] = []
        self.current_step: int = 0
    
    def set_steps(self, steps: List[Dict]) -> None:
        self.steps = steps
        self.current_step = 0
    
    def next_step(self) -> None:
        if self.steps and self.current_step < len(self.steps) - 1:
            self.current_step += 1
    
    def prev_step(self) -> None:
        if self.steps and self.current_step > 0:
            self.current_step -= 1
    
    def clear(self) -> None:
        self.steps = []
        self.current_step = 0
    
    def render(self) -> Text:
        text = Text()
        
        if not self.steps:
            text.append("No route loaded. Press 'd' to search destination.\n", style=Style(color="grey50"))
            return text
        
        text.append("┌─ DIRECTIONS ──────────────────────────────────────────┐\n", style=Style(color="cyan"))
        
        # Show current step prominently
        if 0 <= self.current_step < len(self.steps):
            step = self.steps[self.current_step]
            icon = get_turn_icon(step["type"], step["modifier"])
            instruction = step["instruction"] or "Continue"
            dist = step["distance"]
            dist_str = f"{dist:.1f}km" if dist >= 1 else f"{int(dist * 1000)}m"
            
            text.append(f"│ {icon} ", style=Style(color="yellow", bold=True))
            text.append(f"{instruction[:40]:<40}", style=Style(color="white", bold=True))
            text.append(f" {dist_str:>6} │\n", style=Style(color="green"))
        
        # Show next 2 steps
        for i in range(self.current_step + 1, min(self.current_step + 3, len(self.steps))):
            step = self.steps[i]
            icon = get_turn_icon(step["type"], step["modifier"])
            instruction = step["instruction"] or "Continue"
            dist = step["distance"]
            dist_str = f"{dist:.1f}km" if dist >= 1 else f"{int(dist * 1000)}m"
            
            text.append(f"│   {icon} {instruction[:38]:<38} {dist_str:>6} │\n", style=Style(color="grey70"))
        
        # Pad if needed
        displayed = min(3, len(self.steps) - self.current_step)
        for _ in range(3 - displayed):
            text.append(f"│{'':<55}│\n", style=Style(color="cyan"))
        
        text.append(f"│ Step {self.current_step + 1}/{len(self.steps):<5} ", style=Style(color="cyan"))
        text.append(f"{'[n]ext [p]revious':<35} │\n", style=Style(color="grey50"))
        text.append("└───────────────────────────────────────────────────────┘\n", style=Style(color="cyan"))
        
        return text


class SuggestionsWidget(Static):
    """Shows location suggestions dropdown."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.items: List[Dict] = []
        self.selected: int = 0
    
    def set_items(self, items: List[Dict]) -> None:
        self.items = items
        self.selected = 0
    
    def clear(self) -> None:
        self.items = []
    
    def move_selection(self, delta: int) -> None:
        if self.items:
            self.selected = (self.selected + delta) % len(self.items)
    
    def get_selected(self) -> Optional[Dict]:
        if self.items and 0 <= self.selected < len(self.items):
            return self.items[self.selected]
        return None
    
    def render(self) -> Text:
        text = Text()
        if not self.items:
            return text
        
        text.append("┌─ Suggestions ─────────────────────────────────────────┐\n", style=Style(color="yellow"))
        for i, item in enumerate(self.items[:5]):
            name = item["name"][:52]
            if i == self.selected:
                text.append(f"│ ▶ {name:<52} │\n", style=Style(color="green", bold=True))
            else:
                text.append(f"│   {name:<52} │\n", style=Style(color="white"))
        text.append("└───────────────────────────────────────────────────────┘\n", style=Style(color="yellow"))
        return text


class InfoWidget(Static):
    """Shows route summary information."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.gps_status: str = "Press 'r' to get GPS location"
        self.my_lat: Optional[float] = None
        self.my_lon: Optional[float] = None
        self.dest_name: Optional[str] = None
        self.route_distance: float = 0
        self.route_duration: float = 0
    
    def update_info(self, gps_status: str, lat: Optional[float], lon: Optional[float],
                    dest_name: Optional[str], distance: float, duration: float) -> None:
        self.gps_status = gps_status
        self.my_lat = lat
        self.my_lon = lon
        self.dest_name = dest_name
        self.route_distance = distance
        self.route_duration = duration
    
    def render(self) -> Text:
        text = Text()
        
        text.append("┌─ NAVIGATION ──────────────────────────────────────────┐\n", style=Style(color="green"))
        
        # GPS Status
        text.append(f"│ {self.gps_status:<54} │\n", style=Style(color="cyan"))
        
        # Location
        if self.my_lat is not None:
            loc = f"YOUR LOCATION: {self.my_lat:.5f}, {self.my_lon:.5f}"
            text.append(f"│ {loc:<54} │\n", style=Style(color="white"))
        else:
            text.append(f"│ {'YOUR LOCATION: Unknown (press r)':<54} │\n", style=Style(color="yellow"))
        
        # Destination & Route
        if self.dest_name and self.route_distance > 0:
            text.append(f"│ DESTINATION: {self.dest_name[:41]:<41} │\n", style=Style(color="white"))
            
            # Format duration
            hours = int(self.route_duration // 60)
            mins = int(self.route_duration % 60)
            if hours > 0:
                time_str = f"{hours}h {mins}m"
            else:
                time_str = f"{mins} min"
            
            route_info = f"DISTANCE: {self.route_distance:.1f} km  |  ETA: {time_str}"
            text.append(f"│ {route_info:<54} │\n", style=Style(color="green"))
        elif self.dest_name:
            text.append(f"│ DESTINATION: {self.dest_name[:41]:<41} │\n", style=Style(color="white"))
            text.append(f"│ {'Loading route...':<54} │\n", style=Style(color="yellow"))
        else:
            text.append(f"│ {'DESTINATION: Not set (press d)':<54} │\n", style=Style(color="grey50"))
            text.append(f"│ {'':<54} │\n", style=Style(color="green"))
        
        text.append("└───────────────────────────────────────────────────────┘\n", style=Style(color="green"))
        
        return text


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class TermGPSApp(App):
    """TermGPS with turn-by-turn navigation."""
    
    TITLE = "TermGPS - Navigation"
    
    CSS = """
    Screen { background: #000000; }
    
    #radar-container { height: 45%; border: heavy green; }
    #directions-panel { height: 25%; padding: 0 1; }
    #info-panel { height: 15%; padding: 0 1; }
    
    #search-box {
        display: none;
        height: auto;
        border: solid yellow;
        background: #111100;
        padding: 1;
    }
    #search-box.visible { display: block; }
    
    #search-input {
        width: 100%;
        background: #222200;
        color: #00ff00;
        border: solid green;
    }
    
    Static { color: #00ff00; }
    Footer { background: #001100; }
    Header { background: #001100; }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "open_search", "Search"),
        Binding("r", "refresh_gps", "GPS"),
        Binding("c", "clear_route", "Clear"),
        Binding("n", "next_step", "Next"),
        Binding("p", "prev_step", "Prev"),
        Binding("escape", "close_search", "Cancel", show=False),
        Binding("enter", "confirm_search", "OK", show=False),
        Binding("up", "move_up", "↑", show=False),
        Binding("down", "move_down", "↓", show=False),
    ]
    
    def __init__(self):
        super().__init__()
        self.my_lat: Optional[float] = None
        self.my_lon: Optional[float] = None
        self.gps_status: str = "Press 'r' for GPS"
        self.dest_lat: Optional[float] = None
        self.dest_lon: Optional[float] = None
        self.dest_name: Optional[str] = None
        self.route: Optional[Dict] = None
        self.search_active: bool = False
        self._last_query: str = ""
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        self.radar = RadarWidget(id="radar")
        self.directions = DirectionsWidget(id="directions-panel")
        self.suggestions = SuggestionsWidget(id="suggestions")
        self.info = InfoWidget(id="info-panel")
        self.search_input = Input(placeholder="Type destination...", id="search-input")
        
        with Container(id="search-box"):
            yield Label("🔍 Search Destination:")
            yield self.search_input
            yield self.suggestions
        
        with Container(id="radar-container"):
            yield self.radar
        
        yield self.directions
        yield self.info
        yield Footer()
    
    def on_mount(self) -> None:
        self._refresh_display()
        self.notify("Press 'r' for GPS, 'd' to search destination")
    
    def _refresh_display(self) -> None:
        """Refresh all displays."""
        self.radar.set_my_position(self.my_lat, self.my_lon)
        
        if self.dest_lat:
            self.radar.set_destination(self.dest_lat, self.dest_lon, self.dest_name or "")
        
        if self.route:
            self.radar.set_route(self.route["geometry"])
            self.directions.set_steps(self.route["steps"])
            self.info.update_info(
                self.gps_status, self.my_lat, self.my_lon,
                self.dest_name, self.route["distance"], self.route["duration"]
            )
        else:
            self.info.update_info(
                self.gps_status, self.my_lat, self.my_lon,
                self.dest_name, 0, 0
            )
        
        self.radar.refresh()
        self.directions.refresh()
        self.info.refresh()
    
    def action_refresh_gps(self) -> None:
        """Get GPS location."""
        self.notify("📍 Getting GPS location...")
        self.my_lat, self.my_lon, self.gps_status = get_macos_location()
        self._refresh_display()
        
        if self.my_lat:
            self.notify(f"Location: {self.my_lat:.4f}, {self.my_lon:.4f}")
            
            # Recalculate route if destination exists
            if self.dest_lat:
                self._calculate_route()
    
    def action_open_search(self) -> None:
        self.search_active = True
        self.query_one("#search-box").add_class("visible")
        self.search_input.value = ""
        self.suggestions.clear()
        self.search_input.focus()
    
    def action_close_search(self) -> None:
        self.search_active = False
        self.query_one("#search-box").remove_class("visible")
        self.suggestions.clear()
        self.radar.focus()
    
    def action_confirm_search(self) -> None:
        if self.search_active:
            selected = self.suggestions.get_selected()
            if selected:
                self.dest_lat = selected["lat"]
                self.dest_lon = selected["lon"]
                self.dest_name = selected["name"].split(",")[0][:25]
                
                self.notify(f"📍 Destination: {self.dest_name}")
                self._calculate_route()
            
            self.action_close_search()
    
    def _calculate_route(self) -> None:
        """Calculate route to destination."""
        if not self.my_lat or not self.dest_lat:
            return
        
        self.notify("🗺️ Calculating route...")
        self.route = get_route(self.my_lat, self.my_lon, self.dest_lat, self.dest_lon)
        
        if self.route:
            steps = len(self.route["steps"])
            dist = self.route["distance"]
            self.notify(f"✅ Route found: {dist:.1f}km, {steps} turns")
        else:
            self.notify("❌ Could not calculate route", severity="error")
        
        self._refresh_display()
    
    def action_clear_route(self) -> None:
        self.dest_lat = None
        self.dest_lon = None
        self.dest_name = None
        self.route = None
        self.radar.clear_destination()
        self.directions.clear()
        self._refresh_display()
        self.notify("Route cleared")
    
    def action_next_step(self) -> None:
        self.directions.next_step()
        self.directions.refresh()
    
    def action_prev_step(self) -> None:
        self.directions.prev_step()
        self.directions.refresh()
    
    def action_move_up(self) -> None:
        if self.search_active:
            self.suggestions.move_selection(-1)
            self.suggestions.refresh()
    
    def action_move_down(self) -> None:
        if self.search_active:
            self.suggestions.move_selection(1)
            self.suggestions.refresh()
    
    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            query = event.value.strip()
            if len(query) >= 3 and query != self._last_query:
                self._last_query = query
                results = search_places(query)
                self.suggestions.set_items(results)
                self.suggestions.refresh()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self.action_confirm_search()


def run():
    """Run TermGPS."""
    print("\n" + "=" * 60)
    print("  TermGPS - Turn-by-Turn Navigation")
    print("=" * 60)
    print("\nControls:")
    print("  r = Get GPS location")
    print("  d = Search destination")
    print("  n/p = Next/Previous step")
    print("  c = Clear route")
    print("  Mouse drag = Pan view")
    print("  q = Quit")
    print("\n" + "=" * 60 + "\n")
    
    app = TermGPSApp()
    app.run()


if __name__ == "__main__":
    run()
