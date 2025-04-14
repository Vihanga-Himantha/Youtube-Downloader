# <<<--- Start of Code --- >>>
import tkinter as tk # Keep standard tkinter for filedialog and messagebox
import customtkinter as ctk # Use customtkinter for UI elements
from tkinter import filedialog, messagebox
import threading
import os
import time
import requests
from PIL import Image, ImageTk
import io
import subprocess
import json
import traceback
import re # For detecting playlist URLs

# --- Global Variables ---
video_info_json = None # Store the parsed JSON output from yt-dlp
available_formats = {} # Map user-friendly format descriptions to yt-dlp format codes
available_captions = {} # Map language names to yt-dlp language codes
is_playlist = False # Flag to indicate if the current URL is a playlist

# --- Appearance Settings ---
ctk.set_appearance_mode("System")  # Modes: "System" (default), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (default), "green", "dark-blue"

# --- Functions ---

def select_path(entry_widget):
    """Opens a dialog to select a directory and inserts into entry."""
    path = filedialog.askdirectory()
    if path:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, path)
        print(f"Selected path: {path}")
    else:
        print("No path selected.")

def select_archive_file(entry_widget):
    """Opens a dialog to select or create an archive file."""
    path = filedialog.asksaveasfilename(
        title="Select or Create Archive File",
        defaultextension=".txt",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
    )
    if path:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, path)
        print(f"Selected archive file: {path}")
    else:
        print("No archive file selected.")


def format_ydl_stream_info(format_data):
    """Creates a user-friendly string for a yt-dlp format entry."""
    resolution = format_data.get('resolution', 'N/A')
    ext = format_data.get('ext', 'N/A')
    format_note = format_data.get('format_note', '')
    filesize_val = format_data.get('filesize') or format_data.get('filesize_approx') or 0
    vcodec = format_data.get('vcodec', 'none')
    acodec = format_data.get('acodec', 'none')
    format_id = format_data.get('format_id', '?')
    abr_val = format_data.get('abr') or 0
    fps = format_data.get('fps') or 0

    type_str = ""
    if vcodec != 'none' and acodec != 'none':
        type_str = "Video+Audio"
    elif vcodec != 'none':
        type_str = "Video Only"
    elif acodec != 'none':
        type_str = "Audio Only"
        resolution = f"{int(abr_val)}k" if abr_val else "Audio"

    filesize_str = f"{filesize_val / (1024 * 1024):.1f}MB" if filesize_val > 0 else "Size N/A"

    desc = f"{resolution} ({ext.upper()}"
    if fps > 0 and vcodec != 'none': # Show FPS for video
         desc += f", {int(fps)}fps"
    if format_note and format_note not in ['N/A', resolution]:
       desc += f", {format_note}" # Add note if useful (like 'HDR')
    desc += f", {type_str}, {filesize_str}) [ID: {format_id}]"
    return desc

def check_yt_dlp():
    """Checks if yt-dlp command runs."""
    try:
        process = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, check=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        print(f"yt-dlp check successful: Version {process.stdout.strip()}")
        return True
    except Exception as e:
        messagebox.showerror("yt-dlp Error", f"yt-dlp check failed:\n{e}\n\nPlease ensure yt-dlp is installed and in your system's PATH.\n(Try: pip install yt-dlp)")
        return False

def fetch_video_info_thread():
    """Fetches video/playlist info using yt-dlp in a separate thread."""
    global video_info_json, available_formats, available_captions, is_playlist

    if not check_yt_dlp():
        ui_set_fetch_button_state(True)
        return

    url = url_entry.get()
    if not url:
        messagebox.showwarning("Input Error", "Please enter a YouTube URL or Playlist URL.")
        ui_set_fetch_button_state(True)
        return

    is_playlist = bool(re.search(r'list=[^&]+', url))
    print(f"Detected Playlist: {is_playlist}")

    ui_set_controls_state(False)
    ui_set_fetch_button_state(False)
    ui_clear_comboboxes()
    title_label.configure(text="Title: Fetching...")
    thumbnail_label.configure(image=None, text="Fetching...")
    status_label.configure(text="Status: Connecting & Fetching via yt-dlp...")
    progress_bar.set(0)
    progress_bar.configure(mode='indeterminate')
    progress_bar.start()

    try:
        command = ['yt-dlp', '--dump-json', '--no-warnings', '--skip-download']
        if is_playlist:
             command.extend(['--playlist-items', '1'])
             print("Fetching info for first playlist item only...")
        else:
             command.extend(['--no-playlist'])
        command.append(url)

        print(f"Executing fetch command: {' '.join(command)}")
        process = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8', timeout=30, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

        try:
            video_info_json = json.loads(process.stdout)
        except json.JSONDecodeError:
             raise ValueError("Failed to decode JSON output from yt-dlp.")

        title = video_info_json.get('title', 'No Title Found')
        if is_playlist:
             playlist_title = video_info_json.get('playlist_title', 'Playlist')
             playlist_index = video_info_json.get('playlist_index', 1)
             title = f"{playlist_title} (Item {playlist_index}: {title})"
        thumbnail_url = video_info_json.get('thumbnail')

        available_formats = {}
        format_options = []
        formats = video_info_json.get('formats', [])
        formats_sorted = sorted(formats, key=lambda f: (-int(f.get('height') or 0), -int(f.get('abr') or 0)))

        best_option_key = "Best Available (Video+Audio merged by yt-dlp)"
        available_formats[best_option_key] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
        format_options.append(best_option_key)

        for f in formats_sorted:
            if (f.get('vcodec') != 'none' or f.get('acodec') != 'none') and f.get('format_id'):
                desc = format_ydl_stream_info(f)
                if desc not in available_formats:
                    available_formats[desc] = f.get('format_id')
                    format_options.append(desc)

        available_captions = {"(No Subtitles)": None}
        caption_options = ["(No Subtitles)"]
        subtitles_data = video_info_json.get('subtitles') or video_info_json.get('automatic_captions', {})
        sorted_lang_codes = sorted(subtitles_data.keys())
        for lang_code in sorted_lang_codes:
            subs_list = subtitles_data[lang_code]
            if isinstance(subs_list, list) and len(subs_list) > 0:
                sub_info = sorted(subs_list, key=lambda s: (s.get('is_automatic', False), s.get('ext') != 'srt'))[0]
                ext = sub_info.get('ext', 'srt')
                lang_name_desc = sub_info.get('name', lang_code)
                is_auto = '[auto]' if sub_info.get('is_automatic') else ''
                lang_name = f"{lang_name_desc} ({ext}){is_auto}"
                if lang_name not in available_captions:
                     available_captions[lang_name] = lang_code
                     caption_options.append(lang_name)

        app.after(0, update_gui_after_fetch, title, format_options, caption_options, thumbnail_url)

    except subprocess.TimeoutExpired:
        error_msg = f"Fetching video info timed out for {url}"
        print(error_msg)
        app.after(0, handle_fetch_error, error_msg)
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.strip() or e.stdout.strip()
        if "confirm your age" in error_output.lower():
             error_msg = "Age-restricted video. yt-dlp may need cookies..."
        elif "private video" in error_output.lower():
             error_msg = "This video is private."
        elif "video unavailable" in error_output.lower():
             error_msg = "This video is unavailable."
        else:
             error_msg = f"yt-dlp Error:\nReturn Code: {e.returncode}\nOutput: {error_output[:500]}..."
        print(f"yt-dlp failed. Output:\n{error_output}")
        app.after(0, handle_fetch_error, error_msg)
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse yt-dlp output (invalid JSON): {e}"
        print(error_msg)
        app.after(0, handle_fetch_error, error_msg)
    except Exception as e:
        error_msg = f"Error processing video details:\n{e}"
        print(f"{error_msg}\n{traceback.format_exc()}")
        app.after(0, handle_fetch_error, error_msg)
    finally:
        app.after(0, lambda: progress_bar.stop())
        app.after(0, lambda: progress_bar.configure(mode='determinate'))
        app.after(0, lambda: ui_set_fetch_button_state(True))


def handle_fetch_error(error_message):
    """Updates GUI in case of fetch error."""
    progress_bar.stop()
    progress_bar.configure(mode='determinate')
    messagebox.showerror("Fetch Error", error_message)
    title_label.configure(text="Title: Error")
    status_label.configure(text="Status: Error fetching details.")
    ui_set_fetch_button_state(True)
    thumbnail_label.configure(image=None, text="Error")
    ui_clear_comboboxes()
    ui_set_download_button_state(False)


def update_gui_after_fetch(title, format_options, caption_options, thumbnail_url):
    """Updates GUI elements after successfully fetching streams."""
    progress_bar.stop()
    # Corrected line: Use .set() for value
    progress_bar.configure(mode='determinate')
    progress_bar.set(0) # FIXED
    # ---

    title_label.configure(text=f"Title: {title}")
    status_label.configure(text="Status: Ready. Select options and press Download.")

    if format_options:
        quality_combobox.configure(state="readonly", values=format_options)
        quality_combobox.set(format_options[0])
        caption_combobox.configure(state="readonly", values=caption_options)
        caption_combobox.set(caption_options[0])
        ui_set_controls_state(True)
    else:
        status_label.configure(text="Status: No downloadable formats found.")
        messagebox.showwarning("No Formats", "Could not find any downloadable formats.")
        ui_set_controls_state(False)

    ui_set_fetch_button_state(True)

    if thumbnail_url:
        load_thumbnail_thread(thumbnail_url)
    else:
        thumbnail_label.configure(image=None, text="No Thumbnail")


# --- Thumbnail Loading ---
def load_thumbnail_thread(url):
    threading.Thread(target=load_thumbnail, args=(url,), daemon=True).start()

def load_thumbnail(url):
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        image_data = response.raw.read()
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail((240, 135))
        photo = ImageTk.PhotoImage(img)
        app.after(0, lambda: update_thumbnail_label(photo))
    except Exception as e:
        print(f"Error loading/processing thumbnail: {e}")
        app.after(0, lambda: thumbnail_label.configure(image=None, text="Thumb Error"))

def update_thumbnail_label(photo):
    if thumbnail_label:
        thumbnail_label.configure(image=photo, text="")
        # Keep reference for CTkImage if needed? No, ImageTk okay here for CTkLabel.
        # But need to keep reference for Tkinter itself if not using CTkImage directly
        thumbnail_label.image = photo # Keep reference like before

# --- Downloading Logic ---

def download_finished(success, message, return_code=None):
    """Handles actions after download attempt."""
    progress_bar.stop()
    progress_bar.configure(mode='determinate')
    progress_bar.set(1.0 if success else 0)

    status_label.configure(text=f"Status: {'Complete!' if success else 'Failed!'}")

    if success:
        messagebox.showinfo("Success", message)
    else:
        full_message = f"Download Failed:\n{message}"
        if return_code is not None:
            full_message += f"\n(yt-dlp exit code: {return_code})"
        messagebox.showerror("Error", full_message)

    ui_set_controls_state(True)
    ui_set_fetch_button_state(True)


def download_video_thread(url, format_code, subtitle_lang, save_path, output_template_str, is_audio_only, convert_to_mp3, use_archive, archive_file):
    """Handles the download process using yt-dlp subprocess."""

    app.after(0, lambda: progress_bar.configure(mode='indeterminate'))
    app.after(0, lambda: progress_bar.start())
    status_prefix = "Downloading Playlist" if is_playlist else "Downloading"
    app.after(0, lambda: status_label.configure(text=f"Status: {status_prefix} via yt-dlp..."))

    try:
        if not output_template_str.strip():
            output_template_str = "%(title)s [%(id)s].%(ext)s"
        output_template = os.path.join(save_path, output_template_str)

        command = ['yt-dlp']

        if is_audio_only:
            command.extend(['-f', 'bestaudio/best'])
            command.append('-x')
            if convert_to_mp3:
                command.extend(['--audio-format', 'mp3', '--audio-quality', '0'])
                print("INFO: MP3 conversion requested. Requires ffmpeg.")
        elif is_playlist:
             print(f"INFO: Playlist detected. Applying format '{format_code}' to all items (might fail for some).")
             command.extend(['-f', format_code])
        else:
             command.extend(['-f', format_code])

        command.extend(['--no-warnings', '--progress', '--no-overwrites'])
        command.extend(['-o', output_template])

        if subtitle_lang:
            command.extend(['--write-subs', '--sub-lang', subtitle_lang])

        if use_archive and archive_file and os.path.exists(os.path.dirname(archive_file)):
             command.extend(['--download-archive', archive_file])
             print(f"INFO: Using download archive: {archive_file}")
        elif use_archive:
             print("WARNING: 'Use Archive' checked, but archive file path is invalid. Skipping.")

        command.append(url)

        print(f"Executing command: {' '.join(command)}")

        process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', check=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

        if process.returncode == 0:
            final_message = f"{status_prefix} successful!\n(Saved to folder: {save_path})"
            if use_archive:
                 final_message += f"\n(Archive file updated: {archive_file})"
            app.after(0, download_finished, True, final_message)
        else:
            error_output = process.stderr.strip() or process.stdout.strip()
            print(f"yt-dlp failed. Return Code: {process.returncode}")
            print(f"Output:\n{error_output}")
            fail_reason = f"yt-dlp failed.\nOutput:\n{error_output[:500]}..."

            if ("ffmpeg" in error_output.lower() or "ffprobe" in error_output.lower()) and "not found" in error_output.lower():
                 fail_reason = "yt-dlp failed: ffmpeg/ffprobe not found..."
            elif "already been downloaded" in error_output.lower():
                 fail_reason = "Download skipped: File(s) already recorded in archive or exist..."
            elif "unable to extract" in error_output.lower():
                 fail_reason = f"yt-dlp failed: Unable to extract video data..."

            app.after(0, download_finished, False, fail_reason, process.returncode)

    except FileNotFoundError:
         app.after(0, download_finished, False, "yt-dlp command not found. Is it installed and in PATH?")
    except Exception as e:
        print(f"Unexpected error during download subprocess: {e}")
        print(traceback.format_exc())
        app.after(0, download_finished, False, f"An unexpected Python error occurred: {e}")
    finally:
        app.after(0, lambda: progress_bar.stop())
        # Corrected line: Use .set() for value
        app.after(0, lambda: progress_bar.configure(mode='determinate'))
        app.after(0, lambda: progress_bar.set(0)) # FIXED
        # ---


def start_fetch():
    """Starts fetching info in a new thread."""
    fetch_thread = threading.Thread(target=fetch_video_info_thread, daemon=True)
    fetch_thread.start()

def start_download():
    """Validates input and starts the download process in a new thread."""
    selected_quality_desc = quality_combobox.get()
    selected_caption_desc = caption_combobox.get()
    save_path = path_entry.get()
    url = url_entry.get()
    output_template_str = output_template_entry.get()
    is_audio_only = audio_only_checkbox.get() == 1
    convert_to_mp3 = mp3_checkbox.get() == 1 and is_audio_only
    use_archive = archive_checkbox.get() == 1
    archive_file = archive_entry.get() if use_archive else None

    if not url: messagebox.showwarning("Input Error", "URL is missing."); return
    if not selected_quality_desc and not is_audio_only: messagebox.showwarning("Input Error", "Please fetch and select a quality."); return
    if not save_path or not os.path.isdir(save_path): messagebox.showwarning("Input Error", f"Please select a valid download directory."); return
    if use_archive and (not archive_file or not os.path.exists(os.path.dirname(archive_file))):
         messagebox.showwarning("Input Error", f"Please select a valid path for the archive file."); return

    format_code = None
    if not is_audio_only:
         format_code = available_formats.get(selected_quality_desc)
         if not format_code: messagebox.showerror("Error", "Selected quality format code not found. Please fetch again."); return

    ui_set_controls_state(False)
    ui_set_fetch_button_state(False)
    status_label.configure(text="Status: Preparing download...")
    progress_bar.set(0)
    app.update_idletasks()

    print("-" * 20)
    print(f"DEBUG: Starting Download Job")
    print(f"DEBUG: URL: '{url}'")
    print(f"DEBUG: Is Playlist: {is_playlist}")
    print(f"DEBUG: Audio Only: {is_audio_only}")
    print(f"DEBUG: Convert MP3: {convert_to_mp3}")
    print(f"DEBUG: Quality Desc: '{selected_quality_desc}'")
    print(f"DEBUG: Format Code (if used): '{format_code}'")
    print(f"DEBUG: Caption Desc: '{selected_caption_desc}'")
    print(f"DEBUG: Subtitle Lang Code: '{available_captions.get(selected_caption_desc)}'")
    print(f"DEBUG: Save Path: '{save_path}'")
    print(f"DEBUG: Output Template: '{output_template_str}'")
    print(f"DEBUG: Use Archive: {use_archive}")
    print(f"DEBUG: Archive File: '{archive_file}'")
    print("-" * 20)

    download_thread = threading.Thread(
        target=download_video_thread,
        args=(url, format_code, available_captions.get(selected_caption_desc), save_path, output_template_str, is_audio_only, convert_to_mp3, use_archive, archive_file),
        daemon=True
    )
    download_thread.start()

# --- UI Helper Functions ---
def ui_set_controls_state(enabled: bool):
    """Enable/disable download-related controls."""
    state = "normal" if enabled else "disabled"
    # Use try-except blocks for robustness in case widgets haven't been created yet or window is closing
    try: quality_combobox.configure(state="readonly" if enabled else "disabled")
    except Exception: pass
    try: caption_combobox.configure(state="readonly" if enabled else "disabled")
    except Exception: pass
    try: path_entry.configure(state=state)
    except Exception: pass
    try: path_button.configure(state=state)
    except Exception: pass
    try: audio_only_checkbox.configure(state=state)
    except Exception: pass

    try:
        is_audio = audio_only_checkbox.get() == 1
        mp3_checkbox.configure(state="normal" if enabled and is_audio else "disabled")
    except Exception: pass

    try: output_template_entry.configure(state=state)
    except Exception: pass
    try: archive_checkbox.configure(state=state)
    except Exception: pass

    try:
        is_archive = archive_checkbox.get() == 1
        archive_entry.configure(state="normal" if enabled and is_archive else "disabled")
        archive_button.configure(state="normal" if enabled and is_archive else "disabled")
    except Exception: pass

    ui_set_download_button_state(enabled)


def ui_set_fetch_button_state(enabled: bool):
     try: fetch_button.configure(state="normal" if enabled else "disabled")
     except Exception: pass

def ui_set_download_button_state(enabled: bool):
    has_formats = bool(available_formats)
    try: download_button.configure(state="normal" if enabled and has_formats else "disabled")
    except Exception: pass

def ui_clear_comboboxes():
    """Clear and disable quality/caption comboboxes."""
    try:
         quality_combobox.set('')
         quality_combobox.configure(state="disabled", values=[])
    except Exception: pass
    try:
         caption_combobox.set('')
         caption_combobox.configure(state="disabled", values=[])
    except Exception: pass

def toggle_mp3_checkbox():
    """Enable/disable MP3 checkbox based on Audio Only checkbox."""
    try:
        if audio_only_checkbox.get() == 1:
            mp3_checkbox.configure(state="normal")
            # Maybe disable quality box when audio only? Or keep enabled for info? Keep enabled.
            # quality_combobox.configure(state="disabled")
        else:
            mp3_checkbox.deselect()
            mp3_checkbox.configure(state="disabled")
            # Re-enable quality box if it was disabled
            # quality_combobox.configure(state="readonly")
    except Exception: pass # Prevent error if widgets destroyed

def toggle_archive_controls():
    """Enable/disable archive file entry/button based on archive checkbox."""
    try:
        if archive_checkbox.get() == 1:
            archive_entry.configure(state="normal")
            archive_button.configure(state="normal")
        else:
            archive_entry.configure(state="disabled")
            archive_button.configure(state="disabled")
    except Exception: pass

def clear_url_and_info():
     """Clears URL entry and resets fetched info."""
     try:
         url_entry.delete(0, tk.END)
         title_label.configure(text="Title:")
         thumbnail_label.configure(image=None, text="Thumbnail")
         ui_clear_comboboxes()
         ui_set_controls_state(False) # Disable options
         status_label.configure(text="Status: Idle.")
         progress_bar.set(0)
         global video_info_json, available_formats, available_captions, is_playlist
         video_info_json = None
         available_formats = {}
         available_captions = {}
         is_playlist = False
     except Exception as e:
         print(f"Error during clear: {e}") # Handle if widgets already destroyed


# --- GUI Setup using CustomTkinter ---
app = ctk.CTk()
app.title("Advanced YouTube Downloader (vhr)")
app.geometry("800x750")

# --- Main Frame ---
main_frame = ctk.CTkFrame(app)
main_frame.pack(padx=10, pady=10, fill="both", expand=True)
main_frame.grid_columnconfigure(0, weight=1)

# --- Row 0: URL Input ---
input_frame = ctk.CTkFrame(main_frame)
input_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
input_frame.grid_columnconfigure(1, weight=1)

url_label = ctk.CTkLabel(input_frame, text="URL:")
url_label.grid(row=0, column=0, padx=(10, 5), pady=10)
url_entry = ctk.CTkEntry(input_frame, placeholder_text="Enter YouTube Video or Playlist URL", width=400)
url_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
fetch_button = ctk.CTkButton(input_frame, text="Fetch Info", width=100, command=start_fetch)
fetch_button.grid(row=0, column=2, padx=5, pady=10)
clear_button = ctk.CTkButton(input_frame, text="Clear", width=60, command=clear_url_and_info)
clear_button.grid(row=0, column=3, padx=(0, 10), pady=10)


# --- Row 1: Video Info ---
info_frame = ctk.CTkFrame(main_frame)
info_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
info_frame.grid_columnconfigure(0, weight=1)
info_frame.grid_columnconfigure(1, weight=0)

info_left_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
info_left_frame.grid(row=0, column=0, sticky="nsew", padx=(10,5), pady=5)
title_label = ctk.CTkLabel(info_left_frame, text="Title:", wraplength=500, anchor="w", justify="left")
title_label.pack(fill="x")

info_right_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
info_right_frame.grid(row=0, column=1, sticky="ne", padx=5, pady=5)
thumbnail_label = ctk.CTkLabel(info_right_frame, text="", width=240, height=135)
thumbnail_label.pack(padx=5, pady=5)

# --- Row 2: Path Selection ---
path_frame = ctk.CTkFrame(main_frame)
path_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
path_frame.grid_columnconfigure(1, weight=1)

path_label_widget = ctk.CTkLabel(path_frame, text="Save To:")
path_label_widget.grid(row=0, column=0, padx=(10, 5), pady=10)
path_entry = ctk.CTkEntry(path_frame, width=400)
path_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
path_button = ctk.CTkButton(path_frame, text="Browse...", width=80, command=lambda: select_path(path_entry))
path_button.grid(row=0, column=2, padx=(0, 10), pady=10)

# --- Row 3: Download Options ---
options_frame = ctk.CTkFrame(main_frame)
options_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
options_frame.grid_columnconfigure(1, weight=1)
options_frame.grid_columnconfigure(3, weight=1)

quality_label = ctk.CTkLabel(options_frame, text="Quality:")
quality_label.grid(row=0, column=0, padx=(10, 5), pady=5, sticky="w")
quality_combobox = ctk.CTkComboBox(options_frame, state="disabled", width=350, values=[])
quality_combobox.grid(row=0, column=1, columnspan=3, padx=5, pady=5, sticky="ew")

caption_label = ctk.CTkLabel(options_frame, text="Subtitles:")
caption_label.grid(row=1, column=0, padx=(10, 5), pady=5, sticky="w")
caption_combobox = ctk.CTkComboBox(options_frame, state="disabled", width=200, values=[])
caption_combobox.grid(row=1, column=1, padx=5, pady=5, sticky="w")

audio_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
audio_frame.grid(row=2, column=0, columnspan=4, pady=(5, 5), padx=10, sticky="w")
audio_only_checkbox = ctk.CTkCheckBox(audio_frame, text="Download Audio Only", command=toggle_mp3_checkbox)
audio_only_checkbox.grid(row=0, column=0, padx=0, pady=5, sticky="w")
mp3_checkbox = ctk.CTkCheckBox(audio_frame, text="Convert to MP3 (Requires ffmpeg)", state="disabled")
mp3_checkbox.grid(row=0, column=1, padx=(20, 0), pady=5, sticky="w")


# --- Row 4: Output Options ---
output_options_frame = ctk.CTkFrame(main_frame)
output_options_frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew")
output_options_frame.grid_columnconfigure(1, weight=1)

template_label = ctk.CTkLabel(output_options_frame, text="Filename Template:")
template_label.grid(row=0, column=0, padx=(10, 5), pady=5, sticky="w")
output_template_entry = ctk.CTkEntry(output_options_frame)
output_template_entry.insert(0, "%(title)s [%(id)s].%(ext)s")
output_template_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
template_help_label = ctk.CTkLabel(output_options_frame, text="(yt-dlp format codes)", text_color="gray", font=ctk.CTkFont(size=10))
template_help_label.grid(row=1, column=1, columnspan=2, padx=5, pady=(0,5), sticky="w")

archive_checkbox = ctk.CTkCheckBox(output_options_frame, text="Use Download Archive (Skip downloaded items)", command=toggle_archive_controls)
archive_checkbox.grid(row=2, column=0, columnspan=3, padx=(10, 5), pady=5, sticky="w")
archive_entry = ctk.CTkEntry(output_options_frame, placeholder_text="Path to archive file (.txt)", state="disabled", width=400)
archive_entry.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
archive_button = ctk.CTkButton(output_options_frame, text="Select File...", width=100, command=lambda: select_archive_file(archive_entry), state="disabled")
archive_button.grid(row=3, column=2, padx=(0, 10), pady=5)


# --- Row 5: Download Action ---
download_frame = ctk.CTkFrame(main_frame)
download_frame.grid(row=5, column=0, padx=10, pady=10, sticky="ew")
download_frame.grid_columnconfigure(0, weight=1)

download_button = ctk.CTkButton(download_frame, text="Download", command=start_download, state="disabled", height=40, font=ctk.CTkFont(size=16, weight="bold"))
download_button.grid(row=0, column=0, pady=10)


# --- Row 6: Progress ---
progress_frame = ctk.CTkFrame(main_frame)
progress_frame.grid(row=6, column=0, padx=10, pady=(5, 10), sticky="ew")
progress_frame.grid_columnconfigure(0, weight=1)

status_label = ctk.CTkLabel(progress_frame, text="Status: Idle. Install yt-dlp (pip install yt-dlp) if needed.", anchor="w")
status_label.grid(row=0, column=0, padx=10, pady=(5,0), sticky="ew")
progress_bar = ctk.CTkProgressBar(progress_frame, mode='determinate')
progress_bar.set(0)
progress_bar.grid(row=1, column=0, padx=10, pady=(5,10), sticky="ew")

# --- Initial UI State ---
ui_set_controls_state(False)

# --- Run App ---
if __name__ == "__main__":
    app.mainloop()

# <<<--- End of Code --- >>>