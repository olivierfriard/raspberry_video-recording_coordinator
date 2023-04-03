# configuration file for coordinator.py


TIME_OUT = 10
SERVER_PORT = 5000
DEBUG = True


IP_RANGES = (("192.168.1.1", [2, 2]),)

WLAN_INTERVAL = [128, 254]


# path for receiving video from raspberries
VIDEO_ARCHIVE  = "/tmp"


REFRESH_INTERVAL = 300 # seconds -> 10 min

# seconds between 2 pictures in time lapse mode
DEFAULT_INTERVAL = 20




PICTURE_RESOLUTIONS = ["3280x2464", "1920x1080", "1640x1232", "1640x922", "1280x720", "640x480"]
DEFAULT_PICTURE_RESOLUTION = 4 # index of RESOLUTIONS (list starts at index 0!)


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

MIN_VIDEO_FPS = 1
MAX_VIDEO_FPS = 30
DEFAULT_FPS = 10

DEFAULT_VIDEO_DURATION = 2400 # seconds

MIN_VIDEO_QUALITY = 1
MAX_VIDEO_QUALITY = 10
DEFAULT_VIDEO_QUALITY = 1 # Mbp/s

CLIENT_PROJECT_DIRECTORY = "/home/pi/video"
