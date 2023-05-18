"""
Raspberry Pi coordinator

Configuration of Worker on Raspberry Pi

(c) 2021 Olivier Friard
"""

PORT = 5000
DEFAULT_PICTURE_WIDTH = 640
DEFAULT_PICTURE_HEIGHT = 480

# VIDEO_ARCHIVE = "/home/pi/worker/static/video_archive"
# TIME_LAPSE_ARCHIVE = "/home/pi/worker/static/pictures_archive"
# LIVE_PICTURES_ARCHIVE = "/home/pi/worker/static/live_pictures"

STATIC_DIR = "static"
VIDEO_ARCHIVE_DIR = "video_archive"
TIME_LAPSE_ARCHIVE_DIR = "pictures_archive"
LIVE_PICTURES_ARCHIVE_DIR = "live_pictures"

DEFAULT_VIDEO_DURATION = 10  # seconds
DEFAULT_FPS = 10
DEFAULT_VIDEO_WIDTH = 640
DEFAULT_VIDEO_HEIGHT = 480
DEFAULT_VIDEO_QUALITY = 1  # Mb/s

LOG_PATH = "/home/pi/worker/worker.log"

WIFI_INTERFACE = "wlan0"
