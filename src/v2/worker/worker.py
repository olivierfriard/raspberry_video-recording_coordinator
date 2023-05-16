"""

Raspberry Pi worker

to enable the service at boot:
sudo systemctl enable worker
"""

__version__ = "31"
__version_date__ = "2023-05-16"


VCGENCMD_PATH = "/usr/bin/vcgencmd"

from crontab import CronTab  # from python-crontab (not crontab)

import threading
import datetime
import glob
import time
import subprocess
import socket
import logging

# required by get_hw_addr function
import fcntl
import socket
import struct

# import base64
import pathlib as pl
import shutil
import hashlib
import json

from functools import wraps

import config as cfg


def is_camera_detected():
    """
        check if camera is plugged


        Available cameras
    -----------------
    0 : imx219 [3280x2464] (/base/soc/i2c0mux/i2c@1/imx219@10)
        Modes: 'SRGGB10_CSI2P' : 640x480 [206.65 fps - (1000, 752)/1280x960 crop]
                                 1640x1232 [41.85 fps - (0, 0)/3280x2464 crop]
                                 1920x1080 [47.57 fps - (680, 692)/1920x1080 crop]
                                 3280x2464 [21.19 fps - (0, 0)/3280x2464 crop]
               'SRGGB8' : 640x480 [206.65 fps - (1000, 752)/1280x960 crop]
                          1640x1232 [41.85 fps - (0, 0)/3280x2464 crop]
                          1920x1080 [47.57 fps - (680, 692)/1920x1080 crop]
                          3280x2464 [21.19 fps - (0, 0)/3280x2464 crop]

    """
    process = subprocess.run(["libcamera-hello", "--list-cameras"], stdout=subprocess.PIPE)
    output = process.stdout.decode("utf-8").strip()
    return output


def get_hw_addr(ifname):
    """
    return hw addr
    get_hw_addr(WIFI_INTERFACE)
    """

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        info = fcntl.ioctl(s.fileno(), 0x8927, struct.pack("256s", bytes(ifname, "utf-8")[:15]))
        return ":".join("%02x" % b for b in info[18:24])
    except:
        return "Not determined"


def get_ip():
    """
    return IP address. Does not need to be connected to internet
    https://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib
    """

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(("10.255.255.255", 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = "127.0.0.1"
    finally:
        s.close()
    return IP


def get_timezone():
    try:
        return str(datetime.datetime.now().astimezone().tzinfo.utcoffset(None).seconds / 3600)
    except:
        return "Not determined"


def get_wifi_ssid():
    """
    Get the WiFi name
    """

    process = subprocess.run(["/usr/sbin/iwgetid"], stdout=subprocess.PIPE)
    output = process.stdout.decode("utf-8").strip()
    if output:
        try:
            return output.split('"')[1]
        except:
            return output
    else:
        return "not connected to wifi"


def video_streaming_active():
    """
    check if uv4l process is present
    """

    process = subprocess.run(["ps", "auxwg"], stdout=subprocess.PIPE)
    processes_list = process.stdout.decode("utf-8").split("\n")
    return len([x for x in processes_list if "/usr/bin/vlc -I dummy stream:///dev/stdin" in x]) > 0


def recording_video_active():
    """
    check if libcamera-vid process is present
    """
    process = subprocess.run(["ps", "auxwg"], stdout=subprocess.PIPE)
    processes_list = process.stdout.decode("utf-8").split("\n")
    return len([x for x in processes_list if "libcamera-vid" in x and "libcamera-vid -t 0" not in x]) > 0


def time_lapse_active():
    """
    check if libcamera-still process is present
    """
    process = subprocess.run(["ps", "auxwg"], stdout=subprocess.PIPE)
    processes_list = process.stdout.decode("utf-8").split("\n")
    return len([x for x in processes_list if "libcamera-still" in x and " -q " in x]) > 0


def get_cpu_temperature() -> str:
    """
    get temperature of the CPU
    """
    process = subprocess.run([VCGENCMD_PATH, "measure_temp"], stdout=subprocess.PIPE)
    output = process.stdout.decode("utf-8").strip()
    if output:
        try:
            return output.split("=")[1].replace("'", "°")
        except:
            return "not determined"
    else:
        return "not determined"


def get_free_space() -> str:
    """
    free disk space in Gb
    """
    stat = shutil.disk_usage("/home/pi")
    return f"{round(stat.free / 1024 / 1024 / 1024, 2)} Gb"


def get_uptime():
    process = subprocess.run(["uptime", "-p"], stdout=subprocess.PIPE)
    output = process.stdout.decode("utf-8").strip()
    return output


def datetime_now_iso():
    return datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", " ")


class Libcamera_vid_thread(threading.Thread):
    """
    Class for recording video using a thread
    """

    def __init__(self, parameters: dict):
        threading.Thread.__init__(self)
        self.parameters = parameters

    def run(self):
        logging.info("start libcamera-vid thread")

        command_line = [
            "/usr/bin/libcamera-vid",
        ]

        for key in self.parameters:

            if key in ["prefix", "annotate", "key"]:
                continue
            if self.parameters[key] == "True":
                command_line.extend([f"--{key}"])
            elif self.parameters[key] != "False":
                command_line.extend([f"--{key}", f"{self.parameters[key]}"])

        file_name = datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", "_").replace(":", "")
        prefix = (self.parameters["prefix"] + "_") if self.parameters.get("prefix", "") else ""

        file_path = f"{cfg.VIDEO_ARCHIVE}/{socket.gethostname()}_{prefix}{file_name}.h264"

        command_line.extend(["-o", file_path])

        logging.info(" ".join(command_line))

        self.started_at = datetime.datetime.now().replace(microsecond=0).isoformat()

        subprocess.run(command_line)

        # md5sum
        process = subprocess.run(["md5sum", file_path], stdout=subprocess.PIPE)

        try:
            with open(
                f"{cfg.VIDEO_ARCHIVE}/{socket.gethostname()}_{self.parameters['prefix']}_{file_name}.md5sum", "w"
            ) as f_out:
                f_out.write(process.stdout.decode("utf-8"))
        except Exception:
            logging.warning(f"MD5SUM writing failed for {file_path}")


class Blink_thread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        logging.info("start blinking")
        subprocess.run(["bash", "blink_sudo.bash"])


class Video_streaming_thread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        logging.info("start video streaming")
        subprocess.run(["bash", "stream_video.bash"])


from flask import Flask, request, send_from_directory, Response

while True:
    try:
        logging.basicConfig(
            filename=cfg.LOG_PATH,
            filemode="a",
            format="%(asctime)s, %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            level=logging.DEBUG,
        )
        break
    except FileNotFoundError:
        print("log file path not found. Use server.log")
        LOG_PATH = "server.log"
        break


# load security key
if pl.Path("/boot/worker_security_key").is_file():
    with pl.Path("/boot/worker_security_key").open() as f_in:
        security_key_sha256 = f_in.read().strip()
    logging.info("Security key loaded")
else:
    security_key_sha256 = ""
    logging.info("Security key file not found")


# create static directory
pl.Path(cfg.STATIC_DIR).mkdir(parents=True, exist_ok=True)

# create VIDEO_ARCHIVE_DIR
(pl.Path(cfg.STATIC_DIR) / pl.Path(cfg.VIDEO_ARCHIVE_DIR)).mkdir(parents=True, exist_ok=True)


# create TIME_LAPSE_ARCHIVE_DIR
(pl.Path(cfg.STATIC_DIR) / pl.Path(cfg.TIME_LAPSE_ARCHIVE_DIR)).mkdir(parents=True, exist_ok=True)


app = Flask(__name__, static_url_path="/" + cfg.STATIC_DIR)

thread = threading.Thread()


def security_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if security_key_sha256:

            if not request.values.get("key", ""):
                status_code = Response(status=204)
                return status_code

            if hashlib.sha256(request.values.get("key", "").encode("utf-8")).hexdigest() != security_key_sha256:
                status_code = Response(
                    status=204
                )  # 204 No Content     The server successfully processed the request, and is not returning any content.
                return status_code

        return f(*args, **kwargs)

    return decorated_function


@app.route("/")
def home():
    return f"""<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Raspberry Pi worker service">
<meta name="author" content="Olivier Friard">
<title>Raspberry Pi worker</title>
</head>
<style>body {{font-family: Arial, Helvetica, sans-serif;}}</style>
</body>
<h1>Raspberry Pi worker</h1>
<b>id: {socket.gethostname()}</b><br>
<br>
Worker version: <b>{__version__}</b> ({__version_date__})<br>
<br>
IP address: {get_ip()}<br>
MAC Addr: {get_hw_addr(cfg.WIFI_INTERFACE)}<br>
date/time: {datetime_now_iso()} timezone:{get_timezone()} <br>
CPU temperature: <b>{get_cpu_temperature()}</b><br>
Uptime: <b>{get_uptime()}</b><br>
<!--
<br>
<a href="/status">server status</a><br>
<a href="/shutdown">shutdown server</a><br>
<br>
<a href="/video_list">list of video on server</a><br>
-->
</body>
</html>
"""


@app.route(
    "/status",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def status():

    # global thread
    try:
        # logging.info(f"thread is alive: {thread.is_alive()}")

        server_info = {
            "status": "OK",
            "server_datetime": datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", " "),
            "server_version": __version__,
            "MAC_addr": get_hw_addr(cfg.WIFI_INTERFACE),
            "hostname": socket.gethostname(),
            "IP_address": get_ip(),
            "video_streaming_active": video_streaming_active(),
            "wifi_essid": get_wifi_ssid(),
            "CPU temperature": get_cpu_temperature(),
            "free disk space": get_free_space(),
            "camera detected": is_camera_detected(),
            "uptime": get_uptime(),
            "time_lapse_active": time_lapse_active(),
            "video_recording": recording_video_active(),
        }

        return server_info

    except Exception:
        return {"status": "Not available"}


@app.route(
    "/video_streaming/<action>",
    methods=(
        "GET",
        "POST",
    ),
)
def video_streaming(action):
    """
    start/stop video streaming with uv4l

    DEPRECATED
                see /etc/uv4l/uv4l-raspicam.conf for default configuration
                sudo uv4l -nopreview --auto-video_nr --driver raspicam --encoding mjpeg --width 640 --height 480 --framerate 10 --server-option '--port=9090'
                --server-option '--max-queued-connections=30' --server-option '--max-streams=25' --server-option '--max-threads=29'

    libcamera-vid -t 0 --inline --listen -o - | cvlc stream:///dev/stdin --sout '#rtp{sdp=rtsp://:8554/stream}' :demux=h264

    """
    # kill current streaming
    try:
        subprocess.run(["sudo", "pkill", "vlc"])
        time.sleep(2)
    except Exception:
        return {"msg": "Problem trying to stop the video streaming"}

    if action == "stop":
        return {"msg": "video streaming stopped"}

    if action == "start":

        try:
            thread = Video_streaming_thread()
            thread.start()
            return {"msg": "video streaming started"}
        except Exception:
            return {"msg": "video streaming not started"}

        """
        try:
            subprocess.run(
                [
                    "sudo",
                    "uv4l",
                    "-nopreview",
                    "--auto-video_nr",
                    "--driver",
                    "raspicam",
                    "--encoding",
                    "mjpeg",
                    "--width",
                    str(width),
                    "--height",
                    str(height),
                    "--framerate",
                    "5",
                    "--server-option",
                    "--port=9090",
                    "--server-option",
                    "--max-queued-connections=30",
                    "--server-option",
                    "--max-streams=25",
                    "--server-option",
                    "--max-threads=29",
                ]
            )
            return {"msg": "video streaming started"}
        except Exception:
            return {"msg": "video streaming not started"}
        """


'''
@app.route("/set_hostname/<hostname>")
def set_hostname(hostname):
    """
    set client hostname
    """
    subprocess.run(["sudo", "hostnamectl", "set-hostname", hostname])
    return str({"new_hostname": socket.gethostname()})
'''

'''
@app.route("/add_key/<key>")
def add_key(key):
    """
    add coordinator public key to ~/.ssh/authorized_keys
    """
    try:
        file_content = base64.b64decode(key).decode("utf-8")
        dir_exists = (pathlib.Path.home() / pathlib.Path(".ssh")).is_dir()
        logging.info(f"dir .ssh exists? {dir_exists}")
        if not (pathlib.Path.home() / pathlib.Path(".ssh")).is_dir():
            subprocess.run(["mkdir", str(pathlib.Path.home() / pathlib.Path(".ssh"))])
            logging.info(f".ssh directory created")

        with open(pathlib.Path.home() / pathlib.Path(".ssh") / pathlib.Path("authorized_keys"), "w") as f_out:
            f_out.write(file_content)
            logging.info(f"Coordinator public key written in .ssh/authorized_keys")
        return {"msg": "file authorized_keys created"}
    except:
        return {"msg": "error"}
'''


@app.route(
    "/schedule_time_lapse",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def schedule_time_lapse():
    """
    schedule the time lapse using crontab of user pi
    see https://pypi.org/project/crontab/
    """

    crontab_event = request.values.get("crontab", "")
    if not crontab_event:
        return {"error": True, "msg": "Time lapse NOT configured. Crontab event not found"}

    logging.info(f"crontab event: {crontab_event}")

    command_line = [
        "libcamera-still",
        "-q",
        "90",
    ]

    for key in request.values:

        if key in ["timelapse", "timeout", "prefix", "annotate", "key", "crontab"]:
            continue
        if request.values[key] == "True":
            command_line.extend([f"--{key}"])
        elif request.values[key] != "False":
            command_line.extend([f"--{key}", f"{request.values[key]}"])

    # use Epoch time for file name
    # command_line.extend(["--timestamp"])

    if (
        "timeout" in request.values
        and request.values["timeout"] != "0"
        and "timelapse" in request.values
        and request.values["timelapse"] != "0"
    ):
        command_line.extend([f"--timeout", str(int(request.values["timeout"]) * 1000)])
        command_line.extend([f"--timelapse", str(int(request.values["timelapse"]) * 1000)])
        comment = f'time-lapse for {request.values["timeout"]} s (every {request.values["timelapse"]} s)'

    command_line.extend(
        [
            "-o",
            str(pl.Path(cfg.TIME_LAPSE_ARCHIVE) / pl.Path(f"{socket.gethostname()}_%04d").with_suffix(".jpg")),
        ]
    )

    """
    prefix = (request.values["prefix"] + "_" ) if request.values.get("prefix", "") else ""
    file_path = f"{cfg.VIDEO_ARCHIVE}/{socket.gethostname()}_{prefix}" + "$(/usr/bin/date_crontab_helper).h264"
    command_line.extend(["-o", file_path])
    """

    logging.info(" ".join(command_line))

    cron = CronTab(user="pi")
    job = cron.new(command=" ".join(command_line), comment=comment)
    try:
        job.setall(crontab_event)
    except Exception:
        return {"error": True, "msg": f"Time lapse NOT scheduled. '{crontab_event}' is not valid."}

    cron.write()

    return {"error": False, "msg": "Time lapse scheduled"}


@app.route(
    "/view_time_lapse_schedule",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def view_time_lapse_schedule():
    """
    send all time lapse crontab schedule
    """
    cron = CronTab(user="pi")
    output = []
    try:
        for job in cron:
            if "libcamera-still" in job.command:
                output.append(
                    [str(job.minutes), str(job.hours), str(job.dom), str(job.month), str(job.dow), job.comment]
                )

    except Exception:
        return {"error": True, "msg": f"Error during time lapse schedule view."}

    return {"error": False, "msg": output}


@app.route(
    "/delete_time_lapse_schedule",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def delete_time_lapse_schedule():
    """
    delete all time lapse schedule
    """
    cron = CronTab(user="pi")
    try:
        for job in cron:
            if "libcamera-still" in job.command:
                cron.remove(job)
        cron.write()
    except Exception:
        return {"error": True, "msg": f"Time lapse schedule NOT deleted."}

    return {"error": False, "msg": f"Time lapse schedule deleted."}


@app.route(
    "/start_video",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def start_video():
    """
    Start video recording
    """

    global thread

    if recording_video_active():
        return {"msg": "Video already recording"}

    if time_lapse_active():
        return {"msg": "The video cannot be recorded because the time lapse is active"}

    if video_streaming_active():
        return {"msg": "The video cannot be recorded because the video streaming is active"}

    logging.info(
        f"Starting video recording for {int(request.values['timeout']) / 1000} s ({request.values['width']}x{request.values['height']})"
    )
    try:
        thread = Libcamera_vid_thread(request.values)
        thread.start()

        logging.info("Video recording started")
        return {"msg": "Video recording"}
    except Exception:
        logging.info("Video recording not started")
        return {"msg": "Video not recording"}


@app.route(
    "/stop_video",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def stop_video():
    """
    Stop the video recording
    """

    subprocess.run(["sudo", "killall", "libcamera-vid"])
    time.sleep(2)

    if not recording_video_active():
        return {"msg": "video recording stopped"}
    else:
        return {"msg": "video recording not stopped"}


@app.route(
    "/schedule_video_recording",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def schedule_video_recording():
    """
    schedule the video recording using crontab of user pi
    see https://pypi.org/project/crontab/
    """

    crontab_event = request.values.get("crontab", "")
    if not crontab_event:
        return {"error": True, "msg": "Video recording NOT configured. Crontab event not found"}

    command_line = [
        "/usr/bin/raspivid",
    ]

    for key in request.values:

        if key in ["prefix", "annotate", "key", "crontab"]:
            continue
        if request.values[key] == "True":
            command_line.extend([f"--{key}"])
        elif request.values[key] != "False":
            command_line.extend([f"--{key}", f"{request.values[key]}"])

    prefix = (request.values["prefix"] + "_") if request.values.get("prefix", "") else ""
    file_path = f"{cfg.VIDEO_ARCHIVE}/{socket.gethostname()}_{prefix}" + "$(/usr/bin/date_crontab_helper).h264"

    command_line.extend(["-o", file_path])

    logging.info(" ".join(command_line))

    comment = f'recording for {round(int(request.values["timeout"]) / 1000)} s'

    cron = CronTab(user="pi")
    job = cron.new(command=" ".join(command_line), comment=comment)
    try:
        job.setall(crontab_event)
    except Exception:
        return {"error": True, "msg": f"Video recording NOT scheduled. '{crontab_event}' is not valid."}

    cron.write()

    return {"error": False, "msg": "Video recording scheduled"}


@app.route(
    "/view_video_recording_schedule",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def view_video_recording_schedule():
    """
    send all video recording schedule
    """
    cron = CronTab(user="pi")
    output = []
    try:
        for job in cron:
            if "/usr/bin/raspivid" in job.command:
                output.append(
                    [str(job.minutes), str(job.hours), str(job.dom), str(job.month), str(job.dow), job.comment]
                )

    except Exception:
        return {"error": True, "msg": f"Error during video recording view."}

    return {"error": False, "msg": output}


@app.route(
    "/delete_video_recording_schedule",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def delete_video_recording_schedule():
    """
    delete all video recording schedule
    """
    cron = CronTab(user="pi")
    try:
        for job in cron:
            if "/usr/bin/raspivid" in job.command:
                cron.remove(job)
        cron.write()
    except Exception:
        return {"error": True, "msg": f"Video recording schedule NOT deleted."}

    return {"error": False, "msg": f"Video recording schedule deleted."}


@app.route(
    "/video_list",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def video_list():
    """
    Return the list of recorded video
    """
    return {
        "video_list": [
            (x.replace(cfg.VIDEO_ARCHIVE + "/", ""), pl.Path(x).stat().st_size)
            for x in glob.glob(cfg.VIDEO_ARCHIVE + "/*.h264")
        ]
    }


@app.route(
    "/pictures_list",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def pictures_list():
    """
    Return the list of recorded pictures
    """
    return {
        "pictures_list": [
            (x.replace(cfg.TIME_LAPSE_ARCHIVE + "/", ""), pl.Path(x).stat().st_size)
            for x in glob.glob(cfg.TIME_LAPSE_ARCHIVE + "/*.jpg")
        ]
    }


@app.route(
    "/get_video/<file_name>",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def get_video(file_name):

    return send_from_directory(cfg.VIDEO_ARCHIVE, file_name, as_attachment=True)


@app.route(
    "/stop_time_lapse",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def stop_time_lapse():
    """
    Stop the time lapse
    """

    subprocess.run(["sudo", "killall", "libcamera-still"])
    time.sleep(5)

    if not time_lapse_active():
        return {"msg": "Time lapse stopped"}
    else:
        return {"msg": "Time lapse not stopped"}


@app.route(
    "/blink",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def blink():
    """
    Blink the power led
    """

    try:
        thread = Blink_thread()
        thread.start()
        return {"msg": "blinking successful"}
    except Exception:
        return {"msg": "blinking not successful"}


@app.route(
    "/sync_time/<date>/<hour>",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def sync_time(date, hour):
    """
    synchronize the date and time
    """

    completed = subprocess.run(["sudo", "timedatectl", "set-ntp", "false"])

    completed = subprocess.run(["sudo", "timedatectl", "set-time", f"{date} {hour}"])  # 2015-11-23 10:11:22
    if completed.returncode:
        return {"error": True, "msg": "Time not synchronised"}
    else:
        return {"error": False, "msg": "Time successfully synchronized"}


@app.route(
    "/take_picture",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def take_picture():
    """
    Start time lapse or take a picture and send it
    """

    logging.info("take picture init")

    if video_streaming_active():
        return {"error": True, "msg": "Time lapse cannot be started because the video streaming is active"}

    if recording_video_active():
        return {"error": True, "msg": "Time lapse cannot be started because the video recording is active"}

    if time_lapse_active():
        return {"error": True, "msg": "The time lapse is already active"}

    # delete previous picture
    try:
        completed = subprocess.run(["sudo", "rm", "-f", pl.Path(cfg.STATIC_DIR) / pl.Path("live.jpg")])
    except Exception:
        pass

    command_line = [
        "libcamera-still",
        # "--timeout", "5",
        "--nopreview",
        "-q",
        "90",
    ]

    for key in request.values:
        logging.info(f"{key}: {request.values[key]}")

    for key in request.values:

        if key in ("timelapse", "timeout", "annotate", "key"):
            continue
        if request.values[key] == "True":
            command_line.extend([f"--{key}"])
        elif request.values[key] != "False":
            command_line.extend([f"--{key}", f"{request.values[key]}"])

    """
    if "annotate" in request.values and request.values["annotate"] == "True":
        command_line.extend(["-a", "4", "-a", f'"{socket.gethostname()} %Y-%m-%d %X"'])
    """

    # check if time lapse required
    if (
        "timeout" in request.values
        and request.values["timeout"] != "0"
        and "timelapse" in request.values
        and request.values["timelapse"] != "0"
    ):
        command_line.extend([f"--timeout", str(int(request.values["timeout"]) * 1000)])
        command_line.extend([f"--timelapse", str(int(request.values["timelapse"]) * 1000)])
        # command_line.extend(["--timestamp"])

        command_line.extend(
            [
                "-o",
                str(pl.Path(cfg.TIME_LAPSE_ARCHIVE) / pl.Path(f"{socket.gethostname()}_%04d").with_suffix(".jpg")),
            ]
        )
        logging.info("command: " + (" ".join(command_line)))
        try:

            subprocess.Popen(command_line)
        except:
            logging.warning("Error running time lapse (wrong command line option)")
            return {"error": 1, "msg": "Error running time lapse (wrong command line option)"}
        return {"error": False, "msg": "Time lapse running"}

    else:
        # take one picture
        command_line.extend(["-o", str(pl.Path(cfg.STATIC_DIR) / pl.Path("live.jpg"))])
        logging.info("command:" + (" ".join(command_line)))
        try:
            completed = subprocess.run(command_line)
        except:
            logging.warning("Error taking picture (wrong command line option)")
            return {"error": 1, "msg": "Error taking picture (wrong command line option)"}

        if not completed.returncode:
            return {"error": False, "msg": "Picture taken successfully"}
        else:
            return {"error": completed.returncode, "msg": "Picture not taken"}


'''
@app.route("/command/<command_to_run>")
def command(command_to_run):
    """
    run a command and send output
    """
    try:
        cmd = base64.b64decode(command_to_run).decode("utf-8")
        process = subprocess.run(cmd.split(" "), stdout=subprocess.PIPE)
        results = {"return_code": process.returncode, "output": process.stdout.decode("utf-8")}
        return str(results)
    except Exception:
        return str({"status": "error"})
'''


@app.route("/get_log")
@security_key_required
def get_log():
    """
    return worker log
    """
    try:
        return {"error": False, "msg": open(cfg.LOG_PATH).read()}
    except Exception:
        return {"error": True}


@app.route("/video_archive_dir")
@security_key_required
def video_archive_dir():
    """
    return the video archive directory
    """
    try:
        return {
            "error": False,
            "msg": str(pl.Path("/") / pl.Path(cfg.STATIC_DIR) / pl.Path(cfg.VIDEO_ARCHIVE_DIR)),
        }
    except Exception:
        return {"error": True}


@app.route("/pictures_archive_dir")
@security_key_required
def pictures_archive_dir():
    """
    return the pictures archive directory
    """
    try:
        return {
            "error": False,
            "msg": str(pl.Path("/") / pl.Path(cfg.STATIC_DIR) / pl.Path(cfg.TIME_LAPSE_ARCHIVE_DIR)),
        }
    except Exception:
        return {"error": True}


@app.route(
    "/delete_video",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def delete_video():
    """
    Delete the recorded video from the list in the video archive
    """

    if not request.values.get("video list", []):
        return {"error": True, "msg": "No video to delete"}

    for video_file_name, _ in json.loads(request.values.get("video list", "[]")):
        (pl.Path(cfg.VIDEO_ARCHIVE) / pl.Path(video_file_name)).unlink(missing_ok=True)
        (pl.Path(cfg.VIDEO_ARCHIVE) / pl.Path(video_file_name).with_suffix(".md5sum")).unlink(missing_ok=True)
    return {"error": False, "msg": "All video deleted"}


@app.route(
    "/get_mac",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def get_mac():
    """
    return MAC ADDR of the wireless interface
    """
    return {"mac_addr": get_hw_addr(cfg.WIFI_INTERFACE)}


@app.route(
    "/reboot",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def reboot():
    """
    shutdown the Raspberry Pi with 1 min delay
    """

    try:
        completed = subprocess.run(["sudo", "shutdown", "--reboot", "+1"])
    except Exception:
        return {"error": 1, "msg": "reboot error"}

    if not completed.returncode:
        return {"error": False, "msg": "reboot requested"}
    else:
        return {"error": completed.returncode, "msg": "reboot error"}


@app.route(
    "/shutdown",
    methods=(
        "GET",
        "POST",
    ),
)
@security_key_required
def shutdown():
    """
    shutdown the Raspberry Pi with 1 min delay
    """

    try:
        completed = subprocess.run(["sudo", "shutdown", "+1"])
    except Exception:
        return {"error": 1, "msg": "shutdown error"}

    if not completed.returncode:
        return {"error": False, "msg": "shutdown requested"}
    else:
        return {"error": completed.returncode, "msg": "shutdown error"}


if __name__ == "__main__":
    logging.info("worker started")
    app.debug = True
    if security_key_sha256:
        app.run(host="0.0.0.0", port=cfg.PORT, ssl_context="adhoc")
    else:
        app.run(host="0.0.0.0", port=cfg.PORT)

    # see https://blog.miguelgrinberg.com/post/running-your-flask-application-over-https for HTTPS
