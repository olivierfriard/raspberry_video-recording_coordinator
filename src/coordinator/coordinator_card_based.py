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



from config_coordinator import *

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

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Raspberry - Video recording")
        self.statusBar().showMessage(f"v. {__version__} - {__version_date__}    WIFI SSID: {get_wifi_ssid()}    IP address: {get_wlan_ip_address()}")

        self.setGeometry(0, 0, 1300, 768)

        layout = QVBoxLayout()
        hlayout1 = QHBoxLayout()

        stylesheet = """QTabBar::tab:selected {background: lightgray;} QTabWidget>QWidget>QWidget{background: lightgray;}"""
        self.tw = QTabWidget()
        self.tw.setStyleSheet(stylesheet)

        q1 = QWidget()

        self.raspberry_status = {}
        rasp_count = 0


        # buttons for all raspberries
        hlayout_all_buttons = QHBoxLayout()
        hlayout_all_buttons.addWidget(QPushButton("Status from all", clicked=partial(self.status_all, output=True)))
        hlayout_all_buttons.addWidget(QPushButton("Sync time all", clicked=self.sync_all))
        hlayout_all_buttons.addWidget(QPushButton("video list from all", clicked=self.video_list_from_all))
        hlayout_all_buttons.addWidget(QPushButton("Download video from all", clicked=self.download_all_video_from_all))
        #hlayout_all_buttons.addWidget(QPushButton("Update all server", clicked=self.update_all))
        hlayout_all_buttons.addWidget(QPushButton("Send command to all", clicked=self.send_command_all))
        hlayout_all_buttons.addWidget(QPushButton("Clear all output", clicked=self.clear_all_output))
        hlayout_all_buttons.addWidget(QPushButton("Reboot all", clicked=self.reboot_all))
        hlayout_all_buttons.addWidget(QPushButton("Shutdown all", clicked=self.shutdown_all))
        hlayout_all_buttons.addWidget(QPushButton("Scan network", clicked=partial(self.scan_network, output=True)))
        layout.addLayout(hlayout_all_buttons)

        # add navigation buttons
        hlayout_navigation_buttons = QHBoxLayout()
        hlayout_navigation_buttons.addWidget(QPushButton("<-", clicked=self.go_left))
        hlayout_navigation_buttons.addWidget(QPushButton("->", clicked=self.go_right))
        self.message_box = QLabel('...')
        hlayout_navigation_buttons.addWidget(self.message_box)
        hlayout_navigation_buttons.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        layout.addLayout(hlayout_navigation_buttons)



        self.scan_network(output=True)


        for rb in sorted(self.RASPBERRY_IP.keys()):

            self.download_process[rb] = QProcess()
            rasp_count += 1

            l = QHBoxLayout()

            left_layout = QVBoxLayout()

            combo = QComboBox(self)
            combo.addItem("view command output")
            combo.addItem("view picture")
            combo.addItem("video streaming")
            combo.currentIndexChanged[int].connect(partial(self.combo_index_changed, rb))
            self.combo_list[rb] = combo
            left_layout.addWidget(self.combo_list[rb])

            self.stack_list[rb] = QStackedWidget()

            self.stack1 = QWidget()
            # command output
            stack1_layout = QHBoxLayout()
            self.text_list[rb] = QTextEdit()
            self.text_list[rb].setLineWrapMode(QTextEdit.NoWrap)
            self.text_list[rb].setFontFamily("Monospace")
            stack1_layout.addWidget(self.text_list[rb])
            self.stack1.setLayout(stack1_layout)

            # image viewer
            self.stack2 = QWidget()
            stack2_layout = QHBoxLayout()
            stack2_layout.setContentsMargins(0, 0, 0, 0)
            self.image_label[rb] = QLabel()
            self.image_label[rb].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.image_label[rb].setAlignment(Qt.AlignCenter)
            self.image_label[rb].setStyleSheet("QLabel {background-color: black;}")

            stack2_layout.addWidget(self.image_label[rb])
            self.stack2.setLayout(stack2_layout)

            self.stack_list[rb].addWidget(self.stack1)
            self.stack_list[rb].addWidget(self.stack2)

            # video streaming viewer
            self.stack3 = QWidget()
            stack3_layout = QHBoxLayout()
            stack3_layout.setContentsMargins(0, 0, 0, 0)

            mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
            self.media_list[rb] = mediaPlayer
            videoWidget = QVideoWidget()

            # Create a widget for window contents
            wid = QWidget(self)
            layout_video = QHBoxLayout()
            layout_video.setContentsMargins(0, 0, 0, 0)
            layout_video.addWidget(videoWidget)

            # Set widget to contain window contents
            wid.setLayout(layout_video)

            self.media_list[rb].setVideoOutput(videoWidget)
            stack3_layout.addWidget(wid)

            self.stack3.setLayout(stack3_layout)

            self.stack_list[rb].addWidget(self.stack1)
            self.stack_list[rb].addWidget(self.stack2)
            self.stack_list[rb].addWidget(self.stack3)

            left_layout.addWidget(self.stack_list[rb])
            self.stack_list[rb].setCurrentIndex(0)

            right_layout = QVBoxLayout()

            l2 = QHBoxLayout()

            self.status_list[rb] = QPushButton("Status", clicked=partial(self.status_one, rb, output=True))
            l2.addWidget(self.status_list[rb])

            l2.addWidget(QPushButton("Sync time", clicked=partial(self.sync_time, rb)))
            l2.addWidget(QPushButton("Get log", clicked=partial(self.get_log, rb)))
            l2.addWidget(QPushButton("Clear output", clicked=partial(self.clear_output, rb)))
            l2.addWidget(QPushButton("Blink", clicked=partial(self.blink, rb)))
            l2.addWidget(QPushButton("Send key", clicked=partial(self.send_public_key, rb)))

            right_layout.addLayout(l2)

            right_layout.addWidget(QLabel("<b>Picture</b>"))
            l2 = QHBoxLayout()
            l2.addWidget(QLabel("Resolution"))
            self.resolution[rb] = QComboBox()
            for resol in RESOLUTIONS:
                self.resolution[rb].addItem(resol)
            self.resolution[rb].setCurrentIndex(DEFAULT_RESOLUTION)
            l2.addWidget(self.resolution[rb])
            right_layout.addLayout(l2)
            right_layout.addWidget(QPushButton("Take one picture", clicked=partial(self.one_picture, rb)))


            right_layout.addWidget(QLabel("<b>Video</b>"))
            l2 = QHBoxLayout()
            self.video_streaming_btn[rb] = QPushButton("Start video streaming", clicked=partial(self.video_streaming, rb, "start"))
            l2.addWidget(self.video_streaming_btn[rb])
            l2.addWidget(QPushButton("Stop video streaming", clicked=partial(self.video_streaming, rb, "stop")))
            self.record_button[rb] = QPushButton("Start video recording", clicked=partial(self.start_video_recording, rb))
            l2.addWidget(self.record_button[rb])
            l2.addWidget(QPushButton("Stop video recording", clicked=partial(self.stop_video_recording, rb)))
            right_layout.addLayout(l2)

            l2 = QHBoxLayout()
            l2.addWidget(QLabel("Video mode"))
            self.video_mode[rb] = QComboBox()
            for resol in VIDEO_MODES:
                self.video_mode[rb].addItem(resol)
            self.video_mode[rb].setCurrentIndex(DEFAULT_VIDEO_MODE)
            l2.addWidget(self.video_mode[rb])

            l2.addWidget(QLabel("Video quality Mbp/s"))
            self.video_quality[rb] = QSpinBox()
            self.video_quality[rb].setMinimum(1)
            self.video_quality[rb].setMaximum(10)
            self.video_quality[rb].setValue(DEFAULT_VIDEO_QUALITY)
            l2.addWidget(self.video_quality[rb])

            l2.addWidget(QLabel("FPS"))
            self.fps[rb] = QSpinBox()
            self.fps[rb].setMinimum(1)
            self.fps[rb].setMaximum(30)
            self.fps[rb].setValue(DEFAULT_FPS)
            l2.addWidget(self.fps[rb])

            horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
            l2.addItem(horizontalSpacer)

            right_layout.addLayout(l2)

            l2 = QHBoxLayout()
            l2.addWidget(QLabel("Duration (s)"))
            self.duration[rb] = QSpinBox()
            self.duration[rb].setMinimum(10)
            self.duration[rb].setMaximum(86400)
            self.duration[rb].setValue(DEFAULT_VIDEO_DURATION)
            l2.addWidget(self.duration[rb])

            right_layout.addLayout(l2)

            l2.addWidget(QLabel("Prefix"))
            self.prefix[rb] = QLineEdit("")
            l2.addWidget(self.prefix[rb])

            right_layout.addLayout(l2)

            # get video / video list
            l2 = QHBoxLayout()
            q = QPushButton("Video list")
            q.clicked.connect(partial(self.video_list, rb))
            l2.addWidget(q)

            self.download_button[rb] = QPushButton("Download all video", clicked=partial(self.download_all_video, rb, ""))
            l2.addWidget(self.download_button[rb])

            l2.addWidget(QPushButton("Delete all video", clicked=partial(self.delete_all_video, rb)))
            right_layout.addLayout(l2)

            right_layout.addWidget(QLabel("<b>System commands</b>"))

            l2 = QHBoxLayout()
            l2.addWidget(QPushButton("Send command", clicked=partial(self.send_command, rb)))
            l2.addWidget(QPushButton("Reboot", clicked=partial(self.reboot, rb)))
            l2.addWidget(QPushButton("Shutdown", clicked=partial(self.shutdown, rb)))

            right_layout.addLayout(l2)

            verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
            right_layout.addItem(verticalSpacer)

            l.addLayout(left_layout)
            l.addLayout(right_layout)
            hlayout1.addLayout(l)

            if rasp_count % GUI_COLUMNS_NUMBER == 0 or rasp_count == len(self.RASPBERRY_IP):
                q1.setLayout(hlayout1)
                self.tw.addTab(q1, rb)
                hlayout1 = QHBoxLayout()
                q1 = QWidget()


        self.status_all(output=True)

        # add tab widget
        layout.addWidget(self.tw)

        main_widget = QWidget(self)
        main_widget.setLayout(layout)

        self.setCentralWidget(main_widget)

        self.create_menu()

        self.show()
        app.processEvents()

        # self.scan_network(output=True)

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(lambda: self.status_all(output=False))
        self.status_timer.setInterval(REFRESH_INTERVAL * 1000)
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


    def connect(self, ip_addr):
        '''
        try to connect to http://{ip_addr}/status
        '''
        try:
            r = requests.get(f"http://{ip_addr}:{SERVER_PORT}/status", timeout=TIME_OUT)
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
                        r3 = requests.get(f"http://{ip_addr}:{SERVER_PORT}/sync_time/{date}/{hour}")
                        if r3.status_code == 200:
                            logging.info(f"{ip_addr}: sync time OK {date} {hour}")
                        else:
                            logging.info(f"{ip_addr}: sync time failed")
                    except Exception:
                        logging.info(f"{ip_addr}: sync time failed")


                    '''
                    mac_addr = r_dict.get("MAC_addr", "")


                    if mac_addr in RASPBERRY_MAC_ADDR:
                        self.RASPBERRY_IP[RASPBERRY_MAC_ADDR[mac_addr]] = ip_addr
                        # check hostname
                        remote_hostname = r_dict.get('hostname', '')
                        if remote_hostname != RASPBERRY_MAC_ADDR[mac_addr]:
                            r2 = requests.get(f"http://{ip_addr}:{SERVER_PORT}/set_hostname/{RASPBERRY_MAC_ADDR[mac_addr]}")
                            if r2.status_code == 200:
                                r2_dict = eval(r2.text)
                                logging.info(f"{ip_addr}: hostname change success: {r2_dict.get('new_hostname', '')}")
                            else:
                                logging.info(f"{ip_addr}: hostname change failed: {RASPBERRY_MAC_ADDR[mac_addr]}")
                        # set raspberry time date
                        date, hour = date_iso().split(" ")
                        try:
                            r3 = requests.get(f"http://{ip_addr}:{SERVER_PORT}/sync_time/{date}/{hour}")
                            if r3.status_code == 200:
                                logging.info(f"{ip_addr}: sync time OK {date} {hour}")
                            else:
                                logging.info(f"{ip_addr}: sync time failed")
                        except Exception:
                            logging.info(f"{ip_addr}: sync time failed")
                    '''
                except:
                    logging.debug(f"{ip_addr}: not available")
        except:
            logging.debug(f"{ip_addr}: not available")


    def scan_raspberries(self):
        '''
        scan network same network for rapsberry  clients
        '''
        current_ip = get_wlan_ip_address()

        # current_ip = get_ip()

        current_ip = '130.192.200.127'

        logging.info(f"current WLAN IP address: {current_ip}")
        ip_mask = ".".join(current_ip.split(".")[0:3])
        ip_list = [f"{ip_mask}.{x}" for x in range(WLAN_INTERVAL[0], WLAN_INTERVAL[1] + 1)]
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

        """
        self.message_box.setText("Scanning network...")
        app.processEvents()
        self.scan_raspberries()
        self.message_box.setText(f"Scanning done: {len(self.RASPBERRY_IP)} client(s) found")
        self.status_all(output=output)

        print(self.RASPBERRY_IP)


    def show_ip_list(self):
        print(" ".join([f"pi@{self.RASPBERRY_IP[x]}" for x in self.RASPBERRY_IP]))


    def video_streaming(self, rb, action):
        """
        start/stop video streaming on client and show output
        see /etc/uv4l/uv4l-raspicam.conf for default configuration
        """
        if rb in self.RASPBERRY_IP and self.raspberry_status[rb]:

            if action == "start":
                w, h = self.video_mode[rb].currentText().split("x")
                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/video_streaming/start?&w={w}&h={h}")
                if r.status_code == 200:
                    self.rb_msg(rb, f"Video streaming started")
                else:
                    self.rb_msg(rb, f"Error starting the video streaming")
                    return
                time.sleep(1)
                self.media_list[rb].setMedia(QMediaContent(QUrl(f"http://{self.RASPBERRY_IP[rb]}:9090/stream/video.mjpeg")))
                self.media_list[rb].play()
                self.stack_list[rb].setCurrentIndex(2)
                self.combo_list[rb].setCurrentIndex(2)

                # generate QR code
                try:
                    import qrcode
                    img = qrcode.make(f"http://{self.RASPBERRY_IP[rb]}:9090/stream/video.mjpeg")
                    self.image_label[rb].setPixmap(QPixmap.fromImage(ImageQt(img)))   #.scaled(self.image_label[rb].size(), Qt.KeepAspectRatio))
                except:
                    logging.INFO("qrcode module not installed")

            if action == "stop":
                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/video_streaming/stop")
                if r.status_code == 200:
                    self.rb_msg(rb, f"Video streaming stopped")
                    self.stack_list[rb].setCurrentIndex(0)
                    self.combo_list[rb].setCurrentIndex(0)

            self.status_one(rb, output=False)


    def combo_index_changed(self, rb, idx):
        '''
        switch view for client output
        '''
        self.stack_list[rb].setCurrentIndex(idx)


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

                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/add_key/{base64.b64encode(file_content.encode('utf-8')).decode('utf-8')}")
                if r.status_code == 200:
                    self.rb_msg(rb, f"send public key: {r.text}")
                else:
                    self.rb_msg(rb, f"Error sending public key: {r.text}")



    def go_left(self):
        self.tw.setCurrentIndex(self.tw.currentIndex() - 1)


    def go_right(self):
        self.tw.setCurrentIndex(self.tw.currentIndex() + 1)


    def video_list(self, rb):
        """
        request a list of video to server
        """

        if rb in self.RASPBERRY_IP and self.raspberry_status[rb]:
            try:
                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/video_list")
                if r.status_code == 200:
                    self.rb_msg(rb, "list received (* for files not in archive)")
                    r2 = eval(r.text)
                    if "video_list" in r2:
                        for x in sorted(r2["video_list"]):
                            if not pathlib.Path(VIDEO_ARCHIVE + "/" + x).is_file():
                                self.text_list[rb].append(f"<b>* {x}</b>")
                            else:
                                self.text_list[rb].append(x)
                else:
                    self.rb_msg(rb, f"<b>Error status code: {r.status_code}</b>")
                    self.status_one(rb, output=False)
            except Exception:
                self.rb_msg(rb, "<b>Error</b>")
                self.status_one(rb, output=False)


    def video_list_from_all(self):
        """
        request a list of video to all raspberries
        """
        for rb in sorted(self.RASPBERRY_IP.keys()):
            self.video_list(rb)


    def rb_msg(self, rb, msg):
        self.text_list[rb].append(f"<pre>{date_iso()}: {msg}</pre>")
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
                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/command/{cmd}")
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


    def shutdown(self, rb):
        """
        send shutdown signal to raspberry
        """
        if rb in self.RASPBERRY_IP and self.raspberry_status[rb]:
            text, ok = QInputDialog.getText(self, "Shutdown rasberry", "confirm writing 'yes'")
            if not ok or text != "yes":
                return
            try:
                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/shutdown")
                if r.status_code == 200:
                    self.rb_msg(rb, r.text)
                else:
                    self.rb_msg(rb, f"Error status code: {r.status_code}")
            except Exception:
                self.rb_msg(rb, "Error")
                self.status_one(rb)


    def shutdown_all(self):
        """
        shutdown all raspberries
        """
        text, ok = QInputDialog.getText(self, "Shutdown all rasberries", "confirm writing 'yes'")
        if not ok or text != "yes":
            return

        for rb in sorted(self.RASPBERRY_IP.keys()):
            if self.raspberry_status[rb]:
                try:
                    r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/shutdown")
                except Exception:
                    self.rb_msg(rb, "Error")
                    self.status_one(rb)


    def clear_all_output(self):
        for rb in self.RASPBERRY_IP:
             self.text_list[rb].clear()


    def clear_output(self, rb):
        self.text_list[rb].clear()


    def blink(self, rb):
        """
        blink the powed led
        """
        if self.RASPBERRY_IP.get(rb, ""):
            self.rb_msg(rb, "blink requested")
            try:
                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/blink", timeout=2)
            except Exception:
                self.rb_msg(rb, "Error")
                self.status_one(rb)

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
                    r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/status", timeout=TIME_OUT)
                    if r.status_code == 200:
                        r_dict = eval(r.text)
                    else:
                        r_dict = {"status": "not available"}
            else:
                r_dict = {"status": "not available"}
        except Exception:
            r_dict = {"status": "not available"}

        self.raspberry_status[rb] = (r_dict["status"] == "OK")

        self.status_dict[rb] = dict(r_dict)


    def status_one(self, rb, output=True):
        """
        ask status to one rasberry
        """
        if output: self.rb_msg(rb, "status requested")
        self.status2(rb)
        if output: self.rb_msg(rb, json_formater(str(self.status_dict[rb])))

        self.update_raspberry_display(rb)


    def update_raspberry_display(self, rb):

        if self.status_dict[rb]["status"] == "OK":
            color = "green"
            if self.status_dict[rb].get("video_recording", False):
                color = "orange"
            if self.status_dict[rb].get("video_streaming_active", False):
                color = "yellow"
        else:
            color = "red"
        self.status_list[rb].setStyleSheet(f"background: {color};")
        self.record_button[rb].setStyleSheet(f"background: {color};" if self.status_dict[rb].get("video_recording", False) else "")
        self.video_streaming_btn[rb].setStyleSheet(f"background: {color};" if self.status_dict[rb].get("video_streaming_active", False) else "")
        self.tw.setTabIcon(sorted(self.RASPBERRY_IP.keys()).index(rb), QIcon(f"{color}.png"))



    def status_all(self, output=True):
        """
        ask status to all raspberries
        """
        if output:
            for rb in sorted(self.RASPBERRY_IP.keys()):
                self.status_list[rb].setStyleSheet("")

        self.status_dict = {}
        threads = []
        for rb in sorted(self.RASPBERRY_IP.keys()):
            if output: self.rb_msg(rb, "status requested")
            threads.append(threading.Thread(target=self.status2, args=(rb,)))
            threads[-1].start()
        for x in threads:
            x.join()

        for rb in self.status_dict:
            if output: self.rb_msg(rb, json_formater(str(self.status_dict[rb])))
            self.update_raspberry_display(rb)



    def sync_time(self, rb):
        """
        Set date/time on raspberry
        """
        if rb in self.RASPBERRY_IP and self.raspberry_status[rb]:
            date, hour = date_iso().split(" ")
            self.rb_msg(rb, "Time synchronization requested")
            try:
                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/sync_time/{date}/{hour}")
                self.rb_msg(rb, json_formater(r.text))
            except Exception:
                self.rb_msg(rb, "Error")
                self.status_one(rb)


    def sync_all(self):
        """
        synchronize all raspberries
        """
        for rb in sorted(self.RASPBERRY_IP.keys()):
            self.sync_time(rb)


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


    def get_log(self, rb):

        if rb in self.RASPBERRY_IP and self.raspberry_status[rb]:
            try:
                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/get_log")
                self.rb_msg(rb, r.text)
            except Exception:
                self.rb_msg(rb, "Error")


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


    def download_all_video(self, rb, download_dir=""):
        """
        download all video from one raspberry
        """

        if download_dir == "":
            download_dir = VIDEO_ARCHIVE

        if not pathlib.Path(download_dir).is_dir():
            QMessageBox.critical(None, "Raspberry controller",
                                 f"Destination not found!<br>{VIDEO_ARCHIVE}<br><br>Choose another directory",
                                 QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)

            new_download_dir = QFileDialog().getExistingDirectory(self, "Choose a directory to download video",
                                                                  str(pathlib.Path.home()),
                                                                  options=QFileDialog.ShowDirsOnly)
            if new_download_dir:
                download_dir = new_download_dir
            else:
                return

        if rb in self.RASPBERRY_IP and self.raspberry_status[rb]:

            self.clear_output(rb)
            self.download_button[rb].setStyleSheet("background: red;")
            app.processEvents()
            self.download_process[rb] = QProcess()
            self.download_process[rb].setProcessChannelMode(QProcess.MergedChannels)
            self.download_process[rb].readyReadStandardOutput.connect(lambda: self.read_process_stdout(rb))
            self.download_process[rb].error.connect(lambda x: self.process_error(x, rb))
            self.download_process[rb].finished.connect(lambda exitcode: self.download_finished(exitcode, rb))

            self.download_process[rb].start("rsync",
                                            ["-avz",
                                             f"pi@{self.RASPBERRY_IP[rb]}:{CLIENT_PROJECT_DIRECTORY}/static/video_archive/",
                                             download_dir])


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

        if not pathlib.Path(VIDEO_ARCHIVE).is_dir():
            QMessageBox.critical(None, "Raspberry - Video recording",
                                 f"Destination not found!<br>{VIDEO_ARCHIVE}<br><br>Choose another directory",
                                 QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)

            new_download_dir = QFileDialog().getExistingDirectory(self, "Choose a directory to download video",
                                                                  str(pathlib.Path.home()),
                                                                  options=QFileDialog.ShowDirsOnly)

            if not new_download_dir:
                return
            else:
                download_dir = new_download_dir
        else:
            download_dir = VIDEO_ARCHIVE


        for rb in sorted(self.RASPBERRY_IP.keys()):
            if self.raspberry_status[rb]:
                self.download_all_video(rb, download_dir)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    video_recording_control = Video_recording_control()
    sys.exit(app.exec_())
