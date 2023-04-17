"""

Video control server


"""

__version__ = "0.0.9"




import os
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
import base64
import pathlib
import shutil

from server_config import *


def get_hw_addr(ifname):
    '''
    return hw addr
    get_hw_addr(WIFI_INTERFACE)
    '''
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        info = fcntl.ioctl(s.fileno(), 0x8927,  struct.pack("256s", bytes(ifname, "utf-8")[:15]))
        return ":".join("%02x" % b for b in info[18:24])
    except:
        return "Not determined"


def get_ip():
    '''
    return IP address. Does not need to be connected to internet
    https://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib
    '''
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
    process = subprocess.run(["iwgetid"], stdout=subprocess.PIPE)
    output = process.stdout.decode("utf-8").strip()
    if output:
        try:
            return output.split('"')[1]
        except:
            return output
    else:
        return "not connected to wifi"


def video_streaming_active():
    '''
    check if uv4l process is present
    '''
    process = subprocess.run(["ps", "auxwg"], stdout=subprocess.PIPE)
    processes_list = process.stdout.decode("utf-8").split("\n")
    return len([x for x in processes_list if "uv4l" in x]) > 0


def get_cpu_temperature():
    '''
    get temperature of the CPU
    '''
    process = subprocess.run(["/opt/vc/bin/vcgencmd", "measure_temp"], stdout=subprocess.PIPE)
    output = process.stdout.decode("utf-8").strip()
    if output:
        try:
            return output.split('=')[1]
        except:
            return "not determined"    
    else:
        return "not determined"
        
def get_free_space():
    '''
    free disk space in Gb
    '''
    stat = shutil.disk_usage('/home/pi')
    return f"{round(stat.free / 1024 / 1024 / 1024, 2)} Gb"



def datetime_now_iso():
    return datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", " ")


from flask import Flask, request, send_from_directory

while True:
    try:
        logging.basicConfig(filename=LOG_PATH,
                            filemode="a",
                            format='%(asctime)s, %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level=logging.DEBUG)
        break
    except FileNotFoundError:
        print("log file path not found. Use server.log")
        LOG_PATH = "server.log"
    

app = Flask(__name__, static_url_path='/static')

thread = threading.Thread()

@app.route("/")
def home():
    return f"""<h1>Raspberry <b>{socket.gethostname()}</b></h1>
video control server v. {__version__}<br>
<br>
hostname: {socket.gethostname()}<br>
IP address: {get_ip()}<br>
MAC Addr: {get_hw_addr(WIFI_INTERFACE)}<br>
date time on server: {datetime_now_iso()}<br>
Timezone: {get_timezone()}<br>
<br>
<a href="/status">server status</a><br>
<a href="/shutdown">shutdown server</a><br>
<br>
<a href="/video_list">list of video on server</a><br>
"""


@app.route("/status")
def status():
    global thread
    try:
        logging.info(f"thread is alive: {thread.is_alive()}")
        server_info = {"status": "OK",
                       "server_datetime": datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", " "),
                       "server_version": __version__,
                       "MAC_addr": get_hw_addr(WIFI_INTERFACE),
                       "hostname": socket.gethostname(),
                       "IP_address": get_ip(),
                       "video_streaming_active": video_streaming_active(),
                       "wifi_essid": get_wifi_ssid(),
                       "CPU temperature": get_cpu_temperature(),
                       "free disk space": get_free_space(),
                      }

        if thread.is_alive():
            video_info = {"video_recording": True,
                          "duration": thread.duration,
                          "started_at": thread.started_at,
                          "w": thread.w,
                          "h": thread.h,
                          "fps": thread.fps,
                          "quality": thread.quality,
                          "server_version": __version__}
        else:
            video_info = {"video_recording": False}

        return str({**server_info, **video_info})

    except Exception:
        raise
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

@app.route("/video_streaming/<action>")
def video_streaming(action):
    """
    start/stop video streaming with uv4l

    see /etc/uv4l/uv4l-raspicam.conf for default configuration

    sudo uv4l -nopreview --auto-video_nr --driver raspicam --encoding mjpeg --width 640 --height 480 --framerate 10 --server-option '--port=9090' 
    --server-option '--max-queued-connections=30' --server-option '--max-streams=25' --server-option '--max-threads=29'

    """
    # kill current streaming 
    subprocess.run(["sudo", "pkill", "uv4l"])
    time.sleep(2)
    if action == "stop":
        return str({"msg": "video streaming stopped"})

    if action == "start":
        w = request.args.get("w", default=DEFAULT_VIDEO_WIDTH, type=int)
        h = request.args.get("h", default=DEFAULT_VIDEO_HEIGHT, type=int)
        process = subprocess.run(["sudo",
                                    "uv4l",
                                    "-nopreview",
                                    "--auto-video_nr",
                                    "--driver", "raspicam",
                                    "--encoding", "mjpeg",
                                    "--width", str(w),
                                    "--height", str(h),
                                    "--framerate", "5",
                                    "--server-option", "--port=9090",
                                    "--server-option", "--max-queued-connections=30",
                                    "--server-option", "--max-streams=25",
                                    "--server-option", "--max-threads=29",
                                    ])
        return str({"msg": "video streaming started"})


@app.route("/set_hostname/<hostname>")
def set_hostname(hostname):
    '''
    set client hostname 
    '''
    subprocess.run(["sudo", "hostnamectl", "set-hostname", hostname])
    return str({"new_hostname": socket.gethostname()})


@app.route("/add_key/<key>")
def add_key(key):
    '''
    add coordinator public key to ~/.ssh/authorized_keys
    '''
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

    logging.info(f"Starting video for {duration} min ({w}x{h})")
    try:
        thread = Raspivid_thread(duration, w, h, fps, quality, prefix)
        thread.start()

        logging.info("Video recording started")
        return str({"status": "Video recording"})
    except Exception:
        logging.info("Video recording not started")
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
    '''
    synchronize the date and time
    '''
    completed = subprocess.run(['sudo', 'timedatectl','set-time', "{date} {hour}".format(date=date, hour=hour)]) # 2015-11-23 10:11:22
    if completed.returncode:
        return str({"result": "time not synchronised",
                    "current date": datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", " ")})
    else:
        return str({"result": "time synchronised",
                    "current date": datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", " ")})


@app.route("/one_picture")
def one_picture():
    os.system("sudo rm -f static/live.jpg")
    w = request.args.get("w", default = DEFAULT_PICTURE_WIDTH, type = int)
    h = request.args.get("h", default = DEFAULT_PICTURE_HEIGHT, type = int)
    os.system((#"raspistill --nopreview "
               "raspistill "
               #"--timeout 4 "
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
    '''
    run a command and send output
    '''
    try:
        cmd = base64.b64decode(command_to_run).decode("utf-8")
        process = subprocess.run(cmd.split(" "), stdout=subprocess.PIPE)
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


@app.route("/get_mac")
def get_mac():
    return str({"mac_addr": get_hw_addr(WIFI_INTERFACE)})


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
    app.run(host = '0.0.0.0', port=PORT)
