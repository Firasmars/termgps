#!/usr/bin/env python3
"""
TermGPS - Terminal GPS Navigation with Radar Display

FEATURES:
- Real GPS location using macOS Location Services
- Static radar display (NO automatic movement)
- Destination search with auto-suggestions
- Direction arrow pointing to destination
- Distance and bearing calculation
- Arrival notification

CONTROLS:
- d: Search destination
- r: Refresh GPS location
- c: Clear destination
- Mouse drag: Pan the view
- Arrow keys: Select suggestion
- Enter: Confirm selection
- Escape: Cancel search
- q: Quit
"""

import os
import sys
import math
import subprocess
from typing import Optional, Tuple, List, Dict

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input, Label
from textual.containers import Container
from textual.binding import Binding
from textual import events
from rich.text import Text
from rich.style import Style


# =============================================================================
# GPS LOCATION - Uses macOS Location Services
# =============================================================================

def get_macos_location() -> Tuple[Optional[float], Optional[float], str]:
    """
    Get GPS location using macOS CoreLocation.
    Returns: (latitude, longitude, status_message)
    """
    try:
        # Try using CoreLocation via pyobjc
        import CoreLocation
        from Foundation import NSRunLoop, NSDate
        
        manager = CoreLocation.CLLocationManager.alloc().init()
        
        # Check authorization status
        auth_status = CoreLocation.CLLocationManager.authorizationStatus()
        
        if auth_status == CoreLocation.kCLAuthorizationStatusDenied:
            return None, None, "❌ Location DENIED - Enable in System Preferences > Privacy > Location Services"
        
        if auth_status == CoreLocation.kCLAuthorizationStatusRestricted:
            return None, None, "⚠️ Location restricted by system"
        
        # Request authorization if not determined
        if auth_status == CoreLocation.kCLAuthorizationStatusNotDetermined:
            manager.requestWhenInUseAuthorization()
            # Wait briefly for user response
            for _ in range(30):
                NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
                if CoreLocation.CLLocationManager.authorizationStatus() != CoreLocation.kCLAuthorizationStatusNotDetermined:
                    break
        
        # Start location updates
        manager.setDesiredAccuracy_(CoreLocation.kCLLocationAccuracyBest)
        manager.startUpdatingLocation()
        
        # Wait for location (up to 10 seconds)
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
                elif acc <= 100:
                    return lat, lon, f"📍 GPS: Fair (±{acc:.0f}m)"
                else:
                    return lat, lon, f"📍 GPS: Low accuracy (±{acc:.0f}m)"
        
        manager.stopUpdatingLocation()
        return None, None, "⏳ GPS timeout - try again"
        
    except ImportError:
        return get_ip_location()
    except Exception as e:
        return None, None, f"❌ GPS error: {str(e)[:30]}"


def get_ip_location() -> Tuple[Optional[float], Optional[float], str]:
    """Fallback: Get location via IP geolocation."""
    try:
        import geocoder
        g = geocoder.ip('me')
        if g.ok:
            return g.lat, g.lng, "🌐 IP Location (city-level, ~10km accuracy)"
    except:
        pass
    return None, None, "❌ Could not determine location"


# =============================================================================
# DESTINATION SEARCH - Uses OpenStreetMap Nominatim (free, no API key)
# =============================================================================

def search_places(query: str) -> List[Dict]:
    """Search for places using Nominatim API."""
    if len(query) < 2:
        return []
    
    try:
        import requests
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "json", "limit": 5}
        headers = {"User-Agent": "TermGPS/1.0 (https://github.com/termgps)"}
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
    R = 6371  # Earth's radius in km
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate bearing from point 1 to point 2 in degrees (0-360, 0=North)."""
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


# =============================================================================
# UI COMPONENTS
# =============================================================================

class RadarWidget(Static):
    """
    Radar display widget.
    - Shows crosshair at center (your position)
    - Shows arrow pointing to destination
    - Supports mouse drag to pan view
    """
    
    can_focus = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.my_lat: Optional[float] = None
        self.my_lon: Optional[float] = None
        self.dest_lat: Optional[float] = None
        self.dest_lon: Optional[float] = None
        self.dest_name: str = ""
        self.pan_x: int = 0
        self.pan_y: int = 0
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
    
    def clear_destination(self) -> None:
        self.dest_lat = None
        self.dest_lon = None
        self.dest_name = ""
    
    def reset_pan(self) -> None:
        self.pan_x = 0
        self.pan_y = 0
    
    def render(self) -> Text:
        text = Text()
        w, h = self._width, self._height
        buffer = [[' ' for _ in range(w)] for _ in range(h)]
        
        # Center position (with pan offset)
        cx = w // 2 + self.pan_x
        cy = h // 2 + self.pan_y
        cx = max(3, min(w - 3, cx))
        cy = max(2, min(h - 2, cy))
        
        # Draw range circles
        for radius in [4, 8, 12]:
            for angle in range(0, 360, 8):
                x = int(cx + radius * math.cos(math.radians(angle)))
                y = int(cy - radius * math.sin(math.radians(angle)) * 0.5)
                if 0 <= x < w and 0 <= y < h:
                    buffer[y][x] = '·'
        
        # Draw crosshairs (YOUR position)
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
            if cy > 0:
                buffer[0][cx] = 'N'
            if cy < h - 1:
                buffer[h - 1][cx] = 'S'
        if 0 <= cy < h:
            buffer[cy][0] = 'W'
            buffer[cy][w - 1] = 'E'
        
        # Draw "YOU" label
        if self.my_lat is not None:
            label = " ◉ YOU"
            for i, c in enumerate(label):
                if 0 <= cx + 2 + i < w and 0 <= cy < h:
                    buffer[cy][cx + 2 + i] = c
        
        # Draw destination arrow
        if self.dest_lat and self.dest_lon and self.my_lat and self.my_lon:
            bearing = calculate_bearing(self.my_lat, self.my_lon, self.dest_lat, self.dest_lon)
            distance = haversine_distance(self.my_lat, self.my_lon, self.dest_lat, self.dest_lon)
            
            arrow_len = min(8, min(cx, w - cx, cy, h - cy) - 2)
            if arrow_len > 2:
                angle_rad = math.radians(bearing)
                
                # Draw arrow line
                for i in range(2, arrow_len):
                    ax = int(cx + i * math.sin(angle_rad))
                    ay = int(cy - i * math.cos(angle_rad) * 0.5)
                    if 0 <= ax < w and 0 <= ay < h:
                        buffer[ay][ax] = '●'
                
                # Draw arrow head
                end_x = int(cx + arrow_len * math.sin(angle_rad))
                end_y = int(cy - arrow_len * math.cos(angle_rad) * 0.5)
                arrows = ['▲', '◥', '▶', '◢', '▼', '◣', '◀', '◤']
                arrow_char = arrows[int((bearing + 22.5) / 45) % 8]
                if 0 <= end_x < w and 0 <= end_y < h:
                    buffer[end_y][end_x] = arrow_char
                
                # Draw destination label
                dist_str = f"{distance:.1f}km" if distance >= 1 else f"{int(distance * 1000)}m"
                label = f" {self.dest_name[:8]} ({dist_str})"
                label_x = min(end_x + 1, w - len(label))
                if 0 <= end_y < h:
                    for i, c in enumerate(label):
                        if 0 <= label_x + i < w:
                            buffer[end_y][label_x + i] = c
        
        # Convert to Rich Text
        for row in buffer:
            text.append(''.join(row) + '\n', style=Style(color="green"))
        
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
        text.append("  ↑↓ Select  |  Enter Confirm  |  Esc Cancel\n", style=Style(color="cyan", dim=True))
        return text


class InfoWidget(Static):
    """Shows navigation information."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.gps_status: str = "Press 'r' to get GPS location"
        self.my_lat: Optional[float] = None
        self.my_lon: Optional[float] = None
        self.dest_name: Optional[str] = None
        self.distance: float = 0
        self.bearing: float = 0
    
    def update_info(
        self,
        gps_status: str,
        my_lat: Optional[float],
        my_lon: Optional[float],
        dest_name: Optional[str],
        distance: float,
        bearing: float
    ) -> None:
        self.gps_status = gps_status
        self.my_lat = my_lat
        self.my_lon = my_lon
        self.dest_name = dest_name
        self.distance = distance
        self.bearing = bearing
    
    def render(self) -> Text:
        text = Text()
        
        text.append("┌─ NAVIGATION ─────────────────────────────────────────┐\n", style=Style(color="green"))
        
        # GPS Status
        if "Excellent" in self.gps_status or "Good" in self.gps_status:
            text.append(f"│ {self.gps_status:<53} │\n", style=Style(color="green", bold=True))
        elif "Fair" in self.gps_status or "IP" in self.gps_status:
            text.append(f"│ {self.gps_status:<53} │\n", style=Style(color="yellow"))
        else:
            text.append(f"│ {self.gps_status:<53} │\n", style=Style(color="cyan"))
        
        # My Location
        if self.my_lat is not None and self.my_lon is not None:
            loc_str = f"YOUR LOCATION: {self.my_lat:.6f}, {self.my_lon:.6f}"
            text.append(f"│ {loc_str:<53} │\n", style=Style(color="white"))
        else:
            text.append(f"│ {'YOUR LOCATION: Unknown':<53} │\n", style=Style(color="yellow"))
        
        # Destination
        if self.dest_name:
            text.append(f"│ DESTINATION: {self.dest_name[:40]:<40} │\n", style=Style(color="white"))
            
            dist_str = f"{self.distance:.2f} km" if self.distance >= 1 else f"{int(self.distance * 1000)} m"
            dir_str = bearing_to_direction(self.bearing)
            nav_str = f"DISTANCE: {dist_str}  |  DIRECTION: {self.bearing:.0f}° ({dir_str})"
            text.append(f"│ {nav_str:<53} │\n", style=Style(color="green"))
            
            if self.distance < 0.1:
                text.append(f"│ {'🎉 YOU HAVE ARRIVED! 🎉':^53} │\n", style=Style(color="yellow", bold=True))
        else:
            text.append(f"│ {'DESTINATION: Not set (press d to search)':<53} │\n", style=Style(color="grey50"))
            text.append(f"│ {'':<53} │\n", style=Style(color="green"))
        
        text.append("└───────────────────────────────────────────────────────┘\n", style=Style(color="green"))
        
        return text


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class TermGPSApp(App):
    """
    TermGPS - Terminal GPS Navigation Application
    
    NO AUTOMATIC MOVEMENT - display only updates on user action.
    """
    
    TITLE = "TermGPS"
    
    CSS = """
    Screen {
        background: #000000;
    }
    
    #radar-container {
        height: 55%;
        border: heavy green;
        background: #000000;
    }
    
    #search-box {
        display: none;
        height: auto;
        border: solid yellow;
        background: #111100;
        padding: 1;
    }
    
    #search-box.visible {
        display: block;
    }
    
    #search-input {
        width: 100%;
        background: #222200;
        color: #00ff00;
        border: solid green;
    }
    
    #info-panel {
        height: auto;
        padding: 0 1;
    }
    
    Static {
        color: #00ff00;
    }
    
    Footer {
        background: #001100;
    }
    
    Header {
        background: #001100;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "open_search", "Search"),
        Binding("r", "refresh_gps", "GPS"),
        Binding("c", "clear_dest", "Clear"),
        Binding("escape", "close_search", "Cancel", show=False),
        Binding("enter", "confirm_search", "OK", show=False),
        Binding("up", "move_up", "↑", show=False),
        Binding("down", "move_down", "↓", show=False),
    ]
    
    def __init__(self):
        super().__init__()
        # State
        self.my_lat: Optional[float] = None
        self.my_lon: Optional[float] = None
        self.gps_status: str = "Press 'r' to get your GPS location"
        self.dest_lat: Optional[float] = None
        self.dest_lon: Optional[float] = None
        self.dest_name: Optional[str] = None
        self.search_active: bool = False
        self._last_query: str = ""
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        self.radar = RadarWidget(id="radar")
        self.suggestions = SuggestionsWidget(id="suggestions")
        self.info = InfoWidget(id="info-panel")
        self.search_input = Input(
            placeholder="Type destination (e.g., 'Taj Mahal', 'Mumbai Airport')...",
            id="search-input"
        )
        
        with Container(id="search-box"):
            yield Label("🔍 Search Destination:")
            yield self.search_input
            yield self.suggestions
        
        with Container(id="radar-container"):
            yield self.radar
        
        yield self.info
        yield Footer()
    
    def on_mount(self) -> None:
        """Called when app starts - NO automatic updates."""
        self._refresh_display()
        self.notify("Press 'r' for GPS, 'd' to search destination")
    
    def _refresh_display(self) -> None:
        """Refresh all displays with current data."""
        distance = 0.0
        bearing = 0.0
        
        if self.my_lat and self.dest_lat:
            distance = haversine_distance(self.my_lat, self.my_lon, self.dest_lat, self.dest_lon)
            bearing = calculate_bearing(self.my_lat, self.my_lon, self.dest_lat, self.dest_lon)
        
        self.radar.set_my_position(self.my_lat, self.my_lon)
        if self.dest_lat:
            self.radar.set_destination(self.dest_lat, self.dest_lon, self.dest_name or "")
        
        self.info.update_info(
            self.gps_status,
            self.my_lat, self.my_lon,
            self.dest_name,
            distance, bearing
        )
        
        self.radar.refresh()
        self.info.refresh()
    
    # === ACTIONS ===
    
    def action_refresh_gps(self) -> None:
        """Get GPS location - only when user presses 'r'."""
        self.notify("📍 Getting GPS location...")
        self.my_lat, self.my_lon, self.gps_status = get_macos_location()
        self._refresh_display()
        
        if self.my_lat:
            self.notify(f"Location: {self.my_lat:.4f}, {self.my_lon:.4f}")
    
    def action_open_search(self) -> None:
        """Open search box."""
        self.search_active = True
        self.query_one("#search-box").add_class("visible")
        self.search_input.value = ""
        self.suggestions.clear()
        self.search_input.focus()
    
    def action_close_search(self) -> None:
        """Close search box."""
        self.search_active = False
        self.query_one("#search-box").remove_class("visible")
        self.suggestions.clear()
        self.radar.focus()
    
    def action_confirm_search(self) -> None:
        """Confirm search selection."""
        if self.search_active:
            selected = self.suggestions.get_selected()
            if selected:
                self.dest_lat = selected["lat"]
                self.dest_lon = selected["lon"]
                self.dest_name = selected["name"].split(",")[0][:20]
                self.radar.set_destination(self.dest_lat, self.dest_lon, self.dest_name)
                self._refresh_display()
                self.notify(f"📍 Destination: {self.dest_name}")
            
            self.action_close_search()
    
    def action_clear_dest(self) -> None:
        """Clear destination."""
        self.dest_lat = None
        self.dest_lon = None
        self.dest_name = None
        self.radar.clear_destination()
        self._refresh_display()
        self.notify("Destination cleared")
    
    def action_move_up(self) -> None:
        if self.search_active:
            self.suggestions.move_selection(-1)
            self.suggestions.refresh()
    
    def action_move_down(self) -> None:
        if self.search_active:
            self.suggestions.move_selection(1)
            self.suggestions.refresh()
    
    # === INPUT HANDLING ===
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Search as user types."""
        if event.input.id == "search-input":
            query = event.value.strip()
            if len(query) >= 3 and query != self._last_query:
                self._last_query = query
                results = search_places(query)
                self.suggestions.set_items(results)
                self.suggestions.refresh()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter in search box."""
        if event.input.id == "search-input":
            self.action_confirm_search()


# =============================================================================
# ENTRY POINT
# =============================================================================

def run():
    """Run the TermGPS application."""
    print("\n" + "=" * 50)
    print("  TermGPS - Terminal GPS Navigation")
    print("=" * 50)
    print("\nControls:")
    print("  r = Get GPS location")
    print("  d = Search destination")
    print("  c = Clear destination")
    print("  Mouse drag = Pan view")
    print("  q = Quit")
    print("\n" + "=" * 50 + "\n")
    
    app = TermGPSApp()
    app.run()


if __name__ == "__main__":
    run()
