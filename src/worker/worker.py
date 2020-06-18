"""

Video recording worker
This program must be launched on each Raspberry Pi device
See the documentation on https://github.com/olivierfriard/raspberry_video-recording_coordinator


"""

__version__ = "0.0.3"

PORT = 5000

import os
import threading
import datetime
import glob
import time
import subprocess
import socket
import logging

from flask import Flask, request, send_from_directory

DEFAULT_PICTURE_WIDTH = 640
DEFAULT_PICTURE_HEIGHT = 480

VIDEO_ARCHIVE = "/home/pi/projects/video/static/video_archive"
DEFAULT_VIDEO_DURATION = 10 # seconds
DEFAULT_FPS = 10
DEFAULT_VIDEO_WIDTH = 640
DEFAULT_VIDEO_HEIGHT = 480
DEFAULT_VIDEO_QUALITY = 1 # Mb/s

LOG_PATH = "/home/pi/projects/video/server.log"

logging.basicConfig(filename=LOG_PATH,
                    filemode="a",
                    format='%(asctime)s, %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)

app = Flask(__name__, static_url_path='/static')

thread = threading.Thread()


@app.route("/")
def home():
    return """
video control server v. {__version__}<br>
<br>
hostname: {hostname}<br>
date time on server: {datetime}<br>
<br>
<a href="/status">server status</a><br>
<a href="/shutdown">shutdown server</a><br>
<br>
<a href="/video_list">list of video on server</a><br>
""".format(__version__=__version__,
           hostname=socket.gethostname(),
           datetime=datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", " "))


@app.route("/status")
def status():
    global thread
    try:
        logging.info("thread is alive: {}".format(thread.is_alive()))
        if thread.is_alive():
            thread_info = {"status": "OK",
                           "server_datetime": datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", " "),
                           "video_recording": True,
                           "duration": thread.duration,
                           "started_at": thread.started_at,
                           "w": thread.w,
                           "h": thread.h,
                           "fps": thread.fps,
                           "quality": thread.quality,
                           "server_version": __version__}
        else:
            thread_info = {"status": "OK",
                           "server_datetime": datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", " "),
                           "video_recording": False,
                           "server_version": __version__}
        return str(thread_info)

    except Exception:
        return str("no thread")



class Raspivid_thread(threading.Thread):

    def __init__(self, duration, w, h, fps, quality, prefix):
        threading.Thread.__init__(self)
        self.duration = duration
        self.w = w
        self.h = h
        self.fps = fps
        self.quality = quality
        self.prefix = prefix

        logging.info("thread args: {} fps: {} resolution: {}x{} quality: {} prefix:{}".format(duration, fps, w, h, quality, prefix))


    def run(self):
        logging.info("start  thread")
        file_name = datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", "_").replace(":", "")
        cmd = ("raspivid "
           + "-t {} ".format(self.duration * 1000)
           + "-w {w} -h {h} ".format(w=self.w, h=self.h)
           + "-fps {} ".format(self.fps)
           + "-b {} ".format(self.quality * 1000000)
           + "-o {VIDEO_ARCHIVE}/{hostname}_{prefix}_{file_name}.h264".format(VIDEO_ARCHIVE=VIDEO_ARCHIVE,
                                                                     file_name=file_name,
                                                                     prefix=self.prefix,
                                                                     hostname=socket.gethostname()))

        logging.info(cmd)
        self.started_at = datetime.datetime.now().replace(microsecond=0).isoformat()

        os.system(cmd)


class Blink_thread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)


    def run(self):
        logging.info("start  blinking")

        os.system("bash blink_sudo.bash")



@app.route("/start_video")
def start_video():

    global thread

    if thread.is_alive():
        return str({"status": "Video already recording"})

    duration = request.args.get("duration", default = DEFAULT_VIDEO_DURATION, type = int)
    w = request.args.get("w", default = DEFAULT_VIDEO_WIDTH, type = int)
    h = request.args.get("h", default = DEFAULT_VIDEO_HEIGHT, type = int)
    fps = request.args.get("fps", default = DEFAULT_FPS, type = int)
    quality = request.args.get("quality", default = DEFAULT_VIDEO_QUALITY, type = int)
    prefix = request.args.get("prefix", default="", type = str)

    logging.info("Starting video for {} min ({}x{})".format(duration, w, h))
    try:
        #thread = threading.Thread(target=start_raspivid, args=[duration, w, h, fps, quality])
        #thread.start()
        thread = Raspivid_thread(duration, w, h, fps, quality, prefix)
        thread.start()

        logging.info("Video started")
        return str({"status": "Video recording"})
    except Exception:
        logging.info("Video not started")
        return str({"status": "Video not recording"})


@app.route("/stop_video")
def stop_video():
    os.system("sudo killall raspivid")
    time.sleep(2)
    if not thread.is_alive():
        result = {"result": "video stopped"}
    else:
        result = {"result": "video not stopped"}
    return str(result)


@app.route("/blink")
def blink():
    thread = Blink_thread()
    thread.start()
    result = {"result": "blinking"}
    return str(result)

@app.route("/sync_time/<date>/<hour>")
def sync_time(date, hour):
    completed = subprocess.run(['sudo', 'timedatectl','set-time', "{date} {hour}".format(date=date, hour=hour)]) # 2015-11-23 10:11:22
    if completed.returncode:
        return str({"result": "time not synchronised",
                    "current date": datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", " ")})
    else:
        return str({"result": "time synchronised",
                    "current date": datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", " ")})


@app.route("/one_picture")
def one_picture():
    os.system("rm static/live.jpg")
    w = request.args.get("w", default = DEFAULT_PICTURE_WIDTH, type = int)
    h = request.args.get("h", default = DEFAULT_PICTURE_HEIGHT, type = int)
    os.system(("raspistill --nopreview "
               "--timeout 1 "
               "-w {w} -h {h} "
               "--annotate '{hostname} {datetime}' "
               "-o static/live.jpg").format(w=w,
                                            h=h,
                                            datetime=datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", " "),
                                            hostname=socket.gethostname()))
    return str({"result": "OK"})


@app.route("/video_list")
def video_list():
    return str({"video_list": [x.replace(VIDEO_ARCHIVE + "/", "") for x in glob.glob(VIDEO_ARCHIVE + "/*.h264")]})


@app.route("/get_video/<file_name>")
def get_video(file_name):
    print(VIDEO_ARCHIVE + "/" + file_name)
    return send_from_directory(VIDEO_ARCHIVE, file_name, as_attachment=True)


@app.route("/command/<command_to_run>")
def command(command_to_run):
    try:
        process = subprocess.run(command_to_run.split(" "), stdout=subprocess.PIPE)
        results = {"return_code": process.returncode, "output": process.stdout.decode("utf-8")}
        return str(results)
    except Exception:
        return str({"status": "error"})


@app.route("/get_log")
def get_log():
    try:
        return str("<pre>" + open(LOG_PATH).read() + "</pre>")
    except Exception:
        return str({"status": "error"})


@app.route("/delete_all_video")
def delete_all_video():
    try:
        os.system("rm -f {VIDEO_ARCHIVE}/*.h264".format(VIDEO_ARCHIVE=VIDEO_ARCHIVE))
        return str({"status": "OK", "msg": "all video deleted"})
    except Exception:
        return str({"status": "error"})


@app.route("/reboot")
def reboot():
    os.system("sudo reboot")
    return str({"status": "reboot requested"})



@app.route("/shutdown")
def shutdown():
    os.system("sudo shutdown now")
    return str({"status": "shutdown requested"})

if __name__ == '__main__':
    logging.info("server started")
    app.debug = True
    app.run(host = '0.0.0.0',port=PORT)
