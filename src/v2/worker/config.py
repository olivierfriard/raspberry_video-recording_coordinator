"""
Raspberry Cam System

Configuration of Worker on Raspberry Pi

(c) 2021-2023 Olivier Friard
"""

PORT = 5000
DEFAULT_PICTURE_WIDTH = 640
DEFAULT_PICTURE_HEIGHT = 480

STATIC_DIR = "static"
VIDEO_ARCHIVE_DIR = "video_archive"
TIME_LAPSE_ARCHIVE_DIR = "pictures_archive"
LIVE_PICTURES_ARCHIVE_DIR = "live_pictures"

DEFAULT_VIDEO_DURATION = 10  # seconds
DEFAULT_FPS = 10
DEFAULT_VIDEO_WIDTH = 640
DEFAULT_VIDEO_HEIGHT = 480
DEFAULT_VIDEO_QUALITY = 1  # Mb/s

LOG_PATH = "worker.log"

WIFI_INTERFACE = "wlan0"
