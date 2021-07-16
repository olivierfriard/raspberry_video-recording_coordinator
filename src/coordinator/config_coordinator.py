# configuration file for master.py

RASPBERRY_MAC_ADDR = {


}

TIME_OUT = 10
SERVER_PORT = 5000
DEBUG = True
WLAN_INTERVAL = [128, 254]

# path for receiving video from raspberries
VIDEO_ARCHIVE  = "/data/tmp"


REFRESH_INTERVAL = 300 # seconds -> 10 min

# seconds between 2 pictures in time lapse mode
DEFAULT_INTERVAL = 20

# number of columns in the interface
GUI_COLUMNS_NUMBER = 1 if len(RASPBERRY_MAC_ADDR) == 1 else 2

GUI_COLUMNS_NUMBER = 1

RESOLUTIONS = ["3280x2464", "1920x1080", "1640x1232", "1640x922", "1280x720", "640x480"]
DEFAULT_RESOLUTION = 4 # index of RESOLUTIONS (list starts at index 0!)

# see https://www.raspberrypi.org/documentation/raspbian/applications/camera.md
VIDEO_MODES = [
"1920x1080",
"1280x2464",
"3280x2464",
"1640x1232",
"1640x922",
"1280x720",
"640x480"
]
DEFAULT_VIDEO_MODE = 5

DEFAULT_FPS = 10

DEFAULT_VIDEO_DURATION = 2400 # seconds

DEFAULT_VIDEO_QUALITY = 1 # Mbp/s

CLIENT_PROJECT_DIRECTORY = "/home/pi/video"
