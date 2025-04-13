# Enhanced YouTube Downloader (yt-dlp)

A Python-based GUI application for downloading YouTube videos using yt-dlp with support for various quality options and subtitles.

## Features

- User-friendly graphical interface built with tkinter
- Video quality selection with detailed format information
- Subtitle/Caption download support
- Thumbnail preview
- Progress tracking
- Support for various video formats and resolutions
- Smart format sorting (prioritizes MP4, combined video+audio, higher resolutions)
- Flexible download directory selection

## Requirements

- Python 3.x
- yt-dlp (`pip install yt-dlp`)
- Pillow (`pip install Pillow`)
- requests (`pip install requests`)
- tkinter (usually comes with Python)

## Installation

1. Make sure you have Python installed on your system
2. Install the required packages:
   ```bash
   pip install yt-dlp Pillow requests
   ```
3. Clone or download this repository
4. Run `youtube_downloader_gui.py`

## Usage

1. Launch the application by running `youtube_downloader_gui.py`
2. Paste a YouTube URL into the input field
3. Click "Fetch Info" to get video details and available formats
4. Select your desired video quality from the dropdown menu
5. Optionally select subtitles if available
6. Choose a download directory using the "Select Folder" button
7. Click "Download Selected Quality" to start the download

## Features in Detail

### Video Formats

- Automatically sorts and presents available formats with details like:
  - Resolution
  - File format
  - File size (when available)
  - Video+Audio/Video Only/Audio Only indicators
  - Format-specific details (e.g., 60fps where applicable)

### Subtitle Support

- Download subtitles in various languages (when available)
- Supports both manual and auto-generated captions
- Clear indication of auto-generated captions

### Download Management

- Progress tracking
- Status updates
- Error handling with detailed messages
- Background processing to keep UI responsive

## Notes

- The application requires an active internet connection
- Download speeds depend on your internet connection and YouTube's servers
- Some videos may have restricted formats or may not be available for download
- The application uses yt-dlp which is regularly updated to handle YouTube changes

## Troubleshooting

If you encounter any issues:

1. Ensure yt-dlp is up to date:
   ```bash
   pip install --upgrade yt-dlp
   ```
2. Check if the YouTube URL is valid and accessible
3. Verify you have write permissions in the selected download directory
4. Check your internet connection

## License

This project is open source and available for personal use.
