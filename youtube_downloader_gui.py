# <<<--- Start of Code (Scroll down to line ~105 for the fix) --->>>
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
# No longer using pytube directly for core functionality
import threading
import os
import time
import requests  # Still needed for thumbnail download
from PIL import Image, ImageTk # Still needed for thumbnail display
import io # To handle image data in memory
import subprocess # To run yt-dlp
import json # To parse yt-dlp output

# --- Global Variables ---
video_info_json = None # Store the parsed JSON output from yt-dlp
available_formats = {} # Map user-friendly format descriptions to yt-dlp format codes
available_captions = {} # Map language names to yt-dlp language codes

# --- Functions ---

def select_path():
    """Opens a dialog to select the download directory."""
    path = filedialog.askdirectory()
    if path:
        path_label.config(text=path)
        print(f"Selected path: {path}")
    else:
        print("No path selected.")

def format_ydl_stream_info(format_data):
    """Creates a user-friendly string for a yt-dlp format entry."""
    # Safely get values from the format dictionary
    resolution = format_data.get('resolution', 'N/A')
    ext = format_data.get('ext', 'N/A')
    format_note = format_data.get('format_note', '')
    # Use filesize_approx if filesize is missing; handle potential None with 'or 0'
    filesize_val = format_data.get('filesize') or format_data.get('filesize_approx') or 0
    vcodec = format_data.get('vcodec', 'none')
    acodec = format_data.get('acodec', 'none')
    format_id = format_data.get('format_id', '?')
    # Use 'or 0' for abr as well, just in case
    abr_val = format_data.get('abr') or 0

    # Determine type
    type_str = ""
    if vcodec != 'none' and acodec != 'none':
        type_str = "Video+Audio"
    elif vcodec != 'none':
        type_str = "Video Only"
    elif acodec != 'none':
        type_str = "Audio Only"
        resolution = f"{abr_val}k" if abr_val else "Audio" # Show audio bitrate instead of resolution for audio

    # Filesize string
    filesize_str = f"{filesize_val / (1024 * 1024):.1f}MB" if filesize_val > 0 else "Size N/A"

    # Basic description
    desc = f"{resolution} ({ext.upper()}"
    if format_note and format_note not in ['N/A', resolution]: # Add note if useful (like 720p60)
       desc += f", {format_note}"
    desc += f", {type_str}, {filesize_str}) - [ID: {format_id}]"
    return desc

def check_yt_dlp():
    """Checks if yt-dlp command runs."""
    try:
        # Use --version, it's a quick command
        process = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        print(f"yt-dlp check successful: Version {process.stdout.strip()}")
        return True
    except FileNotFoundError:
        messagebox.showerror("Error", "yt-dlp not found. Please ensure yt-dlp is installed and accessible in your system's PATH.\n\nInstall using: pip install yt-dlp")
        return False
    except subprocess.CalledProcessError as e:
         messagebox.showerror("Error", f"yt-dlp check failed: {e}\nStderr: {e.stderr}")
         return False
    except Exception as e:
         messagebox.showerror("Error", f"An unexpected error occurred while checking yt-dlp: {e}")
         return False

def fetch_video_info_thread():
    """Fetches video info using yt-dlp in a separate thread."""
    global video_info_json, available_formats, available_captions

    if not check_yt_dlp(): # Check if yt-dlp exists before proceeding
         fetch_button.config(state=tk.NORMAL) # Re-enable fetch button
         return

    url = url_entry.get()
    if not url:
        messagebox.showwarning("Input Error", "Please enter a YouTube URL.")
        fetch_button.config(state=tk.NORMAL)
        return

    # Disable buttons/selectors during fetch
    fetch_button.config(state=tk.DISABLED)
    download_button.config(state=tk.DISABLED)
    quality_combobox.set('')
    quality_combobox.config(state=tk.DISABLED, values=[])
    caption_combobox.set('')
    caption_combobox.config(state=tk.DISABLED, values=[])
    title_label.config(text="Title: Fetching...")
    thumbnail_label.config(image='', text="Fetching...") # Clear previous thumbnail, update text
    status_label.config(text="Status: Connecting & Fetching Details via yt-dlp...")
    progress_bar['value'] = 0 # Use progress bar as indeterminate during fetch
    progress_bar['mode'] = 'indeterminate'
    progress_bar.start()
    root.update_idletasks()

    try:
        # Command to get JSON output
        command = ['yt-dlp', '--dump-json', '--no-warnings', url]
        process = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

        video_info_json = json.loads(process.stdout) # Store parsed JSON globally

        # --- Extract Info ---
        title = video_info_json.get('title', 'No Title Found')
        thumbnail_url = video_info_json.get('thumbnail')

        # --- Process Formats ---
        available_formats = {}
        format_options = []
        formats = video_info_json.get('formats', [])

        # <<< --- FIX IS HERE (Lines ~105-113) --- >>>
        # Basic sorting: Prefer mp4, then progressive, then resolution, then audio bitrate
        # Added 'or 0' to handle potential None values returned by .get() if JSON value is null
        formats_sorted = sorted(
            formats,
            key=lambda f: (
                f.get('ext') != 'mp4', # mp4 first
                f.get('vcodec', 'none') == 'none' or f.get('acodec', 'none') == 'none', # Progressive/Combined first
                -int(f.get('height') or 0), # Higher resolution first - FIXED
                -int(f.get('abr') or 0) if f.get('acodec') != 'none' else 0, # Higher audio bitrate first - FIXED
                f.get('format_id') # Tie-break with format_id
            )
        )

        # Add a "best" option which lets yt-dlp decide (usually merges best video/audio)
        best_option_key = "Best Available (Video+Audio merged by yt-dlp)"
        # Use a high-precedence format selection string for yt-dlp
        available_formats[best_option_key] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
        format_options.append(best_option_key)

        for f in formats_sorted:
             # Only include formats yt-dlp likely can download directly and have an ID
            if (f.get('vcodec') != 'none' or f.get('acodec') != 'none') and f.get('format_id'):
                desc = format_ydl_stream_info(f)
                format_id = f.get('format_id')
                if desc not in available_formats: # Avoid duplicates description-wise
                    available_formats[desc] = format_id
                    format_options.append(desc)


        # --- Process Captions ---
        available_captions = {"(No Subtitles)": None}
        caption_options = ["(No Subtitles)"]
        subtitles = video_info_json.get('subtitles', {}) or video_info_json.get('automatic_captions', {}) # Use subtitles first, fallback to automatic
        # Sort captions by language code for consistent order
        sorted_lang_codes = sorted(subtitles.keys())

        for lang_code in sorted_lang_codes:
            subs_list = subtitles[lang_code]
            if isinstance(subs_list, list) and len(subs_list) > 0:
                # Prefer non-auto-generated if multiple exist for a lang
                sub_info = next((s for s in subs_list if not s.get('is_automatic')), subs_list[0])
                ext = sub_info.get('ext', 'srt') # Usually srt, vtt etc.
                # Try to get a more descriptive name if available (sometimes yt-dlp provides it)
                lang_name_desc = sub_info.get('name', lang_code)
                is_auto = sub_info.get('is_automatic', False)
                lang_name = f"{lang_name_desc} ({ext})"
                if is_auto:
                    lang_name += " [auto]"

                if lang_name not in available_captions:
                     available_captions[lang_name] = lang_code # Store the lang code needed by yt-dlp
                     caption_options.append(lang_name)

        # Schedule GUI updates on the main thread
        root.after(0, update_gui_after_fetch, title, format_options, caption_options, thumbnail_url)

    except subprocess.CalledProcessError as e:
        error_msg = f"yt-dlp Error:\nCommand: {' '.join(e.cmd)}\nReturn Code: {e.returncode}\nStderr: {e.stderr.strip()}"
        print(error_msg)
        root.after(0, handle_fetch_error, error_msg)
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse yt-dlp output: {e}"
        print(error_msg)
        root.after(0, handle_fetch_error, error_msg)
    except Exception as e:
        # Catch other potential errors during processing
        error_msg = f"Error processing video details:\n{e}" # Changed error prefix
        import traceback
        print(f"{error_msg}\n{traceback.format_exc()}") # Print full traceback for debugging
        root.after(0, handle_fetch_error, error_msg)
    finally:
        # Ensure progress bar stops
        root.after(0, lambda: progress_bar.stop())
        root.after(0, lambda: progress_bar.config(mode='determinate'))


def handle_fetch_error(error_message):
    """Updates GUI in case of fetch error."""
    progress_bar.stop()
    progress_bar.config(mode='determinate')
    messagebox.showerror("Fetch Error", error_message)
    title_label.config(text="Title: Error")
    status_label.config(text="Status: Error fetching video details")
    fetch_button.config(state=tk.NORMAL) # Re-enable fetch button
    thumbnail_label.config(image='', text="Error") # Update placeholder text
    # Clear selections
    quality_combobox.set('')
    quality_combobox.config(state=tk.DISABLED, values=[])
    caption_combobox.set('')
    caption_combobox.config(state=tk.DISABLED, values=[])

def update_gui_after_fetch(title, format_options, caption_options, thumbnail_url):
    """Updates GUI elements after successfully fetching streams (runs on main thread)."""
    progress_bar.stop()
    progress_bar.config(mode='determinate')
    progress_bar['value'] = 0

    title_label.config(text=f"Title: {title}")
    status_label.config(text="Status: Ready. Select quality and press Download.")

    if format_options:
        quality_combobox.config(state="readonly", values=format_options)
        quality_combobox.current(0) # Select "Best Available" by default
        caption_combobox.config(state="readonly", values=caption_options)
        caption_combobox.current(0) # Select "(No Subtitles)" by default
        download_button.config(state=tk.NORMAL) # Enable download button
    else:
        status_label.config(text="Status: No downloadable formats found by yt-dlp.")
        messagebox.showwarning("No Formats", "yt-dlp could not find any downloadable formats for this video.")

    fetch_button.config(state=tk.NORMAL) # Re-enable fetch button

    # --- Load Thumbnail ---
    if thumbnail_url:
        load_thumbnail_thread(thumbnail_url)
    else:
        thumbnail_label.config(image='', text="No Thumbnail")

# --- Thumbnail Loading (largely unchanged) ---
def load_thumbnail_thread(url):
    threading.Thread(target=load_thumbnail, args=(url,), daemon=True).start()

def load_thumbnail(url):
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        image_data = response.raw.read()
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail((160, 90))
        photo = ImageTk.PhotoImage(img)
        root.after(0, lambda: update_thumbnail_label(photo))
    except requests.exceptions.RequestException as e:
        print(f"Error fetching thumbnail: {e}")
        root.after(0, lambda: thumbnail_label.config(image='', text="No Thumbnail"))
    except Exception as e:
        print(f"Error processing thumbnail: {e}")
        root.after(0, lambda: thumbnail_label.config(image='', text="Thumb Error"))

def update_thumbnail_label(photo):
    thumbnail_label.image = photo
    thumbnail_label.config(image=photo, text="")

# --- Downloading Logic ---

def download_finished(success, message, return_code=None):
    """Handles actions after download attempt (runs on main thread)."""
    progress_bar.stop() # Stop indeterminate progress if it was running
    progress_bar.config(mode='determinate')
    progress_bar['value'] = 100 if success else 0

    status_label.config(text=f"Status: {'Complete!' if success else 'Failed!'}")

    if success:
        messagebox.showinfo("Success", message)
    else:
        full_message = f"Download Failed:\n{message}"
        if return_code is not None:
            full_message += f"\n(yt-dlp exit code: {return_code})"
        messagebox.showerror("Error", full_message)

    # Re-enable buttons/selectors
    if video_info_json: # Only re-enable if fetch was successful
        quality_combobox.config(state="readonly")
        caption_combobox.config(state="readonly")
        download_button.config(state=tk.NORMAL)
    else:
        download_button.config(state=tk.DISABLED)

    fetch_button.config(state=tk.NORMAL)
    url_entry.config(state=tk.NORMAL)

def download_video_thread(url, format_code, subtitle_lang, save_path):
    """Handles the download process using yt-dlp subprocess."""

    # Start indeterminate progress bar for download
    root.after(0, lambda: progress_bar.config(mode='indeterminate'))
    root.after(0, lambda: progress_bar.start())
    root.after(0, lambda: status_label.config(text="Status: Starting download via yt-dlp..."))


    try:
        # Construct the yt-dlp command
        # Use %(title)s [%(id)s].%(ext)s for a more unique filename
        output_template = os.path.join(save_path, "%(title)s [%(id)s].%(ext)s")
        command = [
            'yt-dlp',
            '-f', format_code, # Specify format code (e.g., 'best' or a specific ID)
            '--no-warnings',
            # '--progress', # Request progress output (parsing it is complex, removed for now)
            '--force-overwrites', # Overwrite if file exists (optional)
            # '--ffmpeg-location', '/path/to/ffmpeg', # Uncomment and set if ffmpeg isn't in PATH and merging is needed
            '-o', output_template, # Output template
        ]

        # Add subtitle options if requested
        if subtitle_lang:
            command.extend(['--write-subs', '--sub-lang', subtitle_lang])
            # Specify subtitle format if needed (default is usually fine)
            # command.extend(['--sub-format', 'srt'])
            # command.extend(['--embed-subs']) # Optionally embed instead of separate file

        command.append(url) # Finally, the URL

        print(f"Executing command: {' '.join(command)}") # Log the command

        # Run the command
        process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', check=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0) # Use check=False to handle errors manually

        # Check results based on return code
        if process.returncode == 0:
            # Success - The actual downloaded filename might differ slightly due to sanitization
            # Trying to find the exact filename is complex, just report success.
            final_message = f"Download successful!\n(Saved to folder: {save_path})"
            if subtitle_lang:
                 final_message += f"\nSubtitle language requested: {subtitle_lang}"
            root.after(0, download_finished, True, final_message)
        else:
            # Failure
            error_output = process.stderr.strip()
            if not error_output: # Sometimes errors go to stdout
                error_output = process.stdout.strip()
            print(f"yt-dlp failed. Return Code: {process.returncode}")
            print(f"Stderr/Stdout: {error_output}")
            root.after(0, download_finished, False, f"yt-dlp failed.\nOutput:\n{error_output[:500]}...", process.returncode) # Show first 500 chars of error

    except FileNotFoundError:
         root.after(0, download_finished, False, "yt-dlp command not found. Is it installed and in PATH?")
    except Exception as e:
        print(f"Unexpected error during download subprocess: {e}")
        import traceback
        print(traceback.format_exc())
        root.after(0, download_finished, False, f"An unexpected Python error occurred: {e}")
    finally:
        # Ensure progress bar stops regardless of outcome
         root.after(0, lambda: progress_bar.stop())
         root.after(0, lambda: progress_bar.config(mode='determinate', value=0))


def start_fetch():
    """Starts fetching info in a new thread."""
    fetch_thread = threading.Thread(target=fetch_video_info_thread, daemon=True)
    fetch_thread.start()

def start_download():
    """Validates input and starts the download process in a new thread."""
    selected_quality_desc = quality_combobox.get()
    selected_caption_desc = caption_combobox.get()
    save_path = path_label.cget("text")
    url = url_entry.get() # Get current URL

    if not url:
         messagebox.showwarning("Input Error", "URL is missing.")
         return
    if not selected_quality_desc:
        messagebox.showwarning("Input Error", "Please fetch and select a quality.")
        return
    if not save_path or save_path == "No directory selected" or not os.path.isdir(save_path):
        messagebox.showwarning("Input Error", f"Please select a valid download directory.\n(Selected: {save_path})")
        return

    format_code = available_formats.get(selected_quality_desc)
    subtitle_lang = available_captions.get(selected_caption_desc) # Will be None for "(No Subtitles)"

    if not format_code:
        messagebox.showerror("Error", "Selected quality format code not found. Please fetch again.")
        return

    # Disable buttons/selectors during download
    download_button.config(state=tk.DISABLED)
    fetch_button.config(state=tk.DISABLED)
    quality_combobox.config(state=tk.DISABLED)
    caption_combobox.config(state=tk.DISABLED)
    url_entry.config(state=tk.DISABLED)
    status_label.config(text="Status: Preparing download...")
    progress_bar['value'] = 0
    root.update_idletasks()

    # Run the download logic in a separate thread
    download_thread = threading.Thread(target=download_video_thread, args=(url, format_code, subtitle_lang, save_path), daemon=True)
    download_thread.start()


# --- GUI Setup (Mostly unchanged, ensure widget names match) ---
root = tk.Tk()
root.title("Enhanced YouTube Downloader (yt-dlp)") # Updated Title
root.geometry("650x550")
root.resizable(True, True)

# Style
style = ttk.Style(root)
available_themes = style.theme_names()
print(f"Available themes: {available_themes}")
theme_to_use = 'clam' if 'clam' in available_themes else 'default'
try:
    style.theme_use(theme_to_use)
    print(f"Using theme: {theme_to_use}")
except tk.TclError:
    print(f"{theme_to_use.capitalize()} theme not available, using default.")
    style.theme_use('default')

# --- Frames ---
input_frame = ttk.Frame(root, padding="10")
input_frame.pack(fill=tk.X, side=tk.TOP)

info_frame = ttk.Frame(root, padding="10")
info_frame.pack(fill=tk.X, side=tk.TOP)
info_frame.columnconfigure(0, weight=1)
info_frame.columnconfigure(1, weight=0)

info_left_frame = ttk.Frame(info_frame)
info_left_frame.grid(row=0, column=0, sticky="nsew", padx=(0,10))
info_right_frame = ttk.Frame(info_frame)
info_right_frame.grid(row=0, column=1, sticky="ne")

path_frame = ttk.Frame(root, padding="10")
path_frame.pack(fill=tk.X, side=tk.TOP)

options_frame = ttk.Frame(root, padding="10")
options_frame.pack(fill=tk.X, side=tk.TOP)
options_frame.columnconfigure(1, weight=1)
options_frame.columnconfigure(3, weight=1)

download_frame = ttk.Frame(root, padding="10")
download_frame.pack(fill=tk.X, side=tk.TOP)

progress_frame = ttk.Frame(root, padding="10")
progress_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

# --- Input Frame Widgets ---
url_label = ttk.Label(input_frame, text="YouTube URL:")
url_label.pack(side=tk.LEFT, padx=(0, 5))
url_entry = ttk.Entry(input_frame, width=50)
url_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 10))
fetch_button = ttk.Button(input_frame, text="Fetch Info", command=start_fetch)
fetch_button.pack(side=tk.LEFT)

# --- Info Frame Widgets ---
title_label = ttk.Label(info_left_frame, text="Title: (Enter URL and click Fetch)", wraplength=400, anchor="w", justify=tk.LEFT)
title_label.pack(fill=tk.X, expand=True)
thumbnail_label = ttk.Label(info_right_frame, text="Thumbnail", relief="sunken", anchor=tk.CENTER)
thumbnail_label.pack()

# --- Path Frame Widgets ---
path_button = ttk.Button(path_frame, text="Select Folder", command=select_path)
path_button.pack(side=tk.LEFT, padx=(0, 10))
path_label = ttk.Label(path_frame, text="No directory selected", relief="sunken", padding=5)
path_label.pack(side=tk.LEFT, expand=True, fill=tk.X)

# --- Options Frame Widgets ---
quality_label = ttk.Label(options_frame, text="Quality:")
quality_label.grid(row=0, column=0, padx=(0, 5), sticky="w")
quality_combobox = ttk.Combobox(options_frame, state=tk.DISABLED, width=40)
quality_combobox.grid(row=0, column=1, padx=(0, 15), sticky="ew")

caption_label = ttk.Label(options_frame, text="Subtitles:")
caption_label.grid(row=0, column=2, padx=(10, 5), sticky="w")
caption_combobox = ttk.Combobox(options_frame, state=tk.DISABLED, width=25)
caption_combobox.grid(row=0, column=3, sticky="ew")

# --- Download Frame Widgets ---
download_button = ttk.Button(download_frame, text="Download Selected Quality", command=start_download, state=tk.DISABLED)
download_button.pack(pady=10)

# --- Progress Frame Widgets ---
status_label = ttk.Label(progress_frame, text="Status: Idle. Install yt-dlp (pip install yt-dlp) if needed.", anchor="w")
status_label.pack(pady=(5, 0), fill=tk.X)
progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=400, mode='determinate') # Start in determinate mode
progress_bar.pack(pady=(5, 10), fill=tk.X)


# --- Run the App ---
# Add a check for yt-dlp at the start
if __name__ == "__main__":
    # Optional: Run check at startup, or rely on check before fetch
    # if not check_yt_dlp():
    #    root.destroy() # Exit if yt-dlp is not found on startup
    # else:
    #    root.mainloop()
    root.mainloop() # Current behavior checks before first fetch
# <<<--- End of Code --->>>