"""
Raspberry video recording master (TCP/IP)


TODO:
CLIENT_PROJECT_DIRECTORY: ask to raspberry
"""

from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow,
                             QVBoxLayout, QHBoxLayout, QTabWidget,
                             QTextEdit, QPushButton, QLabel, QComboBox,
                             QSpinBox, QSpacerItem, QSizePolicy,
                             QLineEdit, QMessageBox, QFileDialog,
                             QInputDialog, QStackedWidget,
                             QListWidget, QListWidgetItem,
                             QAction, QMenu)
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import QProcess, QTimer, Qt, QUrl
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtMultimediaWidgets import QVideoWidget

import os
import time
import sys
import pathlib
import datetime
import subprocess
from functools import partial
import requests
import shutil
import threading
import logging
import socket
import fcntl
import struct
import base64
from PIL.ImageQt import ImageQt
from multiprocessing.pool import ThreadPool
import json
import pprint
import shutil

import config_coordinator_local as cfg

__version__ = "5"
__version_date__ = "2021-03-17"


logging.basicConfig(filename="coordinator.log",
                    filemode="a",
                    format='%(asctime)s, %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.DEBUG)


def date_iso():
    """
    return current date in ISO 8601 format
    """
    return datetime.datetime.now().isoformat().split(".")[0].replace("T", " ")


def json_formater(s):
    return s.replace("{", "\n").replace(",", "\n").replace("}", "\n")


def ping(host):
    """
    Returns True if host (str) responds to a ping request.
    """

    command = ["ping", "-W", "1", "-c", "1", host]

    return subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


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


def get_wlan_ip_address():
    '''
    get IP of wireless connection
    '''

    for ifname in os.listdir('/sys/class/net/'):  # https://stackoverflow.com/questions/3837069/how-to-get-network-interface-card-names-in-python/58191277
        if ifname.startswith("wl"):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # https://stackoverflow.com/questions/3837069/how-to-get-network-interface-card-names-in-python/58191277
            try:
                return socket.inet_ntoa(fcntl.ioctl(
                                        s.fileno(),
                                        0x8915,  # SIOCGIFADDR
                                        struct.pack('256s', ifname.encode('utf-8')[:15])
                                        )[20:24])
            except OSError:
                return "not connected"
    return ""


def get_wifi_ssid():
    '''
    get the SSID of the connected wifi network
    '''
    process = subprocess.run(["iwgetid"], stdout=subprocess.PIPE)
    output = process.stdout.decode("utf-8").strip()
    if output:
        try:
            return output.split('"')[1]
        except:
            return output
    else:
        return "not connected to wifi"




class Video_recording_control(QMainWindow):

    RASPBERRY_IP = {}
    raspberry_msg = {}
    (status_list, text_list, download_button, record_button,
    image_label, stack_list, combo_list, media_list, combo_list, video_streaming_btn) = {}, {}, {}, {}, {}, {}, {}, {}, {}, {}
    (start_time, duration, interval, video_mode,
     video_quality, fps, prefix, resolution, download_process) = {}, {}, {}, {}, {}, {}, {}, {}, {}

    raspberry_info = {}

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Raspberry - Video recording")
        self.statusBar().showMessage(f"v. {__version__} - {__version_date__}    WIFI SSID: {get_wifi_ssid()}    IP address: {get_wlan_ip_address()}")

        self.setGeometry(0, 0, 1300, 768)

        self.current_raspberry_id = ""
        self.raspberry_status = {}
        self.raspberry_output = {}
        #self.status_all(output=True)

        self.create_interface()

        self.create_menu()

        self.show()
        app.processEvents()

        # self.scan_network(output=True)

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(lambda: self.status_all(output=False))
        self.status_timer.setInterval(cfg.REFRESH_INTERVAL * 1000)
        self.status_timer.start()


    def create_menu(self):
        self.exitAct = QAction("E&xit", self, shortcut="Ctrl+Q", triggered=self.close)
        self.ip_list = QAction("Show raspberries IP", self, triggered=self.show_ip_list)

        self.fileMenu = QMenu("&File", self)
        self.fileMenu.addAction(self.exitAct)
        self.menuBar().addMenu(self.fileMenu)

        self.tools_menu = QMenu("&Tools", self)
        self.tools_menu.addAction(self.ip_list)
        self.menuBar().addMenu(self.tools_menu)


    def create_interface(self):
        layout = QVBoxLayout()

        layout.addLayout(self.create_all_buttons())

        #layout.addLayout(self.create_navigation_buttons())

        '''
        self.tw = self.create_raspberry_tabs()
        layout.addWidget(self.tw)
        '''

        self.tw = QTabWidget()

        self.q1 = self.create_raspberry_commands()

        self.tw.addTab(self.q1, "Raspberry Pi commands")

        self.tw.addTab(QWidget(), "Dashboard")

        layout.addWidget(self.tw)


        main_widget = QWidget(self)
        main_widget.setLayout(layout)

        self.setCentralWidget(main_widget)


    def create_all_buttons(self):
        """
        Create buttons to send commands to all Raspberries Pi
        """
        # buttons for all raspberries
        hlayout_all_buttons = QHBoxLayout()
        hlayout_all_buttons.addWidget(QPushButton("Status from all", clicked=partial(self.status_all, output=True)))
        hlayout_all_buttons.addWidget(QPushButton("Sync time all", clicked=self.time_synchro_all))
        hlayout_all_buttons.addWidget(QPushButton("video list from all", clicked=self.video_list_from_all))
        hlayout_all_buttons.addWidget(QPushButton("Download video from all", clicked=self.download_all_video_from_all))
        #hlayout_all_buttons.addWidget(QPushButton("Update all server", clicked=self.update_all))
        hlayout_all_buttons.addWidget(QPushButton("Send command to all", clicked=self.send_command_all))
        hlayout_all_buttons.addWidget(QPushButton("Clear all output", clicked=self.clear_all_output))
        hlayout_all_buttons.addWidget(QPushButton("Reboot all", clicked=self.reboot_all))
        hlayout_all_buttons.addWidget(QPushButton("Shutdown all", clicked=self.shutdown_all))
        hlayout_all_buttons.addWidget(QPushButton("Scan network", clicked=partial(self.scan_network, output=True)))

        return hlayout_all_buttons


    def create_navigation_buttons(self):
        """
        Create buttons for selection of Raspberry Pi
        """
        # add navigation buttons
        hlayout_navigation_buttons = QHBoxLayout()
        hlayout_navigation_buttons.addWidget(QPushButton("<-", clicked=self.go_left))
        hlayout_navigation_buttons.addWidget(QPushButton("->", clicked=self.go_right))
        self.message_box = QLabel('...')
        hlayout_navigation_buttons.addWidget(self.message_box)
        hlayout_navigation_buttons.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        return hlayout_navigation_buttons


    def rasp_list_clicked(self, item):
        """
        update the current Raspberry Pi
        """

        self.current_raspberry_id = item.text()
        self.lb_raspberry_id.setText(self.current_raspberry_id)

        self.text_list.setText(self.raspberry_output[self.current_raspberry_id])



    def create_raspberry_commands(self):

        hlayout1 = QHBoxLayout()
        q1 = QWidget()

        # self.download_process[rb] = QProcess()

        l = QHBoxLayout()

        # list of Raspberry Pi
        rasp_list_layout = QVBoxLayout()
        rasp_list_layout.addLayout(self.create_navigation_buttons())
        self.rasp_list = QListWidget()
        self.rasp_list.itemClicked.connect(self.rasp_list_clicked)
        rasp_list_layout.addWidget(self.rasp_list)


        output_layout = QVBoxLayout()

        combo = QComboBox(self)
        combo.addItem("view command output")
        combo.addItem("view picture")
        combo.addItem("video streaming")
        combo.currentIndexChanged[int].connect(self.combo_index_changed)
        self.combo_list = combo
        output_layout.addWidget(self.combo_list)

        self.stack_list = QStackedWidget()

        self.stack1 = QWidget()
        # command output
        stack1_layout = QHBoxLayout()
        self.text_list = QTextEdit()
        self.text_list.setLineWrapMode(QTextEdit.NoWrap)
        self.text_list.setFontFamily("Monospace")
        stack1_layout.addWidget(self.text_list)
        self.stack1.setLayout(stack1_layout)

        # image viewer
        self.stack2 = QWidget()
        stack2_layout = QHBoxLayout()
        stack2_layout.setContentsMargins(0, 0, 0, 0)
        self.image_label = QLabel()
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("QLabel {background-color: black;}")

        stack2_layout.addWidget(self.image_label)
        self.stack2.setLayout(stack2_layout)

        self.stack_list.addWidget(self.stack1)
        self.stack_list.addWidget(self.stack2)

        # video streaming viewer
        self.stack3 = QWidget()
        stack3_layout = QHBoxLayout()
        stack3_layout.setContentsMargins(0, 0, 0, 0)

        mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_list = mediaPlayer
        videoWidget = QVideoWidget()

        # Create a widget for window contents
        wid = QWidget(self)
        layout_video = QHBoxLayout()
        layout_video.setContentsMargins(0, 0, 0, 0)
        layout_video.addWidget(videoWidget)

        # Set widget to contain window contents
        wid.setLayout(layout_video)

        self.media_list.setVideoOutput(videoWidget)
        stack3_layout.addWidget(wid)

        self.stack3.setLayout(stack3_layout)

        self.stack_list.addWidget(self.stack1)
        self.stack_list.addWidget(self.stack2)
        self.stack_list.addWidget(self.stack3)

        output_layout.addWidget(self.stack_list)
        self.stack_list.setCurrentIndex(0)


        commands_layout = QVBoxLayout()
        self.lb_raspberry_id = QLabel(" ")
        commands_layout.addWidget(self.lb_raspberry_id)

        buttons = QHBoxLayout()

        self.status_list = QPushButton("Status", clicked=partial(self.status_one, output=True))
        buttons.addWidget(self.status_list)

        buttons.addWidget(QPushButton("Sync time", clicked=self.time_synchro))
        buttons.addWidget(QPushButton("Get log", clicked=self.get_log))
        buttons.addWidget(QPushButton("Clear output", clicked=self.clear_output))
        buttons.addWidget(QPushButton("Blink", clicked=self.blink))
        buttons.addWidget(QPushButton("Send key", clicked=self.send_public_key))

        commands_layout.addLayout(buttons)

        commands_layout.addWidget(QLabel("<b>Picture</b>"))
        l2 = QHBoxLayout()
        l2.addWidget(QLabel("Resolution"))
        self.resolution = QComboBox()
        for resol in cfg.PICTURE_RESOLUTIONS:
            self.resolution.addItem(resol)
        self.resolution.setCurrentIndex(cfg.DEFAULT_PICTURE_RESOLUTION)
        l2.addWidget(self.resolution)
        commands_layout.addLayout(l2)
        commands_layout.addWidget(QPushButton("Take one picture", clicked=self.one_picture))


        commands_layout.addWidget(QLabel("<b>Video</b>"))
        l2 = QHBoxLayout()
        self.video_streaming_btn = QPushButton("Start video streaming", clicked=partial(self.video_streaming_clicked, "start"))
        l2.addWidget(self.video_streaming_btn)
        l2.addWidget(QPushButton("Stop video streaming", clicked=partial(self.video_streaming_clicked, "stop")))

        self.record_button = QPushButton("Start video recording", clicked=self.start_video_recording)
        l2.addWidget(self.record_button)
        l2.addWidget(QPushButton("Stop video recording", clicked=self.stop_video_recording))
        commands_layout.addLayout(l2)

        l2 = QHBoxLayout()
        l2.addWidget(QLabel("Video mode"))
        self.video_mode = QComboBox()
        for resol in cfg.VIDEO_MODES:
            self.video_mode.addItem(resol)
        self.video_mode.setCurrentIndex(cfg.DEFAULT_VIDEO_MODE)
        l2.addWidget(self.video_mode)

        l2.addWidget(QLabel("Video quality Mbp/s"))
        self.video_quality = QSpinBox()
        self.video_quality.setMinimum(1)
        self.video_quality.setMaximum(10)
        self.video_quality.setValue(cfg.DEFAULT_VIDEO_QUALITY)
        l2.addWidget(self.video_quality)

        l2.addWidget(QLabel("FPS"))
        self.fps = QSpinBox()
        self.fps.setMinimum(1)
        self.fps.setMaximum(30)
        self.fps.setValue(cfg.DEFAULT_FPS)
        l2.addWidget(self.fps)

        horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        l2.addItem(horizontalSpacer)

        commands_layout.addLayout(l2)

        l2 = QHBoxLayout()
        l2.addWidget(QLabel("Duration (s)"))
        self.duration = QSpinBox()
        self.duration.setMinimum(10)
        self.duration.setMaximum(86400)
        self.duration.setValue(cfg.DEFAULT_VIDEO_DURATION)
        l2.addWidget(self.duration)

        commands_layout.addLayout(l2)

        l2.addWidget(QLabel("Video file name prefix"))
        self.prefix = QLineEdit("")
        l2.addWidget(self.prefix)

        commands_layout.addLayout(l2)

        # get video / video list
        l2 = QHBoxLayout()
        q = QPushButton("Get list of videos", clicked=self.get_videos_list)
        l2.addWidget(q)

        self.download_button = QPushButton("Download videos", clicked=self.download_videos_clicked)
        l2.addWidget(self.download_button)

        l2.addWidget(QPushButton("Delete all video", clicked=self.delete_all_video))
        commands_layout.addLayout(l2)

        commands_layout.addWidget(QLabel("<b>System commands</b>"))

        l2 = QHBoxLayout()
        l2.addWidget(QPushButton("Send command", clicked=self.send_command))
        l2.addWidget(QPushButton("Reboot", clicked=self.reboot))
        l2.addWidget(QPushButton("Shutdown", clicked=self.shutdown_clicked))

        commands_layout.addLayout(l2)

        verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        commands_layout.addItem(verticalSpacer)

        l.addLayout(rasp_list_layout)
        l.addLayout(commands_layout)
        l.addLayout(output_layout)

        hlayout1.addLayout(l)

        q1.setLayout(hlayout1)

        return q1


    def time_synchro_clicked(self):
        """
        Synchronize time on the current raspberry
        """
        self.rb_msg(self.current_raspberry_id, self.time_synchro(self.current_raspberry_id))


    def shutdown_clicked(self):
        """
        Shutdown the current raspberry
        """
        if self.current_raspberry_id in self.RASPBERRY_IP and self.raspberry_status[self.current_raspberry_id]:
            text, ok = QInputDialog.getText(self, f"Shutdown Rasberry Pi {self.current_raspberry_id}", "Please confirm writing 'yes'")
            if not ok or text != "yes":
                return

        self.shutdown(self.current_raspberry_id)


    def video_streaming_clicked(self, action):
        """
        Start video streaming on the current raspberry
        """
        self.video_streaming(self.current_raspberry_id, action)

    def download_videos_clicked(self):
        """
        Download videos from current Raspberry Pi
        """
        self.download_videos(self.current_raspberry_id, "")

    def get_videos_list(self):
        """
        Download list of videos from current Raspberry Pi
        """

        self.video_list(self.current_raspberry_id)


    def populate_rasp_list(self):
        """
        Populate the list widget with the Raspberry clients found
        """
        self.raspberry_info = {}
        self.rasp_list.clear()
        for raspberry_id in sorted(self.RASPBERRY_IP.keys()):
            self.rasp_list.addItem(QListWidgetItem(raspberry_id))
            self.raspberry_info[raspberry_id] = {"picture resolution": cfg.PICTURE_RESOLUTIONS[cfg.DEFAULT_PICTURE_RESOLUTION],
                                            "video mode": cfg.VIDEO_MODES[cfg.DEFAULT_VIDEO_MODE],
                                            "video quality": cfg.DEFAULT_VIDEO_QUALITY,
                                            "FPS": cfg.DEFAULT_FPS,
                                            "video duration": cfg.DEFAULT_VIDEO_DURATION,
                                            }


    def connect(self, ip_addr):
        '''
        try to connect to http://{ip_addr}/status
        '''
        try:
            r = requests.get(f"http://{ip_addr}:{cfg.SERVER_PORT}/status", timeout=cfg.TIME_OUT)
            if r.status_code == 200:
                try:
                    logging.info(f"{ip_addr}: server available")
                    r_dict = eval(r.text)

                    # check hostname
                    remote_hostname = r_dict.get('hostname', '')

                    self.RASPBERRY_IP[remote_hostname] = ip_addr

                    # set raspberry time date
                    date, hour = date_iso().split(" ")
                    try:
                        r3 = requests.get(f"http://{ip_addr}:{cfg.SERVER_PORT}/sync_time/{date}/{hour}")
                        if r3.status_code == 200:
                            logging.info(f"{ip_addr}: sync time OK {date} {hour}")
                        else:
                            logging.info(f"{ip_addr}: sync time failed")
                    except Exception:
                        logging.info(f"{ip_addr}: sync time failed")

                except:
                    logging.debug(f"{ip_addr}: not available")
        except:
            logging.debug(f"{ip_addr}: not available")


    def scan_raspberries(self, ip_addr, interval):
        '''
        scan network {ip_range} for raspberry clients
        '''
        #current_ip = get_wlan_ip_address()

        # current_ip = get_ip()

        # current_ip = '130.192.200.127'

        # logging.info(f"current WLAN IP address: {current_ip}")


        ip_mask = ".".join(ip_addr.split(".")[0:3])
        ip_list = [f"{ip_mask}.{x}" for x in range(interval[0], interval[1] + 1)]
        self.RASPBERRY_IP = {}
        threads = []
        logging.info("testing subnet")
        for ip in ip_list:
            threads.append(threading.Thread(target=self.connect, args=(ip,)))
            threads[-1].start()
        for x in threads:
            x.join()
        logging.info(f"testing subnet done: found {len(self.RASPBERRY_IP)} clients: {self.RASPBERRY_IP}")

        return 0


    def scan_network(self, output):
        """
        scan all network defined in IP_RANGES
        """
        self.message_box.setText("Scanning network...")
        app.processEvents()

        for ip_config in cfg.IP_RANGES:

            print(ip_config)

            ip_addr, interval = ip_config[0], ip_config[1]
            self.scan_raspberries(ip_addr, interval)

            self.message_box.setText(f"Scanning done: {len(self.RASPBERRY_IP)} client(s) found on {ip_config[0]}")



        print("self.RASPBERRY_IP", self.RASPBERRY_IP)

        # self.create_raspberry_tabs()
        self.populate_rasp_list()

        self.status_all(output=output)



    def show_ip_list(self):
        print(" ".join([f"pi@{self.RASPBERRY_IP[x]}" for x in self.RASPBERRY_IP]))


    def video_streaming(self, rb, action):
        """
        start/stop video streaming on client and show output
        see /etc/uv4l/uv4l-raspicam.conf for default configuration
        """
        if rb in self.RASPBERRY_IP and self.raspberry_status[rb]:

            if action == "start":

                print(self.raspberry_info)

                w, h = self.raspberry_info[rb]["video mode"].split("x")
                #w, h = self.video_mode[rb].currentText().split("x")
                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{cfg.SERVER_PORT}/video_streaming/start?&w={w}&h={h}")
                if r.status_code == 200:
                    self.rb_msg(rb, f"Video streaming started")
                else:
                    self.rb_msg(rb, f"Error starting the video streaming")
                    return
                time.sleep(1)
                self.media_list.setMedia(QMediaContent(QUrl(f"http://{self.RASPBERRY_IP[rb]}:9090/stream/video.mjpeg")))
                self.media_list.play()
                self.stack_list.setCurrentIndex(2)
                self.combo_list.setCurrentIndex(2)

                # generate QR code
                try:
                    import qrcode
                    img = qrcode.make(f"http://{self.RASPBERRY_IP[rb]}:9090/stream/video.mjpeg")
                    self.image_label[rb].setPixmap(QPixmap.fromImage(ImageQt(img)))   #.scaled(self.image_label[rb].size(), Qt.KeepAspectRatio))
                except:
                    logging.info("qrcode module not installed")

            if action == "stop":
                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{cfg.SERVER_PORT}/video_streaming/stop")
                if r.status_code == 200:
                    self.rb_msg(rb, f"Video streaming stopped")
                    self.stack_list.setCurrentIndex(0)
                    self.combo_list.setCurrentIndex(0)

            self.status_one(output=False)


    def combo_index_changed(self, idx):
        '''
        switch view for client output
        '''
        self.stack_list.setCurrentIndex(idx)


    def send_public_key(self, rb):
        '''
        send the public key id_rsa.pub (if any)
        '''
        if rb in self.RASPBERRY_IP and self.raspberry_status[rb]:
            if (pathlib.Path.home() / pathlib.Path(".ssh") / pathlib.Path("id_rsa.pub")).is_file():
                # read content of id_rsa.pub file
                with open(pathlib.Path.home() / pathlib.Path(".ssh") / pathlib.Path("id_rsa.pub"), "r") as f_in:
                    file_content = f_in.read()

                #print(base64.b64encode(file_content.encode("utf-8")).decode('utf-8'))

                #print(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/add_key/{base64.b64encode(file_content.encode('utf-8')).decode('utf-8')}")

                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{cfg.SERVER_PORT}/add_key/{base64.b64encode(file_content.encode('utf-8')).decode('utf-8')}")
                if r.status_code == 200:
                    self.rb_msg(rb, f"send public key: {r.text}")
                else:
                    self.rb_msg(rb, f"Error sending public key: {r.text}")



    def go_left(self):
        pass


    def go_right(self):
        pass


    def video_list(self, raspberry_id):
        """
        request a list of video to server
        """

        if raspberry_id in self.RASPBERRY_IP and self.raspberry_status[raspberry_id]:
            try:
                r = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}:{cfg.SERVER_PORT}/video_list")
                if r.status_code == 200:
                    self.rb_msg(raspberry_id, "list received (* for files not in archive)")
                    r2 = eval(r.text)
                    if "video_list" in r2:
                        for x in sorted(r2["video_list"]):
                            if not pathlib.Path(cfg.VIDEO_ARCHIVE + "/" + x).is_file():
                                self.raspberry_output[raspberry_id] += f"<b>* {x}</b><br>"
                            else:
                                self.raspberry_output[raspberry_id] += f"{x}<br>"

                    self.rb_msg(raspberry_id, "")
                else:
                    self.rb_msg(raspberry_id, f"<b>Error status code: {r.status_code}</b>")
                    self.status_one(output=False)
            except Exception:
                self.rb_msg(raspberry_id, "<b>Error</b>")



    def video_list_from_all(self):
        """
        request a list of video to all raspberries
        """
        for rb in sorted(self.RASPBERRY_IP.keys()):
            self.video_list(rb)


    def rb_msg(self, raspberry_id, msg):

        print(f"<pre>{date_iso()}: {msg}</pre>")

        if raspberry_id not in self.raspberry_output:
            self.raspberry_output[raspberry_id] = ""
        self.raspberry_output[raspberry_id] += f"<pre>{date_iso()}: {msg}</pre>"

        if raspberry_id == self.current_raspberry_id:
            self.text_list.setText(self.raspberry_output[raspberry_id])

        app.processEvents()


    def send_command(self, rb):
        '''
        send command to a raspberry and retrieve output
        '''
        if rb in self.RASPBERRY_IP and self.raspberry_status[rb]:
            text, ok = QInputDialog.getText(self, "Send a command", "Command:")
            if not ok:
                return
            self.rb_msg(rb, f"sent command: {text}")
            try:
                cmd = base64.b64encode(text.encode('utf-8')).decode('utf-8')
                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{cfg.SERVER_PORT}/command/{cmd}")
                if r.status_code == 200:
                    r_dict = eval(r.text)
                    if r_dict.get("status", "") != "error":
                        self.rb_msg(rb, f"Return code: {r_dict.get('return_code', '-')}")
                        self.rb_msg(rb, f"output:\n{r_dict.get('output', '-')}")
                    else:
                        self.rb_msg(rb, "<b>Error</b>")
                else:
                    self.rb_msg(rb, f"<b>Error status_code: {r.status_code}</b>")
            except Exception:
                self.rb_msg(rb, "<b>Error</b>")
                self.status_one(rb, output=False)


    def send_command_all(self):
        """
        send command to all raspberries
        """
        text, ok = QInputDialog.getText(self, "Send a command to all", "Command:")
        if not ok:
            return

        for rb in sorted(self.RASPBERRY_IP.keys()):
            if self.raspberry_status[rb]:
                self.rb_msg(rb, f"sent command: {text}")
                try:
                    cmd = base64.b64encode(text.encode('utf-8')).decode('utf-8')
                    r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/command/{cmd}")
                    if r.status_code == 200:
                        r2 = eval(r.text)
                        self.rb_msg(rb, f"Return code: {r2.get('return_code', '-')}")
                        self.rb_msg(rb, "output:\n" + r2.get("output", "-"))
                    else:
                        self.rb_msg(rb, f"<b>Error status_code: {r.status_code}</b>")
                except Exception:
                    if DEBUG:
                        raise
                    self.rb_msg(rb, "<b>Error</b>")
                    self.status_one(rb, output=False)


    def reboot(self, rb):
        """
        send reboot signal to raspberry
        """
        if rb in self.RASPBERRY_IP and self.raspberry_status[rb]:
            text, ok = QInputDialog.getText(self, "Reboot rasberry", "confirm writing 'yes'")
            if not ok or text != "yes":
                return
            try:
                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/reboot")
                if r.status_code == 200:
                    self.rb_msg(rb, r.text)
                else:
                    self.rb_msg(rb, f"Error status code: {r.status_code}")
            except Exception:
                self.rb_msg(rb, "Error")
                self.status_one(rb, output=False)


    def reboot_all(self):
        """
        shutdown all raspberries
        """
        text, ok = QInputDialog.getText(self, "Reboot all rasberries", "confirm writing 'yes'")
        if not ok or text != "yes":
            return

        for rb in sorted(self.RASPBERRY_IP.keys()):
            if self.raspberry_status[rb]:
                try:
                    r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/reboot")

                except Exception:
                    self.rb_msg(rb, "Error")
                    self.status_one(rb)


    def shutdown(self, raspberry_id):
        """
        send shutdown signal to Raspberry pi
        """
        try:
            r = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}:{SERVER_PORT}/shutdown")
            if r.status_code == 200:
                self.rb_msg(raspberry_id, r.text)
            else:
                self.rb_msg(raspberry_id, f"Error status code: {r.status_code}")
        except Exception:
            self.rb_msg(raspberry_id, "Error")
            self.status_one()


    def shutdown_all(self):
        """
        shutdown all raspberries
        """
        text, ok = QInputDialog.getText(self, "Shutdown all Rasberries Pi", "lease confirm writing 'yes'")
        if not ok or text != "yes":
            return

        for raspberry_id in sorted(self.RASPBERRY_IP.keys()):
            if self.raspberry_status[raspberry_id]:
                self.shutdown(self, raspberry_id)


    def clear_all_output(self):
        for raspberry_id in self.RASPBERRY_IP:
             self.raspberry_output[raspberry_id] = ""
        self.text_list.clear()

    def clear_output(self):
        self.text_list.clear()


    def blink(self):
        """
        blink the power led
        """
        if self.RASPBERRY_IP.get(self.current_raspberry_id, ""):
            self.rb_msg(self.current_raspberry_id, "blink requested")
            try:
                r = requests.get(f"http://{self.RASPBERRY_IP[self.current_raspberry_id]}:{SERVER_PORT}/blink", timeout=2)
            except Exception:
                self.rb_msg(self.current_raspberry_id, "Error")
                self.status_one(self.current_raspberry_id)

    '''
    def status(self, rb, output=True):
        """
        ask client status
        """
        try:
            if self.RASPBERRY_IP.get(rb, ""):

                r1 = ping(self.RASPBERRY_IP[rb])

                # check if answer to ping
                if not r1:
                    color = "red"
                else:
                    if output:
                        self.rb_msg(rb, "status requested")
                    r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/status", timeout=1)
                    if output:
                        logging.info(f"raspberry: {rb} status_code: {r.status_code}")
                    if r.status_code == 200:
                        if output:
                            self.rb_msg(rb, json_formater(r.text))
                        r_dict = eval(r.text)
                        color = "green" if r_dict["status"] == "OK" else "red"
                    else:
                        color = "red"
            else:
                color = "red"
        except Exception:
            color = "red"

        # check if recording
        if color == "green" and r_dict.get("video_recording", False):
            color = "orange"
            self.record_button[rb].setStyleSheet(f"background: {color};")
        else:
            self.record_button[rb].setStyleSheet("")

        # check if streaming
        if color == "green" and  r_dict.get("video_streaming_active", False):
            color = "yellow"
            self.video_streaming_btn[rb].setStyleSheet(f"background: {color};")
        else:
            self.video_streaming_btn[rb].setStyleSheet("")

        self.status_list[rb].setStyleSheet(f"background: {color};")
        self.raspberry_status[rb] = (color != "red")

        self.tw.setTabIcon(sorted(RASPBERRY_MAC_ADDR.values()).index(rb), QIcon(f"{color}.png"))

        if color == "red" and output:
            self.rb_msg(rb, "status: not available")
    '''


    def status2(self, rb):
        '''
        ask client status
        '''

        try:
            if self.RASPBERRY_IP.get(rb, ""):

                r1 = ping(self.RASPBERRY_IP[rb])

                # check if answer to ping
                if not r1:
                    r_dict = {"status": "not available (ping failed)"}
                else:
                    r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{cfg.SERVER_PORT}/status", timeout=cfg.TIME_OUT)
                    if r.status_code == 200:
                        r_dict = eval(r.text)
                    else:
                        r_dict = {"status": "not available1"}
            else:
                r_dict = {"status": "not available2"}
        except Exception:
            r_dict = {"status": "not available3"}

        self.raspberry_status[rb] = (r_dict["status"] == "OK")

        self.status_dict[rb] = dict(r_dict)


    def status_one(self, output=True):
        """
        ask status to one rasberry
        """

        if output: self.rb_msg(self.current_raspberry_id, "status requested")
        self.status2(self.current_raspberry_id)
        if output: self.rb_msg(self.current_raspberry_id, json_formater(str(self.status_dict[self.current_raspberry_id])))

        self.update_raspberry_display(self.current_raspberry_id)


    def update_raspberry_display(self, rb):


        if self.status_dict[rb]["status"] == "OK":
            color = "green"
            if self.status_dict[rb].get("video_recording", False):
                color = "orange"
            if self.status_dict[rb].get("video_streaming_active", False):
                color = "yellow"
        else:
            color = "red"
        self.status_list.setStyleSheet(f"background: {color};")
        self.record_button.setStyleSheet(f"background: {color};" if self.status_dict[rb].get("video_recording", False) else "")
        self.video_streaming_btn.setStyleSheet(f"background: {color};" if self.status_dict[rb].get("video_streaming_active", False) else "")

        for x in range(self.rasp_list.count()):
            if self.rasp_list.item(x).text() == rb:
                self.rasp_list.item(x).setIcon(QIcon(f"{color}.png"))



    def status_all(self, output=True):
        """
        ask status to all Raspberries Pi
        """

        '''
        if output:
            for rb in sorted(self.RASPBERRY_IP.keys()):
                print(rb)
                self.status_list[rb].setStyleSheet("")
        '''

        self.status_dict = {}
        threads = []
        for raspberry_id in sorted(self.RASPBERRY_IP.keys()):
            if output: self.rb_msg(raspberry_id, "status requested")
            threads.append(threading.Thread(target=self.status2, args=(raspberry_id,)))
            threads[-1].start()
        for x in threads:
            x.join()

        for x in range(self.rasp_list.count()):
            rb = self.rasp_list.item(x).text()

            if self.status_dict[rb]["status"] == "OK":
                color = "green"
                if self.status_dict[rb].get("video_recording", False):
                    color = "orange"
                if self.status_dict[rb].get("video_streaming_active", False):
                    color = "yellow"
            else:
                color = "red"

            self.rasp_list.item(x).setIcon(QIcon(f"{color}.png"))

        '''
        for rb in self.status_dict:
            if output: self.rb_msg(rb, json_formater(str(self.status_dict[rb])))
            self.update_raspberry_display(rb)
        '''


    def time_synchro(self, raspberry_id):
        """
        Set date/time on Raspberry Pi
        """

        if raspberry_id in self.RASPBERRY_IP and self.raspberry_status[raspberry_id]:
            date, hour = date_iso().split(" ")
            try:
                r = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}:{SERVER_PORT}/sync_time/{date}/{hour}")
                return {"raspberry_id": raspberry_id, "msg": json.loads(r.text), "error": False}
            except Exception:
                return {"raspberry_id": raspberry_id, "msg": "Error during time synchronization", "error": True}


    def time_synchro_all(self):
        """
        synchronize all Raspberries Pi
        """

        pool = ThreadPool()
        results = pool.map_async(self.time_synchro, list(self.RASPBERRY_IP.keys()))
        return_val = results.get()

        for x in return_val:
            self.raspberry_output[x["raspberry_id"]] += pprint.pformat(x["msg"])




    def one_picture(self, rb):
        """
        ask one picture
        """
        if rb in self.RASPBERRY_IP and self.raspberry_status[rb]:
            try:
                self.rb_msg(rb, "picture requested")
                w, h = self.resolution[rb].currentText().split("x")
                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/one_picture?w={w}&h={h}")

                r2 = eval(r.text)
                if r2["result"] == "OK":
                    r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/static/live.jpg", stream=True)
                    if r.status_code == 200:
                        with open(f"live_{rb}.jpg", "wb") as f:
                            r.raw.decode_content = True
                            shutil.copyfileobj(r.raw, f)
                        self.rb_msg(rb, "OK")

                        self.image_label[rb].setPixmap(QPixmap(f"live_{rb}.jpg").scaled(self.image_label[rb].size(), Qt.KeepAspectRatio))
                        self.stack_list[rb].setCurrentIndex(1)
                        self.combo_list[rb].setCurrentIndex(1)

                    else:
                        self.rb_msg(rb, "Error1")
                else:
                    self.rb_msg(rb, "Error2")

            except requests.exceptions.ConnectionError:
                self.rb_msg(rb, "Connection refused")

            except Exception:
                if DEBUG: raise
                self.rb_msg(rb, "Error3")


    def start_video_recording(self, rb):
        """
        start video recording with selected parameters
        """

        if rb in self.RASPBERRY_IP and self.raspberry_status[rb]:
            w, h = self.video_mode[rb].currentText().split("x")
            try:
                r = requests.get((f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/start_video?"
                                  f"duration={self.duration[rb].value()}&w={w}&h={h}&prefix={self.prefix[rb].text()}&fps={self.fps[rb].value()}&quality={self.video_quality[rb].value()}")
                                )
                self.rb_msg(rb, r.text)
                self.status_one(rb)

            except requests.exceptions.ConnectionError:
                self.rb_msg(rb, "Connection refused")
                self.status_one(rb, output=False)

            except Exception:
                self.rb_msg(rb, "Error1")
                self.status_one(rb, output=False)


    def stop_video_recording(self, rb):
        """
        stop the video recording
        """
        if rb in self.RASPBERRY_IP and self.raspberry_status[rb]:
            try:
                self.rb_msg(rb, "stop video recording requested")
                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/stop_video")
                self.rb_msg(rb, r.text)
                self.status_one(rb, output=False)
            except Exception:
                self.rb_msg(rb, "Error2")
                self.status_one(rb, output=False)


    def delete_all_video(self, rb):
        """
        delete all video from server
        """
        text, ok = QInputDialog.getText(self, f"Delete all video from Rasberry {rb}", "confirm writing 'yes'")
        if not ok or text != "yes":
            return
        try:
            self.rb_msg(rb, "deletion of all video requested")
            r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/delete_all_video")
            if r.status_code == 200:
                r2 = eval(r.text)
                if r2.get("status", "") == "OK":
                    self.rb_msg(rb, "All video deleted")
                if r2.get("status", "") == "error":
                    self.rb_msg(rb, "<b>Error deleting all video</b>")

            else:
                self.rb_msg(rb, f"<b>Error status code: {r.status_code}</b>")
        except Exception:
            self.rb_msg(rb, "<b>Error</b>")


    def get_log(self):

        if self.current_raspberry_id in self.RASPBERRY_IP and self.raspberry_status[self.current_raspberry_id]:
            try:
                r = requests.get(f"http://{self.RASPBERRY_IP[self.current_raspberry_id]}:{SERVER_PORT}/get_log")
                self.rb_msg(self.current_raspberry_id, r.text)
            except Exception:
                self.rb_msg(self.current_raspberry_id, "Error")


    def update_all(self):
        """
        update server on all raspberries
        """
        text, ok = QInputDialog.getText(self, "Update server on all raspberries", "confirm writing 'yes'")
        if not ok or text != "yes":
            return

        for rb in sorted(self.RASPBERRY_IP.keys()):
            if self.raspberry_status[rb]:
                self.rb_msg(rb, "Server update requested")
                r = os.system(f"scp server.py pi@{self.RASPBERRY_IP[rb]}:{CLIENT_PROJECT_DIRECTORY}")
                if not r:
                    self.rb_msg(rb, "Server updated")
                else:
                    self.rb_msg(rb, "<b>Error during server update</b>")




    def download_videos(self, raspberry_id, download_dir=""):
        """
        download all video from one raspberry
        """

        if download_dir == "":
            download_dir = cfg.VIDEO_ARCHIVE

        if not pathlib.Path(download_dir).is_dir():
            QMessageBox.critical(None, "Raspberry controller",
                                 f"Destination not found!<br>{cfg.VIDEO_ARCHIVE}<br><br>Choose another directory",
                                 QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)

            new_download_dir = QFileDialog().getExistingDirectory(self, "Choose a directory to download videos",
                                                                  str(pathlib.Path.home()),
                                                                  options=QFileDialog.ShowDirsOnly)
            if new_download_dir:
                download_dir = new_download_dir
            else:
                return

        if raspberry_id in self.RASPBERRY_IP and self.raspberry_status[raspberry_id]:

            try:
                r = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}:{cfg.SERVER_PORT}/video_list")
                if r.status_code == 200:
                    self.rb_msg(raspberry_id, "list received (* for files not in archive)")
                    r2 = eval(r.text)
                    if "video_list" in r2:
                        for x in sorted(r2["video_list"]):
                            if not pathlib.Path(cfg.VIDEO_ARCHIVE + "/" + x).is_file():
                                print(f"dOWNLOADING {x}")

                                with requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}:{cfg.SERVER_PORT}/static/video_archive/{x}", stream=True) as r:
                                        with open(cfg.VIDEO_ARCHIVE + "/" + x, 'wb') as f:
                                            shutil.copyfileobj(r.raw, f)


                                # r = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}:{cfg.SERVER_PORT}/static/video_archive/{x}")

                                print(f"{x} downloaded")

                    self.rb_msg(raspberry_id, "")
                else:
                    self.rb_msg(raspberry_id, f"<b>Error status code: {r.status_code}</b>")
                    self.status_one(output=False)
            except Exception:
                self.rb_msg(raspberry_id, "<b>Error</b>")




    def read_process_stdout(self, rb):

        out = self.download_process[rb].readAllStandardOutput()
        self.rb_msg(rb, bytes(out).decode("utf-8").strip())


    def process_error(self, process_error, rb):
        logging.info(f"process error: {process_error}")
        logging.info(f"process state: {self.download_process[rb].state()}")
        self.rb_msg(rb, f"Error downloading video.\nProcess error: {process_error}  Process state: {self.download_process[rb].state()}")
        self.download_button[rb].setStyleSheet("")


    def download_finished(self, exitcode, rb):
        """
        download finished
        """
        print("exit code", exitcode)
        if exitcode:
            self.rb_msg(rb, f"Error downloading video.\nExit code: {exitcode}")
        else:
            self.rb_msg(rb, "File downloaded.")

        self.download_button[rb].setStyleSheet("")


    def download_all_video_from_all(self):
        """
        download all video from all raspberries
        """
        text, ok = QInputDialog.getText(self, "Download video from all raspberries", "confirm writing 'yes'")
        if not ok or text != "yes":
            return

        if not pathlib.Path(cfg.VIDEO_ARCHIVE).is_dir():
            QMessageBox.critical(None, "Raspberry - Video recording",
                                 f"Destination not found!<br>{cfg.VIDEO_ARCHIVE}<br><br>Choose another directory",
                                 QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)

            new_download_dir = QFileDialog().getExistingDirectory(self, "Choose a directory to download video",
                                                                  str(pathlib.Path.home()),
                                                                  options=QFileDialog.ShowDirsOnly)

            if not new_download_dir:
                return
            else:
                download_dir = new_download_dir
        else:
            download_dir = cfg.VIDEO_ARCHIVE


        for rb in sorted(self.RASPBERRY_IP.keys()):
            if self.raspberry_status[rb]:
                self.download_all_video(rb, download_dir)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    video_recording_control = Video_recording_control()
    sys.exit(app.exec_())
