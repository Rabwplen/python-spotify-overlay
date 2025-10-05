import os
import sys
import time
import json
import ctypes
import atexit
import requests
import textwrap
import keyboard
import threading
import webbrowser
from pathlib import Path

import tkinter as tk
import customtkinter as ctk

import pystray
from pystray import MenuItem

from PIL import Image, ImageDraw, ImageTk
from io import BytesIO

import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyPKCE

from http.server import HTTPServer, BaseHTTPRequestHandler


def file_path(relative_path):
    try:
        base_path = sys._MEIPASS  # work as.exe
    except AttributeError:
        base_path = os.path.abspath(".")  # work as .py
    return os.path.join(base_path, relative_path)

def get_data_path(filename: str) -> str:
    if os.name == "nt":  # Windows
        base = os.path.join(os.getenv("APPDATA") or os.getenv("LOCALAPPDATA"), "SpotifyOverlayInPython")
    else:
        base = os.path.join(os.path.expanduser("~"), ".config", "SpotifyOverlayInPython")

    os.makedirs(base, exist_ok=True)  # create, if none exists
    return os.path.join(base, filename)


# === === === Spotify App Configuration === === ===
client_id = "a1b19019bc5f4e0c916ad8b243f1e2f5"
redirect_uri = "http://127.0.0.1:8888/callback"
scope = "user-read-private user-read-playback-state"

auth_code = None # Intermediate variable for storing code

# Server for reading code from redirect
class AuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        if "/callback?" in self.path:
            code = self.path.split("code=")[-1].split("&")[0]
            auth_code = code

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            # Download HTML from a file
            html_path = Path(file_path("auth_success.html"))
            if html_path.exists():
                with open(html_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b"<h1>Logged in</h1>")
                self.wfile.write(b"<h3>Error: HTML file not found</h3>")

# Starts the server in a separate thread
def run_server():
    server = HTTPServer(("localhost", 8888), AuthHandler)
    server.handle_request()

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

# Authorization
cache_path = get_data_path(".cache")
auth_manager = SpotifyPKCE(
    client_id=client_id,
    redirect_uri=redirect_uri,
    scope=scope,
    cache_path=cache_path
)

token_info = auth_manager.get_cached_token()

if not token_info:
    auth_url = auth_manager.get_authorize_url()
    webbrowser.open(auth_url)
    print("Waiting for authorization via browser...")

    server_thread.join() # waiting for the code (the server will receive it itself)
 
    code = auth_code
    token_info = auth_manager.get_access_token(code)

sp = spotipy.Spotify(auth_manager=auth_manager)
try:
    print("-< Authorized as:", sp.current_user()['display_name'],">-")
except:
    print("-< You are offline >-")





# === === === < Main Code > === === ===
def load_settings():
    try:
        with open(get_data_path("settings.json"), "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    
def save_settings(data):
    print("Settings saved.")
    with open(get_data_path("settings.json"), "w") as f:
        json.dump(data, f, indent=4)

def quit_app():
    print("bye!")
    # completes all cycles so that the program closes completely
    if hasattr(app, "update_song_info_after_id") and app.update_song_info_after_id:
        app.after_cancel(app.update_song_info_after_id)

    if hasattr(app, "revert_timer") and app.revert_timer:
        app.revert_timer.cancel()


    # saving app window position
    geo = app.geometry()
    if "+" in geo: # format type: '350x100+30+30'
        parts = geo.split("+")
        app_position_X = int(parts[1])
        app_position_Y = int(parts[2])
    else:
        app_position_X = app_position_Y = 30  # дефолт

    save_settings({ # saves all settings and some data
        "default_opacity": app.default_opacity,
        "hover_opacity": app.hover_opacity,
        "fade_delay": app.fade_delay,
        "fade_duration": app.fade_duration,
        "always_on_top": app.always_on_top,
        "can_drag": app.can_drag,
        "click_through": app.click_through,
        "window_position_x": app_position_X,
        "window_position_y": app_position_Y
        })
    
    app.destroy()

def hide_from_taskbar(window):
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_APPWINDOW = 0x00040000

    hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
    ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ex_style = ex_style & ~WS_EX_APPWINDOW | WS_EX_TOOLWINDOW
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
    ctypes.windll.user32.ShowWindow(hwnd, 5)
    ctypes.windll.user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                                      0x0001 | 0x0002 | 0x0020 | 0x0040)

def set_click_through(window, enable: bool):
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_LAYERED = 0x00080000

    hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
    styles = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

    if enable:
        styles |= WS_EX_LAYERED | WS_EX_TRANSPARENT
    else:
        styles &= ~WS_EX_TRANSPARENT

    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, styles)

def toggle_click_through():
    app.click_through = not app.click_through
    set_click_through(app, app.click_through)

    if app.click_through == True:
        app.close_button.place_forget()
        app.settings_button.place_forget()
        app.resize_button.place_forget()
    elif app.click_through == False:
        if app.resize_type == 1:
            app.close_button.place(**app.POS_close_button)
            app.settings_button.place(**app.POS_settings_button)
            app.resize_button.place(**app.POS_resize_button)
        elif app.resize_type == 2:
            app.close_button.place(**app.POS_close_button)
            app.settings_button.place(**app.POS_settings_button)
            app.resize_button.place(**app.POS_resize_button)
        elif app.resize_type == 3:
            app.close_button.place(rely=0.865, relx=1, x=-15, y=0, anchor="center")
            app.settings_button.place(rely=0.865, relx=0, x=15, y=0, anchor="center")
            app.resize_button.place(rely=0.865, relx=0, x=55, y=0, anchor="center")

    update_tray_menu()

def apply_gradient_alpha(image: Image.Image, direction: str = "left_to_right") -> Image.Image:
    w, h = image.size
    gradient = Image.new('L', (w, 1), color=0xFF)
    draw = ImageDraw.Draw(gradient)

    for x in range(w):
        alpha = int(255 * (x / w)) if direction == "left_to_right" else int(255 * ((w - x) / w))
        draw.point((x, 0), fill=alpha)

    alpha_mask = gradient.resize((w, h))
    image.putalpha(alpha_mask)
    return image

# === Tray functions ===
tray_icon = None

def create_tray():
    image = Image.open(file_path("app-icon.png")).resize((32, 32))
    show_hide_text = "Hide Overlay" if not app.hidden else "Show Overlay"
    click_throuth_text = "Disable Click-Through" if app.click_through else "Enable Click-Through"

    global tray_icon
    tray_icon = pystray.Icon("spotify_overlay", image, "Spotify Overlay", menu=pystray.Menu(
        pystray.MenuItem(show_hide_text, tray_on_show_or_hide),
        pystray.MenuItem(click_throuth_text, toggle_click_through),
        pystray.MenuItem("Open Settings", app.open_settings),
        pystray.MenuItem("Close App", quit_app)
    ))
    tray_icon.run()

def update_tray_menu():
    global tray_icon
    if tray_icon is None:
        return  # tray_icon not created yet

    show_hide_text = "Hide Overlay" if not app.hidden else "Show Overlay"
    click_throuth_text = "Disable Click-Through" if app.click_through else "Enable Click-Through"

    tray_icon.menu = pystray.Menu(
        pystray.MenuItem(show_hide_text, tray_on_show_or_hide),
        pystray.MenuItem(click_throuth_text, toggle_click_through),
        pystray.MenuItem("Open Settings", app.open_settings),
        pystray.MenuItem("Close App", quit_app)
    )
    tray_icon.update_menu()

def tray_on_show_or_hide():
    print(app.hidden)
    if app.hidden == True:
        app.deiconify()
    elif app.hidden == False:
        app.withdraw()
    app.hidden = not app.hidden
    print(app.hidden)
    update_tray_menu()





# === Main Class ===
class Overlay(ctk.CTk):
    current = sp.current_playback()
    def format_time(self, ms):
        seconds = int(ms / 1000)
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"

    def update_song_info(self):
        try:
            current = sp.current_playback()
        except:
            print("what?")

        if current and current["is_playing"]:
            track = current['item']
            title = track['name']
            middleTitle = textwrap.shorten(title, width=35, placeholder="...")
            shortTitle = textwrap.shorten(title, width=32, placeholder="...")
            shortestTitle = textwrap.shorten(title, width=30, placeholder="...")
            artist = track['artists'][0]['name']
            album = track['album'].get('name')
            track_duration = "0:00 / 0:00"
            images = track['album'].get('images', [])
            image_url = images[0]['url'] if images else None
            progress_ms = current["progress_ms"]
            duration_ms = current["item"]["duration_ms"]
            self.track_total_duration = duration_ms
            track_duration = f"{self.format_time(progress_ms)} / {self.format_time(duration_ms)}"
                
            if self.resize_type == 1:
                # Updates all label (new version for optimization (does not work))
                if self.title_label.cget("text") != "Now playing:":
                    print("Update < title_label > to 'Now playing:'")
                    self.title_label.configure(text="Now playing:")
                    self.spotify_track_duration_slider.place(**self.POS_spotify_track_duration_slider) # its not supposed to be here, but ok
               
                middle_spotify_title_new = f"{middleTitle}"
                if self.spotify_title.cget("text") != middle_spotify_title_new:
                    print("Update < spotify_title > to < middleTitle >")
                    self.spotify_title.configure(text=middle_spotify_title_new)

                spotify_artist_new = f"{artist}"
                if self.spotify_artist.cget("text") != spotify_artist_new:
                    print("Update < spotify_artist > to < artist >")
                    self.spotify_artist.configure(text=spotify_artist_new)
                
                if self.spotify_image.place_info() == {}:
                    print("cho")
                    self.spotify_image.place(**self.POS_spotify_image)

                self.spotify_track_duration.configure(text=track_duration)

                if self.spotify_playPause_track_button.cget("text") != "||":
                    print("Update < spotify_playPause_track_button > to '||'")
                    self.spotify_playPause_track_button.configure(text="||", font=ctk.CTkFont(size=11, weight="bold"))

            elif self.resize_type == 2:
                short_spotify_title_new = f"{shortTitle}"
                if self.spotify_title.cget("text") != short_spotify_title_new:
                    print("Update < spotify_title > to < shortTitle >")
                    self.spotify_title.configure(text=f"{shortTitle}")
                
                if self.spotify_track_duration_slider.place_info() == {}:
                    self.spotify_track_duration_slider.place(rely=0.88, relx=0.5, anchor="center")
                    
                self.spotify_artist.configure(text=f"{artist} • {track_duration}")
            elif self.resize_type == 3:
                spotify_title_new = f"{title}"
                if self.spotify_title.cget("text") != spotify_title_new:
                    print("Update < spotify_title > to < title >")
                    self.spotify_title.configure(text=spotify_title_new)

                # middle_spotify_title_new = f"{middleTitle}"
                # if self.spotify_title.cget("text") != middle_spotify_title_new:
                #     print("Update < spotify_title > to < middleTitle >")
                #     self.spotify_title.configure(text=middle_spotify_title_new)

                # shortest_spotify_title_new = f"{shortestTitle}"
                # if self.spotify_title.cget("text") != shortest_spotify_title_new:
                #     print("Update < spotify_title > to < shortestTitle >")
                #     self.spotify_title.configure(text=f"{shortestTitle}")

                spotify_artist_new = f"{artist}"
                if self.spotify_artist.cget("text") != spotify_artist_new:
                    print("Update < spotify_artist > to < artist >")
                    self.spotify_artist.configure(text=spotify_artist_new)

                spotify_album_new = f"{album}"
                if self.spotify_album.cget("text") != spotify_album_new:
                    print("Update < spotify_album > to < album >")
                    self.spotify_album.configure(text=spotify_album_new)
                
                if self.spotify_image.place_info() == {}:
                    print("cho 3")
                    self.spotify_image.place(rely=0, relx=1, anchor="ne")
                
                if self.spotify_playPause_track_button.cget("text") != "||":
                    print("Update < spotify_playPause_track_button > to '||'")
                    self.spotify_playPause_track_button.configure(text="||", font=ctk.CTkFont(size=11, weight="bold"))
                    self.spotify_track_duration_slider.place(rely=0.955, relx=0.5, anchor="center")
                
                if self.spotify_track_duration_slider.place_info == {}:
                    print("cho 3 but slider (???)")
                    self.spotify_track_duration_slider.place(rely=0.955, relx=0.5, anchor="center")
                    self.spotify_track_duration_slider.configure(width=310)

                self.spotify_track_duration_progress.configure(text=self.format_time(progress_ms))
                self.spotify_track_duration_total.configure(text=self.format_time(duration_ms))
                        

            # Update slider
            if duration_ms > 0:
                slider_value = (progress_ms / duration_ms) * 100
                self.spotify_track_duration_slider.set(slider_value)

            # Get image
            def update_album_cover(image_url):
                if not image_url:
                    if self.spotify_image.cget("image") is not self.default_album_cover and self.spotify_image.cget("image") is not self.default_album_cover_gradient or self.current_image_url == "idk123":
                        if self.resize_type != 3:
                            print("Update < spotify_image > to default album cover < self.default_album_cover >")
                            self.spotify_image.configure(image=self.default_album_cover)
                            self.spotify_image.image = self.default_album_cover
                        elif self.resize_type == 3:
                            print("Update < spotify_image > to default album cover < self.default_album_cover_gradient >")
                            self.spotify_image.configure(image=self.default_album_cover_gradient)
                            self.spotify_image.image = self.default_album_cover_gradient
                        self.current_image_url = None
                    return

                if image_url == self.current_image_url and self.resize_type != 3:
                    return # same image, do nothing
                
                if image_url != self.current_image_url:
                    print("Update < spotify_image > to < image_url >")

                    self.current_image_url = image_url

                    response = requests.get(image_url, timeout=2)

                    if self.resize_type != 3:
                        # Small version with rounded corners
                        image_data = Image.open(BytesIO(response.content)).resize((60, 60)).convert("RGBA")

                        mask = Image.new("L", (60, 60), 0)
                        draw = ImageDraw.Draw(mask)
                        draw.rounded_rectangle((0, 0, 60, 60), radius=10, fill=255)
                        image_data.putalpha(mask)

                        final_image = ctk.CTkImage(light_image=image_data, size=(60, 60))
                        self.spotify_image.configure(image=final_image)
                        self.spotify_image.image = final_image
                    elif self.resize_type == 3:
                        # Big version with gradient transparency
                        image_data = Image.open(BytesIO(response.content)).resize((175, 175)).convert("RGBA")

                        # Apply alpha gradient
                        image_data = apply_gradient_alpha(image_data, direction="left_to_right")

                        final_image = ctk.CTkImage(light_image=image_data, size=(175, 175))
                        self.spotify_image.configure(image=final_image)
                        self.spotify_image.image = final_image

            update_album_cover(image_url)

        else: # if nothing is playing right now
            if self.title_label.cget("text") != "Paused." or self.spotify_playPause_track_button.cget("text") != "▶":
                print("Update all ui elements to < 'non playing' >")
                self.title_label.configure(text="Paused.")
                # self.spotify_title.configure(text="")
                # self.spotify_artist.configure(text="")
                # self.spotify_track_duration.configure(text="")
                # self.spotify_image.configure(image=None)
                # self.spotify_image.image = None
                # self.current_image_url = None
                # image_url = None
                # self.spotify_image.place_forget()
                # self.spotify_track_duration_slider.place_forget()
                self.spotify_playPause_track_button.configure(text="▶", font=ctk.CTkFont(size=10))
    
    def change_resolution(self):
        self.current_image_url = "idk123"

        if app.resize_type == 1:
            print("Overlay size: 2")

            app.geometry("350x55")
            app.resize_type = 2

            if app.click_through == False:
                app.close_button.place(**app.POS_close_button)
                app.settings_button.place(**app.POS_settings_button)
                app.resize_button.place(**app.POS_resize_button)

            app.control_frame.place_forget()
            app.title_label.place_forget()
            app.spotify_title.place(rely=0, relx=0.01)
            app.spotify_artist.place(rely=0.4, relx=0.01)
            app.spotify_album.place_forget()
            app.spotify_account_name.place_forget()
            app.spotify_image.place_forget()
            app.spotify_track_duration.place_forget() #.place(rely=0.64, relx=0.78)
            app.spotify_track_duration_slider.place(rely=0.88, relx=0.5, anchor="center")
            app.spotify_track_duration_slider.configure(width=350, bg_color="#0F0F0F")
            app.spotify_previous_track_button.place_forget()
            app.spotify_playPause_track_button.place_forget()
            app.spotify_next_track_button.place_forget()
        elif app.resize_type == 2:
            print("Overlay size: 3")

            app.geometry("420x220")
            app.resize_type = 3

            if app.click_through == False:
                app.close_button.place(rely=0.855, relx=1, x=-15, y=0, anchor="center")
                app.settings_button.place(rely=0.855, relx=0, x=15, y=0, anchor="center")
                app.resize_button.place(rely=0.855, relx=0, x=45, y=0, anchor="center")
            
            app.control_frame.place(relx=0, rely=1-0.203, relwidth=1, relheight=0.203)
            app.title_label.place_forget()
            app.spotify_title.place(rely=0, relx=0.01)
            app.spotify_artist.place(rely=0.1, relx=0.01)
            app.spotify_album.place(rely=0.18, relx=0.01)
            app.spotify_account_name.place(rely=0.64, relx=0.01)
            app.spotify_image.place(rely=0, relx=1, anchor="ne")
            app.spotify_track_duration.place_forget()
            app.spotify_track_duration_slider.place(rely=0.955, relx=0.5, anchor="center")
            app.spotify_track_duration_slider.configure(width=310, bg_color="#000000") 
            app.spotify_track_duration_progress.place(rely=0.92, relx=0.02, anchor="nw")
            app.spotify_track_duration_total.place(rely=0.92, relx=0.98, anchor="ne")
            app.spotify_previous_track_button.place(rely=0.87, relx=0.43, anchor="center")
            app.spotify_playPause_track_button.place(rely=0.87, relx=0.5, anchor="center")
            app.spotify_next_track_button.place(rely=0.87, relx=0.57, anchor="center")
        elif app.resize_type == 3:
            print("Overlay size: 1")

            app.geometry("350x100")
            app.resize_type = 1

            if app.click_through == False:
                app.close_button.place(**app.POS_close_button)
                app.settings_button.place(**app.POS_settings_button)
                app.resize_button.place(**app.POS_resize_button)
            
            app.control_frame.place_forget()
            app.title_label.place(**app.POS_title_label)
            app.spotify_title.place(rely=0.3, relx=0.2)
            app.spotify_artist.place(rely=0.52, relx=0.2)
            app.spotify_album.place_forget()
            app.spotify_account_name.place_forget()
            app.spotify_image.place(**app.POS_spotify_image)
            app.spotify_track_duration.place(**app.POS_spotify_track_duration)
            app.spotify_track_duration_progress.place_forget()
            app.spotify_track_duration_total.place_forget()
            app.spotify_track_duration_slider.place(**app.POS_spotify_track_duration_slider)
            app.spotify_track_duration_slider.configure(width=110, bg_color="#0F0F0F")
            app.spotify_previous_track_button.place(rely=0.75, relx=0.825, anchor="ne")
            app.spotify_playPause_track_button.place(rely=0.75, relx=0.90, anchor="ne")
            app.spotify_next_track_button.place(rely=0.75, relx=0.985, anchor="ne")

        self.update_song_info()

            

    

    def __init__(self):
        super().__init__()
        self.settings = load_settings()

        # Changeable Variables

        # variables that are saved
        self.default_opacity = 0.3
        self.hover_opacity = 0.8
        self.fade_delay = 1
        self.fade_duration = 0.2
        self.inside = False
        self.revert_timer = None
        self.always_on_top = True
        self.can_drag = True
        self.click_through = False

        # variables that are not saved
        self.hidden = False

        # Extract the settings or use the default
        load_settings()
        self.default_opacity = self.settings.get("default_opacity", 0.3)
        self.hover_opacity = self.settings.get("hover_opacity", 0.8)
        self.fade_delay = self.settings.get("fade_delay", 1)
        self.fade_duration = self.settings.get("fade_duration", 0.2)
        self.always_on_top = self.settings.get("always_on_top", True)
        self.can_drag = self.settings.get("can_drag", True)
        self.click_through = self.settings.get("click_through", False)
        app_position_X = self.settings.get("window_position_x", 30)
        app_position_Y = self.settings.get("window_position_y", 30)
        save_settings({
            "default_opacity": self.default_opacity,
            "hover_opacity": self.hover_opacity,
            "fade_delay": self.fade_delay,
            "fade_duration": self.fade_duration,
            "always_on_top": self.always_on_top,
            "can_drag": self.can_drag,
            "click_through": self.click_through
            })


        # UIs Positions
        self.POS_title_label = {'rely': 0, 'relx': 0.01, 'anchor': "nw"}
        self.POS_close_button = {'relx': 1, 'rely': 0, 'x': -2, 'y': 3, "anchor": "ne"}
        self.POS_settings_button = {'relx': 1, 'rely': 0, 'x': -34, 'y': 3, "anchor": "ne"}
        self.POS_resize_button = {'relx': 1, 'rely': 0, 'x': -66, 'y': 3, "anchor": "ne"}
        self.POS_spotify_image = {'rely': 0.33, 'relx': 0.015, 'anchor': "nw"}
        self.POS_spotify_track_duration = {'rely': 0.77, 'relx': 0.2, 'anchor': "nw"} # rely=0.77, relx=0.2
        self.POS_spotify_track_duration_slider = {'rely': 0.8, 'relx': 0.75, 'anchor': "ne"}


        # Other Variables
        self.title("Spotify Overlay")
        self.geometry(f"350x100+{app_position_X}+{app_position_Y}")
        self.resize_type = 1
        self.overrideredirect(True)
        self.attributes("-topmost", self.always_on_top)
        self.attributes("-alpha", self.default_opacity)
        self.after(250, lambda: hide_from_taskbar(self))
        set_click_through(self, self.click_through)

        self.settings_openned = False

        self.track_total_duration = None
        self.current_image_url = None

        self.can_update_song_info = True
        self.update_song_info_after_id = None


        # Create default album cover and default album cover with gradient
        self.default_album_cover = None
        self.default_album_cover_gradient = None
        default_album_cover_path = Path(file_path("album-cover.jpeg"))

        if os.path.exists(default_album_cover_path):
            # Create a mask with rounded edges
            normal_image = Image.open(default_album_cover_path).resize((60, 60)).convert("RGBA")
            normal_mask = Image.new("L", (60, 60), 0)
            normal_draw = ImageDraw.Draw(normal_mask)
            normal_draw.rounded_rectangle((0, 0, 60, 60), radius=10, fill=255)
            normal_image.putalpha(normal_mask)

            # Create a mask with gradient
            gradient_image = Image.open(default_album_cover_path).resize((175, 175)).convert("RGBA")
            gradient_image = apply_gradient_alpha(gradient_image, direction="left_to_right")

            # Applying all masks for default album cover
            self.default_album_cover = ctk.CTkImage(light_image=normal_image, size=(60, 60))
            self.default_album_cover_gradient = ctk.CTkImage(light_image=gradient_image, size=(175, 175))
        else:
            print("!: album-cover.jpeg not found")
        
        

        # Commands
        def on_slider_change(value):
            current_seconds = int(value)
            total_seconds = self.track_total_duration

            current_minutes = current_seconds // 60
            current_secs = current_seconds % 60
            track_duration = self.format_time(total_seconds)

            new_position_ms = int((value / 100) * self.track_total_duration)

            #try:
            #    current = sp.current_playback()
            #    if current and current["item"]:
            #        progress_ms = current["progress_ms"]
            #        duration_ms = current["item"]["duration_ms"]
            #        self.track_total_duration = duration_ms

            #        # Оновлюємо слайдер
            #        if duration_ms > 0:
            #            slider_value = (progress_ms / duration_ms) * 100
            #            self.spotify_track_duration_slider.set(slider_value)
            #except Exception as e:
            #    print("Error update track: ", e)

            self.spotify_track_duration.configure(text=f"{current_minutes}:{current_secs:02d} / {track_duration}")

            try:
                sp.seek_track(new_position_ms)
            except spotipy.exceptions.SpotifyException as e:
                if "PREMIUM_REQUIRED" in str(e):
                    print("Rewind is only available for Spotify Premium.")
                else:
                    print("Another error when rewinding:", e)

        # === The Script ===

        # Background
        self.background = ctk.CTkFrame(self, fg_color="#0F0F0F")
        self.background.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Control Panel For 3-rd size mode
        self.control_frame = ctk.CTkFrame(self.background, fg_color="#000000")

        # Title
        self.title_label = ctk.CTkLabel(self.background, text="Nothing is playing right now.", font=ctk.CTkFont(size=16, weight="bold"), text_color="white")
        self.title_label.place(**self.POS_title_label)
        self.title_label.bind("<Button-1>", self.start_move)
        self.title_label.bind("<B1-Motion>", self.on_motion)

        # Close window button
        self.close_button = ctk.CTkButton(self.background, text="X", font=ctk.CTkFont(size=12, weight="bold"),
                                       width=25, height=25, corner_radius=5,
                                       fg_color="#180000", hover_color="#900", text_color="white",
                                       command=quit_app)
        self.close_button.place(**self.POS_close_button)

        # Settings button
        self.settings_icon = ctk.CTkImage(light_image=Image.open(file_path('settings-icon.png')), size=(13, 13))

        self.settings_button = ctk.CTkButton(self.background, text="", font=ctk.CTkFont(size=13, weight="bold"),
                                        width=25, height=25, corner_radius=5, image=self.settings_icon,
                                       fg_color="#202020", hover_color="#3D3D3D", text_color="white",
                                       command=self.open_settings)
        self.settings_button.place(**self.POS_settings_button)

        # Change resolution button
        self.resize_icon = ctk.CTkImage(light_image=Image.open(file_path('resize-icon.png')), size=(13, 13))

        self.resize_button = ctk.CTkButton(self.background, text="", font=ctk.CTkFont(size=13, weight="bold"),
                                        width=25, height=25, corner_radius=5, image=self.resize_icon,
                                       fg_color="#202020", hover_color="#3D3D3D", text_color="white",
                                       command=self.change_resolution)
        self.resize_button.place(**self.POS_resize_button)

        # === Spotify ===

        # Track title
        self.spotify_title = ctk.CTkLabel(self.background, text="",
                                         font=ctk.CTkFont(size=16, weight="bold", family="Lexend"), text_color="white")
        self.spotify_title.place(rely=0.3, relx=0.2)
        self.spotify_title.bind("<Button-1>", self.start_move)
        self.spotify_title.bind("<B1-Motion>", self.on_motion)

        # Track artist
        self.spotify_artist = ctk.CTkLabel(self.background, text="",
                                         font=ctk.CTkFont(size=14, family="Courier New"), text_color="#D1D1D1",
                                         width=10, height=20)
        self.spotify_artist.place(rely=0.52, relx=0.2)

        # Track album
        self.spotify_album = ctk.CTkLabel(self.background, text="",
                                     font=ctk.CTkFont(size=13, family="Courier New", slant="italic"), text_color="#AAAAAA",
                                     height=8)

        # Spotify account name
        self.spotify_account_name = ctk.CTkLabel(self.background, text=f"Logged as:\n{sp.current_user()['display_name']}",
                                                 font=ctk.CTkFont(size=12, family="Courier New", weight="bold"),
                                                 text_color="#D1D1D1", height=13)

        # Track image
        self.spotify_image = ctk.CTkLabel(self.background, text="")
        self.spotify_image.place(**self.POS_spotify_image)

        # Track duration
        self.spotify_track_duration = ctk.CTkLabel(self, text="0:00 / 0:00", font=ctk.CTkFont(size=13, family="Comic Sans"), text_color="light gray", height=12, fg_color="#0F0F0F")
        self.spotify_track_duration.place(**self.POS_spotify_track_duration)

        self.spotify_track_duration_progress = ctk.CTkLabel(self, text="0:00", font=ctk.CTkFont(size=13, family="Comic Sans"), text_color="light gray", height=12, fg_color="#000000")
        self.spotify_track_duration_total = ctk.CTkLabel(self, text="0:00", font=ctk.CTkFont(size=13, family="Comic Sans"), text_color="light gray", height=12, fg_color="#000000")

        self.spotify_track_duration_slider = ctk.CTkSlider(self, from_=0, to=100, state="disabled", command=on_slider_change,
                                                           width=110, height=10,
                                                           bg_color="#0F0F0F", fg_color="#303030", progress_color="#FFFFFF",
                                                           button_color="#FFFFFF", button_hover_color="#0F0F0F")
        # self.spotify_track_duration_slider.place(**self.POS_spotify_track_duration_slider)

        # Previous Track
        def previous_track():
            keyboard.send("previous track")

        self.spotify_previous_track_button = ctk.CTkButton(self.background, text="|◀", font=ctk.CTkFont(size=10),
                                                            width=20, height=20, corner_radius=5,
                                                            fg_color="#202020", hover_color="#3D3D3D", text_color="white",
                                                            command=previous_track)
        self.spotify_previous_track_button.place(rely=0.75, relx=0.825, anchor="ne")

        # Resume/Pause Track
        def resume_pause_track():
            keyboard.send("play/pause")

        self.spotify_playPause_track_button = ctk.CTkButton(self.background, text="▶", font=ctk.CTkFont(size=11, weight="bold"),
                                                            width=20, height=20, corner_radius=5,
                                                            fg_color="#FFF", hover_color="light gray", text_color="#202020",
                                                            command=resume_pause_track)
        self.spotify_playPause_track_button.place(rely=0.75, relx=0.90, anchor="ne")

        # Next Track
        def next_track():
            keyboard.send("next track")

        self.spotify_next_track_button = ctk.CTkButton(self.background, text="▶|", font=ctk.CTkFont(size=10),
                                                            width=20, height=20, corner_radius=5,
                                                            fg_color="#202020", hover_color="#3D3D3D", text_color="white",
                                                            command=next_track)
        self.spotify_next_track_button.place(rely=0.75, relx=0.985, anchor="ne")


        # Other
        self.monitor_mouse()
        #update_song_info()
        def loop_update_song_info():
            self.update_song_info()
            if self.can_update_song_info:
                self.update_song_info_after_id = self.after(350, loop_update_song_info)
        loop_update_song_info()
        
    
    

    # === Settings ===
    def open_settings(self):
        if getattr(self, "settings_openned", False):
            if hasattr(self, "settings_window") and self.settings_window.winfo_exists():
                self.settings_window.destroy()
            self.settings_openned = False
            self.attributes("-alpha", self.default_opacity)
            return

        self.settings_openned = True
        # self.attributes("-alpha", 0.8)

        self.settings_window = ctk.CTkToplevel(self)
        self.settings_window.title("Overlay Settings")
        self.settings_window.geometry("500x240")
        self.settings_window.resizable(False, False)
        self.settings_window.configure(fg_color="#00141B")

        def on_close():
            self.settings_openned = False
            self.settings_window.destroy()
            save_settings({
                "default_opacity": self.default_opacity,
                "hover_opacity": self.hover_opacity,
                "fade_delay": self.fade_delay,
                "fade_duration": self.fade_duration,
                "always_on_top": self.always_on_top,
                "can_drag": self.can_drag,
                "click_through": self.click_through
                })
            
        self.settings_window.protocol("WM_DELETE_WINDOW", on_close)

        # Title
        title_label = ctk.CTkLabel(self.settings_window, text="Settings", width=500, font=ctk.CTkFont(size=18, weight="bold"))
        title_label.place(relx=0, rely=0)

        # Slider opacity
        opacity_label = ctk.CTkLabel(self.settings_window, text=f"Window opacity: {self.default_opacity:.1f}")
        opacity_label.place(y=30, x=8)

        opacity_slider = ctk.CTkSlider(self.settings_window, from_=0.1, to=1.0, number_of_steps=9, width=205)
        opacity_slider.set(self.default_opacity)
        opacity_slider.place(y=30+4.5, relx=0.98, anchor="ne")

        def update_opacity(value):
            self.default_opacity = float(value)
            opacity_label.configure(text=f"Window opacity: {float(value):.1f}")
            if not self.inside:
                self.fade_to(self.default_opacity)
        opacity_slider.configure(command=update_opacity)

        # Slider opacity-on-hover
        opacityOnHover_label = ctk.CTkLabel(self.settings_window, text=f"Window opacity on hover: {self.hover_opacity:.1f}")
        opacityOnHover_label.place(y=60, x=8)

        opacityOnHover_slider = ctk.CTkSlider(self.settings_window, from_=0.1, to=1.0, number_of_steps=9, width=205)
        opacityOnHover_slider.set(self.hover_opacity)
        opacityOnHover_slider.place(y=60+4.5, relx=0.98, anchor="ne")

        def update_opacityOnHover(value):
            self.hover_opacity = float(value)
            opacityOnHover_label.configure(text=f"Window opacity on hover: {float(value):.1f}")
            if not self.inside:
                self.fade_to(self.default_opacity)
        opacityOnHover_slider.configure(command=update_opacityOnHover)

        # Slider fade-delay
        fadeDelay_label = ctk.CTkLabel(self.settings_window, text=f"Fade delay: {self.fade_delay:.1f}")
        fadeDelay_label.place(y=90, x=8)

        fadeDelay_slider = ctk.CTkSlider(self.settings_window, from_=1, to=10, number_of_steps=9, width=205)
        fadeDelay_slider.set(self.fade_delay)
        fadeDelay_slider.place(y=90+4.5, relx=0.98, anchor="ne")

        def update_fadeDelay(value):
            self.fade_delay = float(value)
            fadeDelay_label.configure(text=f"Fade delay: {float(value):.1f}")
            if not self.inside:
                self.fade_to(self.fade_delay)
        fadeDelay_slider.configure(command=update_fadeDelay)

        # Slider fade-duration
        fadeDuration_label = ctk.CTkLabel(self.settings_window, text=f"Fade duration: {self.fade_duration:.1f}")
        fadeDuration_label.place(y=120, x=8)

        fadeDuration_slider = ctk.CTkSlider(self.settings_window, from_=0.1, to=5, number_of_steps=49, width=205)
        fadeDuration_slider.set(self.fade_duration)
        fadeDuration_slider.place(y=120+4.5, relx=0.98, anchor="ne")

        def update_fadeDuration(value):
            self.fade_duration = float(value)
            fadeDuration_label.configure(text=f"Fade duration: {float(value):.1f}")
            if not self.inside:
                self.fade_to(self.fade_duration)
        fadeDuration_slider.configure(command=update_fadeDuration)

        # Toggle always-on-top
        def toggle_top(value):
            self.always_on_top = value
            self.attributes("-topmost", self.always_on_top)

        top_switch = ctk.CTkSwitch(self.settings_window, text="Always on top", command=lambda: toggle_top(top_switch.get()))
        if self.always_on_top == True: top_switch.select()
        top_switch.place(y=150, x=8)

        # Toggle can-drag
        def toggle_canDrag(value):
            self.can_drag = value

        canDrag_switch = ctk.CTkSwitch(self.settings_window, text="Can drag", command=lambda: toggle_canDrag(canDrag_switch.get()))
        if self.can_drag == True: canDrag_switch.select() 
        canDrag_switch.place(y=180, x=8)

        # Change window resolution
        # def change_resolution_in_settings(size_type):
        #     if size_type == 1:
        #         self.resize_type = size_type
        #         self.change_resolution()

        # change_resolution_label = ctk.CTkLabel(self.settings_window, text="Overlay size type:")
        # change_resolution_label.place(y=210, x=8)

        # change_resolution_button1 = ctk.CTkButton(self.settings_window, text="1", width=12, height=12, command=lambda: change_resolution_in_settings(1))
        # change_resolution_button1.place(y=212.3, x=115)

        # change_resolution_button2 = ctk.CTkButton(self.settings_window, text="2", width=12, height=12, command=lambda: change_resolution_in_settings(2))
        # change_resolution_button2.place(y=212.3, x=140)

        # change_resolution_button3 = ctk.CTkButton(self.settings_window, text="3", width=12, height=12, command=lambda: change_resolution_in_settings(3))
        # change_resolution_button3.place(y=212.3, x=165)
        
        # Toggle Big Resize Mode
        # def toggle_bigResizeMode(value):
        #     if value == True:
        #         self.resize_type = "change_to_3"
        #         self.change_resolution()
        #     elif value == False:
        #         self.resize_type = 2
        #         self.change_resolution()

        # bigResizeMode_switch = ctk.CTkSwitch(self.settings_window, text="Big size", command=lambda: toggle_bigResizeMode(bigResizeMode_switch.get()))
        # if self.resize_type == 3: bigResizeMode_switch.select() 
        # bigResizeMode_switch.place(y=210, x=8)




    def start_move(self, event):
        if self.can_drag == True:
            self._drag_start_x = self.winfo_pointerx() - self.winfo_x()
            self._drag_start_y = self.winfo_pointery() - self.winfo_y()

    def on_motion(self, event):
        if self.can_drag == True:
            new_x = self.winfo_pointerx() - self._drag_start_x
            new_y = self.winfo_pointery() - self._drag_start_y
            self.geometry(f"+{new_x}+{new_y}")

    def monitor_mouse(self):
        def check_loop():
            try:
                x, y = self.winfo_pointerx(), self.winfo_pointery()
                x0, y0 = self.winfo_rootx(), self.winfo_rooty()
                x1, y1 = x0 + self.winfo_width(), y0 + self.winfo_height()
                inside_now = x0 <= x <= x1 and y0 <= y <= y1

                if inside_now and not self.inside:
                    self.inside = True
                    self.on_enter()
                elif not inside_now and self.inside:
                    self.inside = False
                    self.on_leave()
            except tk.TclError:
                return

            self.after(50, check_loop)

        check_loop()


    def on_enter(self):
        # self.attributes("-alpha", self.hover_opacity)

        if self.click_through == False:
            if self.revert_timer:
                self.revert_timer.cancel()
            self.fade_to(self.hover_opacity)

    def on_leave(self):
        # def set_default_opacity():
        #     self.attributes("-alpha", self.default_opacity)
        # self.after(self.fade_delay * 1000, set_default_opacity)
        
        if self.revert_timer:
            self.revert_timer.cancel()
        self.revert_timer = threading.Timer(self.fade_delay, lambda: self.fade_to(self.default_opacity))
        self.revert_timer.daemon = True
        self.revert_timer.start()

    def fade_to(self, target_opacity):
        current_opacity = self.attributes("-alpha")
        steps = 10
        step_size = (target_opacity - current_opacity) / steps
        delay = int(self.fade_duration * 1000 / steps)

        def fade_step(step=0):
            if step < steps:
                new_opacity = self.attributes("-alpha") + step_size
                self.attributes("-alpha", max(0.0, min(1.0, new_opacity)))
                self.after(delay, lambda: fade_step(step + 1))
            else:
                self.attributes("-alpha", target_opacity)

        fade_step()

if __name__ == "__main__":
    #ctk.set_appearance_mode("dark")
    #ctk.set_default_color_theme("dark-blue")
    app = Overlay()
    app.iconbitmap(file_path("app-icon.ico"))

    threading.Thread(target=create_tray, daemon=True).start()

    app.click_through = not app.click_through
    toggle_click_through()

    app.mainloop()