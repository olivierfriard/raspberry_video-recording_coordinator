"""

Raspberry Pi worker

to enable the service at boot:
sudo systemctl enable worker
"""

__version__ = "0.0.26"
__version_date__ = "2021-10-06"


from crontab import CronTab

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
#import base64
import pathlib
import shutil
import hashlib
import json

from functools import wraps

import config as cfg


def is_camera_detected():
    """
    check if camera is plugged
    """
    process = subprocess.run(["/opt/vc/bin/vcgencmd", "get_camera"], stdout=subprocess.PIPE)
    output = process.stdout.decode("utf-8").strip()
    return (output == "supported=1 detected=1")


def get_hw_addr(ifname):
    """
    return hw addr
    get_hw_addr(WIFI_INTERFACE)
    """

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        info = fcntl.ioctl(s.fileno(), 0x8927,  struct.pack("256s", bytes(ifname, "utf-8")[:15]))
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
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
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
    return len([x for x in processes_list if "uv4l" in x]) > 0


def recording_video_active():
    """
    check if raspivid process is present
    """
    process = subprocess.run(["ps", "auxwg"], stdout=subprocess.PIPE)
    processes_list = process.stdout.decode("utf-8").split("\n")
    return len([x for x in processes_list if "raspivid" in x]) > 0



def time_lapse_active():
    """
    check if raspistill process is present
    """
    process = subprocess.run(["ps", "auxwg"], stdout=subprocess.PIPE)
    processes_list = process.stdout.decode("utf-8").split("\n")
    return len([x for x in processes_list if "raspistill" in x]) > 0


def get_cpu_temperature():
    """
    get temperature of the CPU
    """
    process = subprocess.run(["/opt/vc/bin/vcgencmd", "measure_temp"], stdout=subprocess.PIPE)
    output = process.stdout.decode("utf-8").strip()
    if output:
        try:
            return output.split('=')[1].replace("'", "°")
        except:
            return "not determined"
    else:
        return "not determined"


def get_free_space():
    """
    free disk space in Gb
    """
    stat = shutil.disk_usage('/home/pi')
    return f"{round(stat.free / 1024 / 1024 / 1024, 2)} Gb"


def get_uptime():
    process = subprocess.run(["uptime", "-p"], stdout=subprocess.PIPE)
    output = process.stdout.decode("utf-8").strip()
    return output


def datetime_now_iso():
    return datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", " ")



class Raspivid_thread(threading.Thread):
    """
    Class for recording video using a thread
    """

    def __init__(self, parameters: dict):
        threading.Thread.__init__(self)
        self.parameters = parameters

    def run(self):
        logging.info("start raspivid thread")

        command_line = ["/usr/bin/raspivid", ]

        for key in self.parameters:

            if key in ["prefix", "annotate", "key"]:
                continue
            if self.parameters[key] == 'True':
                command_line.extend([f"--{key}"])
            elif self.parameters[key] != 'False':
                command_line.extend([f"--{key}", f"{self.parameters[key]}"])

        file_name = datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", "_").replace(":", "")
        prefix = (self.parameters["prefix"] + "_" ) if self.parameters.get("prefix", "") else ""

        file_path = f"{cfg.VIDEO_ARCHIVE}/{socket.gethostname()}_{prefix}{file_name}.h264"

        command_line.extend(["-o", file_path])

        logging.info(" ".join(command_line))

        self.started_at = datetime.datetime.now().replace(microsecond=0).isoformat()

        subprocess.run(command_line)

        # md5sum
        process = subprocess.run(["md5sum", file_path],
                                 stdout=subprocess.PIPE)

        try:
            with open(f"{cfg.VIDEO_ARCHIVE}/{socket.gethostname()}_{self.parameters['prefix']}_{file_name}.md5sum", "w") as f_out:
                f_out.write(process.stdout.decode("utf-8"))
        except Exception:
            logging.warning(f"MD5SUM writing failed for {file_path}")



class Blink_thread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        logging.info("start  blinking")

        subprocess.run(["bash", "blink_sudo.bash"])

        '''
        # Set the PWR LED to GPIO mode (set 'off' by default).
        os.system("echo gpio | sudo tee /sys/class/leds/led1/trigger")

        # (Optional) Turn on (1) or off (0) the PWR LED.

        for n in range(30):
            os.system("echo 0 | sudo tee /sys/class/leds/led1/brightness")
            time.sleep(500)
            os.system("echo 1 | sudo tee /sys/class/leds/led1/brightness")
            time.sleep(500)

        # Revert the PWR LED back to 'under-voltage detect' mode.
        os.system("echo input | sudo tee /sys/class/leds/led1/trigger")
        '''



from flask import Flask, request, send_from_directory, Response

while True:
    try:
        logging.basicConfig(filename=cfg.LOG_PATH,
                            filemode="a",
                            format='%(asctime)s, %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level=logging.DEBUG)
        break
    except FileNotFoundError:
        print("log file path not found. Use server.log")
        LOG_PATH = "server.log"

# load security key
try:
    with open("/boot/worker_security_key") as f_in:
        security_key_sha256 = f_in.read().strip()
    logging.info("Security key loaded")
except Exception:
    logging.info("Security key file not found")
    security_key_sha256 = ""


app = Flask(__name__, static_url_path='/static')

thread = threading.Thread()


def security_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if (security_key_sha256):

            if not request.values.get("key", ""):
                status_code = Response(status=204)
                return status_code

            if hashlib.sha256(request.values.get("key", "").encode("utf-8")).hexdigest() != security_key_sha256:
                status_code = Response(status=204)  # 204 No Content     The server successfully processed the request, and is not returning any content.
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



@app.route("/status", methods=("GET", "POST",))
@security_key_required
def status():

    #global thread
    try:
        #logging.info(f"thread is alive: {thread.is_alive()}")

        server_info = {"status": "OK",
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


@app.route("/video_streaming/<action>", methods=("GET", "POST",))
def video_streaming(action):
    """
    start/stop video streaming with uv4l

    see /etc/uv4l/uv4l-raspicam.conf for default configuration

    sudo uv4l -nopreview --auto-video_nr --driver raspicam --encoding mjpeg --width 640 --height 480 --framerate 10 --server-option '--port=9090'
    --server-option '--max-queued-connections=30' --server-option '--max-streams=25' --server-option '--max-threads=29'

    """
    # kill current streaming
    try:
        subprocess.run(["sudo", "pkill", "uv4l"])
        time.sleep(2)
    except Exception:
        return {"msg": "Problem trying to stop the video streaming"}

    if action == "stop":
        return {"msg": "video streaming stopped"}

    if action == "start":

        try:
            width = request.values['width']
        except Exception:
            width = cfg.DEFAULT_PICTURE_WIDTH

        try:
            height = request.values['height']
        except Exception:
            height = cfg.DEFAULT_PICTURE_HEIGHT

        try:
            subprocess.run(["sudo",
                                  "uv4l",
                                  "-nopreview",
                                  "--auto-video_nr",
                                  "--driver", "raspicam",
                                  "--encoding", "mjpeg",
                                  "--width", str(width),
                                  "--height", str(height),
                                  "--framerate", "5",
                                  "--server-option", "--port=9090",
                                  "--server-option", "--max-queued-connections=30",
                                  "--server-option", "--max-streams=25",
                                  "--server-option", "--max-threads=29",
                                  ])
            return {"msg": "video streaming started"}
        except Exception:
            return {"msg": "video streaming not started"}



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


@app.route("/schedule_time_lapse", methods=("GET", "POST",))
@security_key_required
def schedule_time_lapse():
    """
    schedule the time lapse using crontab of user pi
    see https://pypi.org/project/crontab/
    """

    crontab_event = request.values.get("crontab", "")
    if not crontab_event:
        return {"error": True, "msg": "Time lapse NOT configured. Crontab event not found"}


    command_line = ["/usr/bin/raspistill",
                    "-q", "90",]

    for key in request.values:

        if key in ["timelapse", "timeout", "prefix", "annotate", "key", "crontab"]:
            continue
        if request.values[key] == 'True':
            command_line.extend([f"--{key}"])
        elif request.values[key] != 'False':
            command_line.extend([f"--{key}", f"{request.values[key]}"])

    # use Epoch time for file name
    command_line.extend(["--timestamp"])

    if ("timeout" in request.values and request.values["timeout"] != '0'
        and "timelapse" in request.values and request.values["timelapse"] != '0'):
        command_line.extend([f"--timeout", str(int(request.values["timeout"]) * 1000)])
        command_line.extend([f"--timelapse", str(int(request.values["timelapse"]) * 1000)])
        comment = f'time-lapse for {request.values["timeout"]} s (every {request.values["timelapse"]} s)'

    command_line.extend(["-o", str(pathlib.Path(cfg.TIME_LAPSE_ARCHIVE) / pathlib.Path(f"{socket.gethostname()}_%d").with_suffix(".jpg"))])

    '''
    prefix = (request.values["prefix"] + "_" ) if request.values.get("prefix", "") else ""
    file_path = f"{cfg.VIDEO_ARCHIVE}/{socket.gethostname()}_{prefix}" + "$(/usr/bin/date_crontab_helper).h264"
    command_line.extend(["-o", file_path])
    '''

    logging.info(" ".join(command_line))

    cron = CronTab(user="pi")
    job = cron.new(command=" ".join(command_line),
                   comment=comment)
    try:
        job.setall(crontab_event)
    except Exception:
        return {"error": True, "msg": f"Time lapse NOT scheduled. '{crontab_event}' is not valid."}

    cron.write()

    return {"error": False, "msg": "Time lapse  scheduled"}


@app.route("/view_time_lapse_schedule", methods=("GET", "POST",))
@security_key_required
def view_time_lapse_schedule():
    """
    send all time lapse crontab schedule
    """
    cron = CronTab(user="pi")
    output = []
    try:
        for job in cron:
            if "/usr/bin/raspistill" in job.command:
                output.append([str(job.minutes), str(job.hours), str(job.dom), str(job.month), str(job.dow), job.comment])

    except Exception:
        return {"error": True, "msg": f"Error during time lapse schedule view."}

    return {"error": False, "msg": output}


@app.route("/delete_time_lapse_schedule", methods=("GET", "POST",))
@security_key_required
def delete_time_lapse_schedule():
    """
    delete all time lapse schedule
    """
    cron = CronTab(user="pi")
    try:
        for job in cron:
            if "/usr/bin/raspistill" in job.command:
                cron.remove(job)
        cron.write()
    except Exception:
        return {"error": True, "msg": f"Time lapse schedule NOT deleted."}

    return {"error": False, "msg": f"Time lapse schedule deleted."}



@app.route("/start_video", methods=("GET", "POST",))
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


    logging.info(f"Starting video recording for {int(request.values['timeout']) / 1000} s ({request.values['width']}x{request.values['height']})")
    try:
        thread = Raspivid_thread(request.values)
        thread.start()

        logging.info("Video recording started")
        return {"msg": "Video recording"}
    except Exception:
        logging.info("Video recording not started")
        return {"msg": "Video not recording"}


@app.route("/stop_video", methods=("GET", "POST",))
@security_key_required
def stop_video():
    """
    Stop the video recording
    """

    subprocess.run(["sudo", "killall", "raspivid"])
    time.sleep(2)

    if not recording_video_active():
        return {"msg": "video recording stopped"}
    else:
        return {"msg": "video recording not stopped"}


@app.route("/schedule_video_recording", methods=("GET", "POST",))
@security_key_required
def schedule_video_recording():
    """
    schedule the video recording using crontab of user pi
    see https://pypi.org/project/crontab/
    """

    crontab_event = request.values.get("crontab", "")
    if not crontab_event:
        return {"error": True, "msg": "Video recording NOT configured. Crontab event not found"}


    command_line = ["/usr/bin/raspivid", ]

    for key in request.values:

        if key in ["prefix", "annotate", "key", "crontab"]:
            continue
        if request.values[key] == 'True':
            command_line.extend([f"--{key}"])
        elif request.values[key] != 'False':
            command_line.extend([f"--{key}", f"{request.values[key]}"])

    prefix = (request.values["prefix"] + "_" ) if request.values.get("prefix", "") else ""
    file_path = f"{cfg.VIDEO_ARCHIVE}/{socket.gethostname()}_{prefix}" + "$(/usr/bin/date_crontab_helper).h264"

    command_line.extend(["-o", file_path])

    logging.info(" ".join(command_line))

    comment = f'recording for {round(int(request.values["timeout"]) / 1000)} s'

    cron = CronTab(user="pi")
    job = cron.new(command=" ".join(command_line),
                   comment=comment)
    try:
        job.setall(crontab_event)
    except Exception:
        return {"error": True, "msg": f"Video recording NOT scheduled. '{crontab_event}' is not valid."}

    cron.write()

    return {"error": False, "msg": "Video recording scheduled"}


@app.route("/view_video_recording_schedule", methods=("GET", "POST",))
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
                output.append([str(job.minutes), str(job.hours), str(job.dom), str(job.month), str(job.dow), job.comment])

    except Exception:
        return {"error": True, "msg": f"Error during video recording view."}

    return {"error": False, "msg": output}



@app.route("/delete_video_recording_schedule", methods=("GET", "POST",))
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


@app.route("/video_list", methods=("GET", "POST",))
@security_key_required
def video_list():
    """
    Return the list of recorded video
    """
    return {"video_list": [(x.replace(cfg.VIDEO_ARCHIVE + "/", ""), pathlib.Path(x).stat().st_size)
                           for x in glob.glob(cfg.VIDEO_ARCHIVE + "/*.h264")]}


@app.route("/get_video/<file_name>", methods=("GET", "POST",))
@security_key_required
def get_video(file_name):

    return send_from_directory(cfg.VIDEO_ARCHIVE, file_name, as_attachment=True)




@app.route("/stop_time_lapse", methods=("GET", "POST",))
@security_key_required
def stop_time_lapse():
    """
    Stop the time lapse
    """

    subprocess.run(["sudo", "killall", "raspistill"])
    time.sleep(2)

    if not time_lapse_active():
        return {"msg": "Time lapse stopped"}
    else:
        return {"msg": "Time lapse not stopped"}



@app.route("/blink", methods=("GET", "POST",))
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



@app.route("/sync_time/<date>/<hour>", methods=("GET", "POST",))
@security_key_required
def sync_time(date, hour):
    """
    synchronize the date and time
    """

    completed = subprocess.run(['sudo', 'timedatectl','set-time', f"{date} {hour}"]) # 2015-11-23 10:11:22
    if completed.returncode:
        return {"error": True, "msg": "Time not synchronised"}
    else:
        return {"error": False, "msg": "Time successfully synchronized"}


@app.route("/take_picture", methods=("GET", "POST",))
@security_key_required
def take_picture():
    """
    Start time lapse or take a picture and send it
    """

    if video_streaming_active():
        return {"error": True,
                "msg": "Time lapse cannot be started because the video streaming is active"}

    if recording_video_active():
        return {"error": True,
                "msg": "Time lapse cannot be started because the video recording is active"}

    if time_lapse_active():
        return {"error": True,
                "msg": "The time lapse is already active"}


    # delete previous picture
    try:
        completed = subprocess.run(["sudo", "rm", "-f" ,"static/live.jpg"])
    except Exception:
        pass

    command_line = ["/usr/bin/raspistill",
                    #"--timeout", "5",
                    "--nopreview",
                    "-q", "90",
                   ]

    for key in request.values:

        if key in ["timelapse", "timeout", "annotate", "key"]:
            continue
        if request.values[key] == 'True':
            command_line.extend([f"--{key}"])
        elif request.values[key] != 'False':
            command_line.extend([f"--{key}", f"{request.values[key]}"])

    if "annotate" in request.values and request.values["annotate"] == 'True':
        command_line.extend(["-a", "4", "-a", f'"{socket.gethostname()} %Y-%m-%d %X"'])

    # check time lapse
    if ("timeout" in request.values and request.values["timeout"] != '0'
        and "timelapse" in request.values and request.values["timelapse"] != '0'):
        command_line.extend([f"--timeout", str(int(request.values["timeout"]) * 1000)])
        command_line.extend([f"--timelapse", str(int(request.values["timelapse"]) * 1000)])
        command_line.extend(["--timestamp"])

        command_line.extend(["-o", pathlib.Path(cfg.TIME_LAPSE_ARCHIVE) / pathlib.Path(f"{socket.gethostname()}_%d").with_suffix(".jpg")])

        # command_line.extend(["-o", f"static/pictures_archive/{socket.gethostname()}_" + "%04d.jpg"])

        try:
            subprocess.Popen(command_line)
        except:
            logging.warning("Error running time lapse (wrong command line option)")
            return {"error": 1, "msg": "Error running time lapse (wrong command line option)"}
        return {"error": False, "msg": "Time lapse running"}

    else:

        command_line.extend(["-o", "static/live.jpg"])
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




@app.route("/delete_video", methods=("GET", "POST",))
@security_key_required
def delete_video():
    """
    Delete the recorded video from the list in the video archive
    """

    if not request.values.get("video list", []):
        return {"error": True, "msg": "No video to delete"}

    for video_file_name, _ in json.loads(request.values.get("video list", "[]")):
        try:
            subprocess.run(["rm", "-f", f"{cfg.VIDEO_ARCHIVE}/{video_file_name}"])
        except Exception:
            return {"error": True, "msg": "video not deleted"}

    return {"error": False, "msg": "All video deleted"}


@app.route("/get_mac", methods=("GET", "POST",))
@security_key_required
def get_mac():
    """
    return MAC ADDR of the wireless interface
    """
    return {"mac_addr": get_hw_addr(cfg.WIFI_INTERFACE)}


@app.route("/reboot", methods=("GET", "POST",))
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


@app.route("/shutdown", methods=("GET", "POST",))
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


if __name__ == '__main__':
    logging.info("worker started")
    app.debug = True
    app.run(host = '0.0.0.0', port=cfg.PORT, ssl_context='adhoc')

    # see https://blog.miguelgrinberg.com/post/running-your-flask-application-over-https for HTTPS