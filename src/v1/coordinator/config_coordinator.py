# configuration file for master.py

RASPBERRY_MAC_ADDR = {
"b8:27:eb:8d:8a:6d": "rasp01",
"b8:27:eb:bd:51:14": "rasp02",
"b8:27:eb:15:34:06": "rasp03",
"b8:27:eb:23:d5:e5": "rasp04",
"b8:27:eb:d0:29:1d": "rasp05",
"b8:27:eb:29:a0:45": "rasp06",
"b8:27:eb:8f:c7:6a": "rasp07",
"b8:27:eb:69:46:b9": "rasp08",
"b8:27:eb:cc:5b:fe": "rasp09",
"b8:27:eb:2a:f2:79": "rasp10",
"b8:27:eb:ca:5a:aa": "rasp11",
"b8:27:eb:b2:48:e1": "rasp12",
"b8:27:eb:bd:2d:cd": "rasp13",
"b8:27:eb:c7:1d:61": "rasp14",
"b8:27:eb:4e:ba:e0": "rasp15",
"b8:27:eb:29:46:7e": "rasp16",

# riserva
#"b8:27:eb:b3:ea:92": "rasp17",
#"b8:27:eb:09:84:b9": "rasp18",
}

TIME_OUT = 10
SERVER_PORT = 5000
DEBUG = True
WLAN_INTERVAL = [2, 32]

# path for receiving video from raspberries
#VIDEO_ARCHIVE  = "/media/girini/Backup1/RAGANELLA2019/video"
VIDEO_ARCHIVE  = "/home/user/video"


REFRESH_INTERVAL = 600 # seconds -> 10 min

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
