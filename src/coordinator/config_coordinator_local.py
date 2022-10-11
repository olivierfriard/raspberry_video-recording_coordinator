# configuration file for coordinator.py

TIME_OUT = 10
SERVER_PORT = ":5000"
DEBUG = True
PROTOCOL = "http://"

IP_RANGES = (
    ("192.168.2.1", [1, 12]),
    # ("130.192.200.1", [160, 160]),
)

# IP_RANGES = (("130.192.200.1", [160, 160]),)

# path for receiving video from raspberries
VIDEO_ARCHIVE = "/tmp"

REFRESH_INTERVAL = 60  # seconds -> 10 min

# seconds between 2 pictures in time lapse mode
DEFAULT_INTERVAL = 20

PICTURE_RESOLUTIONS = ["3280x2464", "1920x1080", "1640x1232", "1640x922", "1280x720", "640x480"]
DEFAULT_PICTURE_RESOLUTION = 4  # index of RESOLUTIONS (list starts at index 0!)
PICTURE_BRIGHTNESS = 0
PICTURE_SATURATION = 1
PICTURE_CONTRAST = 1
PICTURE_SHARPNESS = 2
PICTURE_GAIN = 1
PICTURE_ROTATION = 0
PICTURE_HFLIP = False
PICTURE_VFLIP = False
PICTURE_ANNOTATION = True

TIME_LAPSE = False
TIME_LAPSE_DURATION = 0
TIME_LAPSE_WAIT = 0

# see https://www.raspberrypi.org/documentation/raspbian/applications/camera.md
VIDEO_MODES = ["1920x1080", "1280x2464", "3280x2464", "1640x1232", "1640x922", "1280x720", "640x480"]
DEFAULT_VIDEO_MODE = 5

MIN_VIDEO_FPS = 1
MAX_VIDEO_FPS = 30
DEFAULT_FPS = 10

DEFAULT_VIDEO_DURATION = 2400  # seconds
VIDEO_BRIGHTNESS = 0
VIDEO_SATURATION = 1
VIDEO_CONTRAST = 1
VIDEO_SHARPNESS = 1
VIDEO_GAIN = 1
VIDEO_ROTATION = 0
VIDEO_HFLIP = False
VIDEO_VFLIP = False

MIN_VIDEO_QUALITY = 1
MAX_VIDEO_QUALITY = 10
DEFAULT_VIDEO_QUALITY = 1  # Mbp/s

CLIENT_PROJECT_DIRECTORY = "/home/pi/worker"

# keys are widget accessible names
RPI_DEFAULTS = {
    "picture resolution": PICTURE_RESOLUTIONS[DEFAULT_PICTURE_RESOLUTION],
    "picture brightness": PICTURE_BRIGHTNESS,
    "picture contrast": PICTURE_CONTRAST,
    "picture saturation": PICTURE_SATURATION,
    "picture sharpness": PICTURE_SHARPNESS,
    "picture gain": PICTURE_GAIN,
    "picture rotation": PICTURE_ROTATION,
    "picture hflip": PICTURE_HFLIP,
    "picture vflip": PICTURE_VFLIP,
    "time lapse": TIME_LAPSE,
    "time lapse duration": TIME_LAPSE_DURATION,
    "time lapse wait": TIME_LAPSE_WAIT,
    "picture annotation": PICTURE_ANNOTATION,
    "video mode": VIDEO_MODES[DEFAULT_VIDEO_MODE],
    "video quality": DEFAULT_VIDEO_QUALITY,
    "FPS": DEFAULT_FPS,
    "video duration": DEFAULT_VIDEO_DURATION,
    "video brightness": VIDEO_BRIGHTNESS,
    "video contrast": VIDEO_CONTRAST,
    "video saturation": VIDEO_SATURATION,
    "video sharpness": VIDEO_SHARPNESS,
    "video gain": VIDEO_GAIN,
    "video rotation": VIDEO_ROTATION,
    "video hflip": VIDEO_HFLIP,
    "video vflip": VIDEO_VFLIP,
}

STATUS_TAB_INDEX = 0
TIME_LAPSE_TAB_INDEX = 1
VIDEO_STREAMING_TAB_INDEX = 2
VIDEO_REC_TAB_INDEX = 3
