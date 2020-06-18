# configuration file for video-rec_coordinator.py


RASPBERRY_IP  = {
"rasp01": "130.192.1.101",
"rasp02": "192.168.1.102",
"rasp03": "192.168.1.103",
"rasp04": "192.168.1.104",
"rasp05": "192.168.1.105",
"rasp06": "192.168.1.106",
"rasp07": "192.168.1.107",
"rasp08": "192.168.1.108",
"rasp09": "192.168.1.109",
"rasp10": "192.168.1.110",
"rasp11": "192.168.1.111",
"rasp12": "192.168.1.112",
"rasp13": "192.168.1.113",
"rasp14": "192.168.1.114"
}

# path for receiving video from raspberries
VIDEO_ARCHIVE  = "/home/user/video_archive"

#refresh interval (in seconds)
REFRESH_INTERVAL = 600 

# seconds between 2 pictures in time lapse mode
DEFAULT_INTERVAL = 20

# number of columns in the interface
GUI_COLUMNS_NUMBER = 1 if len(RASPBERRY_IP) == 1 else 2

GUI_COLUMNS_NUMBER = 1

RESOLUTIONS = ["3280x2464", "1920x1080", "1640x1232", "1640x922", "1280x720", "640x480"]
DEFAULT_RESOLUTION = 4 # index of RESOLUTIONS (list starts at index 0!)

# see https://www.raspberrypi.org/documentation/raspbian/applications/camera.md
VIDEO_MODES = [
"1920x1080", #0
"1280x2464", #1
"3280x2464", #2
"1640x1232", #3
"1640x922",  #4
"1280x720",  #5
"640x480"    #6
]
DEFAULT_VIDEO_MODE = 5

# default value for number of frames by second
DEFAULT_FPS = 10

# defualt duration for video (in seconds)
DEFAULT_VIDEO_DURATION = 2400 

# default quality of video (in Mbp/s)
DEFAULT_VIDEO_QUALITY = 1 

# directory where the worker.py program is installed on the Raspberry Pi device
CLIENT_PROJECT_DIRECTORY = "/home/pi/projects/video"

