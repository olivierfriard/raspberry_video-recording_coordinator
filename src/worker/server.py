"""

Video control server


"""

__version__ = "0.0.17"



import sys
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

import server_config as cfg


def is_camera_detected():
    '''
    check if camera is plugged
    '''
    process = subprocess.run(["/opt/vc/bin/vcgencmd", "get_camera"], stdout=subprocess.PIPE)
    output = process.stdout.decode("utf-8").strip()
    return (output == "supported=1 detected=1")


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
    '''
    check if uv4l process is present
    '''
    process = subprocess.run(["ps", "auxwg"], stdout=subprocess.PIPE)
    processes_list = process.stdout.decode("utf-8").split("\n")
    return len([x for x in processes_list if "uv4l" in x]) > 0


def time_lapse_active():
    '''
    check if raspistill process is present
    '''
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
            return output.split('=')[1]
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
    with open("/boot/security_key") as f_in:
        security_key = f_in.read().strip()
    logging.info("Security key loaded")
except Exception:
    logging.critical("Security key not found")
    sys.exit()

app = Flask(__name__, static_url_path='/static')

thread = threading.Thread()

'''
@app.route("/test", methods=("GET", "POST"))
def test():
    print(list(request.args.keys()))
    print(request.values)
    print(request.values['data1'])
    return {"test": "blabla"}

'''


@app.route("/")
def home():
    return f"""<h1>Raspberry <b>{socket.gethostname()}</b></h1>
video control server v. {__version__}<br>
<br>
hostname: {socket.gethostname()}<br>
IP address: {get_ip()}<br>
MAC Addr: {get_hw_addr(cfg.WIFI_INTERFACE)}<br>
date time on server: {datetime_now_iso()}<br>
Timezone: {get_timezone()}<br>
<br>
<a href="/status">server status</a><br>
<a href="/shutdown">shutdown server</a><br>
<br>
<a href="/video_list">list of video on server</a><br>
"""


@app.route("/status", methods=("GET", "POST",))
def status():

    if request.values.get('key', '') != security_key:
        status_code = Response(status=204)  # 204 No Content     The server successfully processed the request, and is not returning any content.
        return status_code

    global thread
    try:
        logging.info(f"thread is alive: {thread.is_alive()}")
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
                      }

        if thread.is_alive():
            video_info = {"video_recording": True,
                          "duration": thread.parameters["duration"],
                          "width": thread.parameters["width"],
                          "height": thread.parameters["height"],
                          "fps": thread.parameters["fps"],
                          "quality": thread.parameters["quality"],
                          "started_at": thread.started_at,
                          "server_version": __version__}
        else:
            video_info = {"video_recording": False}

        return {**server_info, **video_info}

    except Exception:
        return {"status": "Not available"}


class Raspivid_thread(threading.Thread):

    def __init__(self, parameters: dict):
        threading.Thread.__init__(self)
        self.parameters = parameters

        # logging.info("thread args: {} fps: {} resolution: {}x{} quality: {} prefix:{}".format(duration, fps, w, h, quality, prefix))

    def run(self):
        logging.info("start raspivid thread")
        file_name = datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", "_").replace(":", "")

        cmd = ["raspivid",
               "-t", str(int(self.parameters['duration']) * 1000),
               "-w", f"{self.parameters['width']}",
               "-h", f"{self.parameters['height']}",
               "-fps", f"{self.parameters['fps']}",
               "-b", str(int(self.parameters['quality']) * 1000),
               "-o", f"{cfg.VIDEO_ARCHIVE}/{socket.gethostname()}_{self.parameters['prefix']}_{file_name}.h264"
              ]

        logging.info(f"{cmd}")

        self.started_at = datetime.datetime.now().replace(microsecond=0).isoformat()

        subprocess.run(cmd)

        # md5sum
        process = subprocess.run(["md5sum", f"{cfg.VIDEO_ARCHIVE}/{socket.gethostname()}_{self.parameters['prefix']}_{file_name}.h264"],
                                 stdout=subprocess.PIPE)

        print(process.stdout.decode("utf-8"))
        try:
            with open(f"{cfg.VIDEO_ARCHIVE}/{socket.gethostname()}_{self.parameters['prefix']}_{file_name}.md5sum", "w") as f_out:
                f_out.write(process.stdout.decode("utf-8"))
        except Exception:
            logging.warning(f"MD5SUM writing failed for {socket.gethostname()}_{self.parameters['prefix']}_{file_name}.h264")



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

@app.route("/start_video", methods=("GET", "POST",))
def start_video():

    global thread

    if thread.is_alive():
        return {"msg": "Video already recording"}

    logging.info(f"Starting video for {request.values['duration']} s ({request.values['width']}x{request.values['height']})")
    try:
        thread = Raspivid_thread(request.values)
        thread.start()

        logging.info("Video recording started")
        return {"msg": "Video recording"}
    except Exception:
        logging.info("Video recording not started")
        return {"msg": "Video not recording"}


@app.route("/stop_video")
def stop_video():
    """
    Stop the video recording
    """

    subprocess.run(["sudo", "killall", "raspivid"])
    time.sleep(2)

    if not thread.is_alive():
        return {"msg": "video recording stopped"}
    else:
        return {"msg": "video recording not stopped"}


@app.route("/stop_time_lapse")
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
def blink():
    """
    Blink the power led
    """
    if request.values.get('key', '') != security_key:
        status_code = Response(status=204)  # 204 No Content     The server successfully processed the request, and is not returning any content.
        return status_code

    try:
        thread = Blink_thread()
        thread.start()
        return {"msg": "blinking successful"}
    except Exception:
        return {"msg": "blinking not successful"}


@app.route("/sync_time/<date>/<hour>", methods=("GET", "POST",))
def sync_time(date, hour):
    """
    synchronize the date and time
    """
    if request.values.get('key', '') != security_key:
        status_code = Response(status=204)  # 204 No Content     The server successfully processed the request, and is not returning any content.
        return status_code

    completed = subprocess.run(['sudo', 'timedatectl','set-time', f"{date} {hour}"]) # 2015-11-23 10:11:22
    if completed.returncode:
        return {"error": True, "msg": "Time not synchronised"}
    else:
        return {"error": False, "msg": "Time successfully synchronized"}


@app.route("/take_picture", methods=("GET", "POST",))
def take_picture():

    if request.values.get('key', '') != security_key:
        status_code = Response(status=204)  # 204 No Content     The server successfully processed the request, and is not returning any content.
        return status_code

    # delete previous picture
    try:
        completed = subprocess.run(["sudo", "rm", "-f" ,"static/live.jpg"])
    except Exception:
        pass

    command_line = ["raspistill",
                    #"--timeout", "5",
                    "--nopreview",
                    "-q", "90",
                   ]

    for key in request.values:

        if key in ["timelapse", "timeout", "annotate"]:
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
        command_line.extend(["-o", f"static/pictures_archive/{socket.gethostname()}_" + "%04d.jpg"])

        try:
            subprocess.Popen(command_line)
        except:
            logging.warning("Error running time lapse (wrong command line option)")
            return {"error": 1, "msg": "Error running time lapse (wrong command line option)"}
        return {"error": False, "msg": "Time lapse running"}

    else:

        command_line.extend(["-o", "static/live.jpg"])
        print(command_line)
        try:
            completed = subprocess.run(command_line)
        except:
            logging.warning("Error taking picture (wrong command line option)")
            return {"error": 1, "msg": "Error taking picture (wrong command line option)"}
        if not completed.returncode:
            return {"error": False, "msg": "Picture taken successfully"}
        else:
            return {"error": completed.returncode, "msg": "Picture not taken"}




@app.route("/video_list", methods=("GET", "POST",))
def video_list():

    if request.values.get('key', '') != security_key:
        status_code = Response(status=204)  # 204 No Content     The server successfully processed the request, and is not returning any content.
        return status_code

    return {"video_list": [x.replace(cfg.VIDEO_ARCHIVE + "/", "") for x in glob.glob(cfg.VIDEO_ARCHIVE + "/*.h264")]}


@app.route("/get_video/<file_name>", methods=("GET", "POST",))
def get_video(file_name):

    if request.values.get('key', '') != security_key:
        status_code = Response(status=204)  # 204 No Content     The server successfully processed the request, and is not returning any content.
        return status_code

    return send_from_directory(cfg.VIDEO_ARCHIVE, file_name, as_attachment=True)


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
        return str("<pre>" + open(cfg.LOG_PATH).read() + "</pre>")
    except Exception:
        return str({"status": "error"})


@app.route("/delete_all_video", methods=("GET", "POST",))
def delete_all_video():
    """
    Delete all video records in the video archive
    """
    if request.values.get('key', '') != security_key:
        status_code = Response(status=204)  # 204 No Content     The server successfully processed the request, and is not returning any content.
        return status_code

    try:
        subprocess.run(["rm", "-f", f"{cfg.VIDEO_ARCHIVE}/*.h264"])
    except Exception:
        return {"error": True, "msg": "video not deleted"}
    return {"error": False, "msg": "All video deleted"}


@app.route("/get_mac")
def get_mac():
    """
    return MAC ADDR of the wireless interface
    """
    return {"mac_addr": get_hw_addr(cfg.WIFI_INTERFACE)}


@app.route("/reboot", methods=("GET", "POST",))
def reboot():
    """
    shutdown the Raspberry Pi with 1 min delay
    """
    if request.values.get('key', '') != security_key:
        status_code = Response(status=204)  # 204 No Content     The server successfully processed the request, and is not returning any content.
        return status_code

    try:
        completed = subprocess.run(["sudo", "shutdown", "--reboot", "+1"])
    except Exception:
        return {"error": 1, "msg": "reboot error"}

    if not completed.returncode:
        return {"error": False, "msg": "reboot requested"}
    else:
        return {"error": completed.returncode, "msg": "reboot error"}


@app.route("/shutdown", methods=("GET", "POST",))
def shutdown():
    """
    shutdown the Raspberry Pi with 1 min delay
    """
    if request.values.get('key', '') != security_key:
        status_code = Response(status=204)  # 204 No Content     The server successfully processed the request, and is not returning any content.
        return status_code

    try:
        completed = subprocess.run(["sudo", "shutdown", "+1"])
    except Exception:
        return {"error": 1, "msg": "shutdown error"}

    if not completed.returncode:
        return {"error": False, "msg": "shutdown requested"}
    else:
        return {"error": completed.returncode, "msg": "shutdown error"}


if __name__ == '__main__':
    logging.info("server started")
    app.debug = True
    app.run(host = '0.0.0.0', port=cfg.PORT)
