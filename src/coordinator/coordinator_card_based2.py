"""
Raspberry Pi coordinator (via TCP/IP)


TODO:

* CLIENT_PROJECT_DIRECTORY: ask to raspberry
* raspberry uptime
* scan network wit QThread


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
from PyQt5.QtCore import QTimer, Qt, QUrl, pyqtSignal, QObject, QThread
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
import shutil

try:
    import config_coordinator_local as cfg
except Exception:
    print("file config_coordinator_local.py not found")
    try:
        import config_coordinator as cfg
    except Exception:
        print("file config_coordinator.py not found")
        sys.exit()



__version__ = "7"
__version_date__ = "2021-09-02"


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


from coordinator_ui import Ui_MainWindow

class Video_recording_control(QMainWindow, Ui_MainWindow):


    class Download_videos_worker(QObject):
        def __init__(self, raspberry_ip):
            super().__init__()
            self.raspberry_ip = raspberry_ip

        start = pyqtSignal(str, list)
        finished = pyqtSignal(str)

        def run(self, raspberry_id, videos_list):
            print(raspberry_id, videos_list)

            output = ""
            for video_file_name in sorted(videos_list):
                if not pathlib.Path(cfg.VIDEO_ARCHIVE + "/" + video_file_name).is_file():

                    logging.info(f"Downloading  {video_file_name} from {raspberry_id}")

                    with requests.get(f"http://{self.raspberry_ip[raspberry_id]}{cfg.SERVER_PORT}/static/video_archive/{video_file_name}", stream=True) as r:
                            with open(cfg.VIDEO_ARCHIVE + "/" + video_file_name, 'wb') as file_out:
                                shutil.copyfileobj(r.raw, file_out)

                    logging.info(f"{video_file_name} downloaded from {raspberry_id}")
                    output += f"{video_file_name} downloaded\n"

            if output == "":
                self.finished.emit("No video to download")
            else:
                self.finished.emit(output)


    RASPBERRY_IP = {}
    raspberry_info = {}

    def __init__(self, parent=None):
        super().__init__()

        self.current_raspberry_id = ""
        self.raspberry_status = {}
        self.raspberry_output = {}

        #super(MainWindow, self).__init__(parent)
        self.setupUi(self)

        self.define_connections()

        self.setWindowTitle("Raspberry Pi coordinator")
        self.statusBar().showMessage(f"v. {__version__} - {__version_date__}    WIFI SSID: {get_wifi_ssid()}    IP address: {get_wlan_ip_address()}")

        self.setGeometry(0, 0, 1300, 768)



        # self.scan_network(output=True)

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.status_for_all_rpi)
        self.status_timer.setInterval(cfg.REFRESH_INTERVAL * 1000)
        self.status_timer.start()


    def define_connections(self):
        """
        Define connections between widget and functions
        """
        self.pb_scan_network.clicked.connect(self.scan_network)
        self.rasp_list.itemClicked.connect(self.rasp_list_clicked)

        # menu
        self.actionExit.triggered.connect(self.close)
        self.actionShow_IP_address.triggered.connect(self.show_ip_list)

        self.rasp_tw.setCurrentIndex(0)

        # commands
        self.status_update_pb.clicked.connect(self.status_update_pb_clicked)
        self.time_synchro_pb.clicked.connect(self.time_synchro_clicked)

        self.blink_pb.clicked.connect(self.blink)
        self.shutdown_pb.clicked.connect(self.shutdown_clicked)

        # picture
        self.take_picture_pb.clicked.connect(self.take_picture_clicked)
        self.stop_time_lapse_pb.clicked.connect(self.stop_time_lapse_clicked)

        self.picture_lb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.picture_lb.setAlignment(Qt.AlignCenter)
        self.picture_lb.setStyleSheet("QLabel {background-color: black;}")

        for resolution in cfg.PICTURE_RESOLUTIONS:
            self.picture_resolution_cb.addItem(resolution)
        self.picture_resolution_cb.setCurrentIndex(cfg.DEFAULT_PICTURE_RESOLUTION)

        self.picture_resolution_cb.currentIndexChanged.connect(self.picture_resolution_changed)
        self.picture_brightness_sb.valueChanged.connect(self.picture_brightness_changed)
        self.picture_contrast_sb.valueChanged.connect(self.picture_contrast_changed)
        self.picture_sharpness_sb.valueChanged.connect(self.picture_sharpness_changed)
        self.picture_saturation_sb.valueChanged.connect(self.picture_saturation_changed)
        self.picture_iso_sb.valueChanged.connect(self.picture_iso_changed)
        self.picture_rotation_sb.valueChanged.connect(self.picture_rotation_changed)
        self.picture_hflip_cb.clicked.connect(self.picture_hflip_changed)
        self.picture_vflip_cb.clicked.connect(self.picture_vflip_changed)
        self.picture_annotation_cb.clicked.connect(self.picture_annotation_changed)

        self.time_lapse_cb.clicked.connect(self.time_lapse_changed)
        self.time_lapse_duration_sb.valueChanged.connect(self.time_lapse_duration_changed)
        self.time_lapse_wait_sb.valueChanged.connect(self.time_lapse_wait_changed)



        # video streaming
        self.pb_start_video_streaming.clicked.connect(partial(self.video_streaming_clicked, "start"))
        self.pb_stop_video_streaming.clicked.connect(partial(self.video_streaming_clicked, "stop"))

        self.streaming_wdg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        #self.streaming_wdg.setAlignment(Qt.AlignCenter)


        # video recording
        self.start_video_recording_pb.clicked.connect(self.start_video_recording_clicked)
        self.stop_video_recording_pb.clicked.connect(self.stop_video_recording_clicked)

        self.download_videos_pb.clicked.connect(self.download_videos_clicked)

        self.video_mode_cb.currentIndexChanged.connect(self.video_mode_changed)
        self.video_duration_sb.valueChanged.connect(self.video_duration_changed)
        self.video_quality_sb.valueChanged.connect(self.video_quality_changed)
        self.video_fps_sb.valueChanged.connect(self.video_fps_changed)

        mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_list = mediaPlayer
        videoWidget = QVideoWidget()
        self.media_list.setVideoOutput(videoWidget)

        streaming_layout = QHBoxLayout()
        streaming_layout.setContentsMargins(0, 0, 0, 0)
        streaming_layout.addWidget(videoWidget)



        self.streaming_wdg.setLayout(streaming_layout)

        self.video_fps_sb.setMinimum(cfg.MIN_VIDEO_FPS)
        self.video_fps_sb.setMaximum(cfg.MAX_VIDEO_FPS)
        self.video_fps_sb.setValue(cfg.DEFAULT_FPS)

        self.video_quality_sb.setMinimum(cfg.MIN_VIDEO_QUALITY)
        self.video_quality_sb.setMaximum(cfg.MAX_VIDEO_QUALITY)
        self.video_quality_sb.setValue(cfg.DEFAULT_VIDEO_QUALITY)

        for video_mode in cfg.VIDEO_MODES:
            self.video_mode_cb.addItem(video_mode)
        self.video_mode_cb.setCurrentIndex(cfg.DEFAULT_VIDEO_MODE)

        # all
        self.all_get_status_pb.clicked.connect(self.status_for_all_rpi)
        self.all_time_synchro_pb.clicked.connect(self.time_synchro_all)
        self.all_shutdown_pb.clicked.connect(self.shutdown_all_rpi)

    def picture_resolution_changed(self, idx):
        """
        update picture resolution in raspberry info
        """
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["picture resolution"] = self.picture_resolution_cb.currentText()

    def picture_brightness_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["picture brightness"] = self.picture_brightness_sb.value()
    def picture_contrast_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["picture contrast"] = self.picture_contrast_sb.value()
    def picture_sharpness_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["picture sharpness"] = self.picture_sharpness_sb.value()
    def picture_saturation_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["picture saturation"] = self.picture_saturation_sb.value()
    def picture_iso_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["picture iso"] = self.picture_iso_sb.value()
    def picture_rotation_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["picture rotation"] = self.picture_rotation_sb.value()
    def picture_hflip_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["picture hflip"] = self.picture_hflip_cb.isChecked()
    def picture_vflip_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["picture vflip"] = self.picture_vflip_cb.isChecked()
    def picture_annotation_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["picture annotation"] = self.picture_annotation_cb.isChecked()
    def time_lapse_changed(self):
        self.raspberry_info[self.current_raspberry_id]["time lapse"] = self.time_lapse_cb.isChecked()
    def time_lapse_duration_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["time lapse duration"] = self.time_lapse_duration_sb.value()
    def time_lapse_wait_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["time lapse wait"] = self.time_lapse_wait_sb.value()




    def video_quality_changed(self):
        """
        update video quality in raspberry info
        """
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["video quality"] = self.video_quality_sb.value()

    def video_fps_changed(self):
        """
        update video FPS in raspberry info
        """
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["FPS"] = self.video_fps_sb.value()

    def video_duration_changed(self):
        """
        update video duration in raspberry info
        """
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["video duration"] = self.video_duration_sb.value()

    def video_mode_changed(self, idx):
        """
        update video mode in raspberry info
        """
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["video mode"] = self.video_mode_cb.currentText()




    def create_all_buttons(self):
        """
        Create buttons to send commands to all Raspberries Pi
        """
        # buttons for all raspberries
        hlayout_all_buttons = QHBoxLayout()
        hlayout_all_buttons.addWidget(QPushButton("video list from all", clicked=self.video_list_from_all))
        hlayout_all_buttons.addWidget(QPushButton("Download video from all", clicked=self.download_all_video_from_all))
        #hlayout_all_buttons.addWidget(QPushButton("Update all server", clicked=self.update_all))
        hlayout_all_buttons.addWidget(QPushButton("Send command to all", clicked=self.send_command_all))
        hlayout_all_buttons.addWidget(QPushButton("Clear all output", clicked=self.clear_all_output))
        hlayout_all_buttons.addWidget(QPushButton("Reboot all", clicked=self.reboot_all))
        hlayout_all_buttons.addWidget(QPushButton("Scan network", clicked=partial(self.scan_network, output=True)))

        return hlayout_all_buttons


    def rasp_list_clicked(self, item):
        """
        update the current Raspberry Pi
        """

        self.current_raspberry_id = item.text()
        self.get_raspberry_status(self.current_raspberry_id)
        self.raspberry_id_lb.setText(self.current_raspberry_id)
        self.update_raspberry_dashboard(self.current_raspberry_id)
        self.update_raspberry_display(self.current_raspberry_id)

        #self.text_list.setText(self.raspberry_output[self.current_raspberry_id])


    '''
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
        self.media_list.setVideoOutput(videoWidget)

        # Create a widget for window contents
        wid = QWidget(self)
        layout_video = QHBoxLayout()
        layout_video.setContentsMargins(0, 0, 0, 0)
        layout_video.addWidget(videoWidget)

        # Set widget to contain window contents
        wid.setLayout(layout_video)


        stack3_layout.addWidget(wid)

        self.stack3.setLayout(stack3_layout)

        self.stack_list.addWidget(self.stack1)
        self.stack_list.addWidget(self.stack2)
        self.stack_list.addWidget(self.stack3)

        output_layout.addWidget(self.stack_list)



        commands_layout = QVBoxLayout()

        tw_commands = QTabWidget()

        self.status_tab = QWidget()
        tw_commands.addTab(self.status_tab, "Status")


        status_layout = QVBoxLayout()

        l2 = QHBoxLayout()
        l2.addWidget(QLabel("Raspberry Pi id: "))
        self.lb_raspberry_id = QLabel(" ")
        l2.addWidget(self.lb_raspberry_id)
        status_layout.addLayout(l2)

        l2 = QHBoxLayout()
        buttons = QHBoxLayout()
        self.status_list = QPushButton("Status", clicked=partial(self.status_one, output=True))
        buttons.addWidget(self.status_list)

        buttons.addWidget(QPushButton("Sync time", clicked=self.time_synchro))
        buttons.addWidget(QPushButton("Get log", clicked=self.get_log))
        buttons.addWidget(QPushButton("Clear output", clicked=self.clear_output))
        buttons.addWidget(QPushButton("Blink", clicked=self.blink))
        buttons.addWidget(QPushButton("Send key", clicked=self.send_public_key))
        l2.addLayout(buttons)

        status_layout.addLayout(l2)

        l2 = QHBoxLayout()
        l2.addWidget(QLabel("<b>System commands</b>"))

        l2.addWidget(QPushButton("Send command", clicked=self.send_command))
        l2.addWidget(QPushButton("Reboot", clicked=self.reboot))
        l2.addWidget(QPushButton("Shutdown", clicked=self.shutdown_clicked))

        status_layout.addLayout(l2)

        verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        status_layout.addItem(verticalSpacer)


        self.status_tab.setLayout(status_layout)


        self.picture_tab = QWidget()
        tw_commands.addTab(self.picture_tab, "Picture")

        l2 = QHBoxLayout()

        l2.addWidget(QLabel("<b>Picture</b>"))

        l2.addWidget(QLabel("Resolution"))
        self.resolution = QComboBox()
        for resol in cfg.PICTURE_RESOLUTIONS:
            self.resolution.addItem(resol)
        self.resolution.setCurrentIndex(cfg.DEFAULT_PICTURE_RESOLUTION)
        l2.addWidget(self.resolution)

        l2.addWidget(QPushButton("Take one picture", clicked=self.one_picture))

        self.picture_tab.setLayout(l2)


        self.video_tab = QWidget()
        tw_commands.addTab(self.video_tab, "Video")

        video_layout = QVBoxLayout()

        l2 = QHBoxLayout()

        l2.addWidget(QLabel("<b>Video</b>"))

        self.video_streaming_btn = QPushButton("Start video streaming", clicked=partial(self.video_streaming_clicked, "start"))
        l2.addWidget(self.video_streaming_btn)
        l2.addWidget(QPushButton("Stop video streaming", clicked=partial(self.video_streaming_clicked, "stop")))

        self.record_button = QPushButton("Start video recording", clicked=self.start_video_recording)
        l2.addWidget(self.record_button)
        l2.addWidget(QPushButton("Stop video recording", clicked=self.stop_video_recording))
        video_layout.addLayout(l2)


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

        video_layout.addLayout(l2)

        l2 = QHBoxLayout()
        l2.addWidget(QLabel("Duration (s)"))
        self.duration = QSpinBox()
        self.duration.setMinimum(10)
        self.duration.setMaximum(86400)
        self.duration.setValue(cfg.DEFAULT_VIDEO_DURATION)
        l2.addWidget(self.duration)

        video_layout.addLayout(l2)

        l2.addWidget(QLabel("Video file name prefix"))
        self.prefix = QLineEdit("")
        l2.addWidget(self.prefix)

        video_layout.addLayout(l2)

        # get video / video list
        l2 = QHBoxLayout()
        q = QPushButton("Get list of videos", clicked=self.get_videos_list)
        l2.addWidget(q)

        self.download_button = QPushButton("Download videos", clicked=self.download_videos_clicked)
        l2.addWidget(self.download_button)

        self.lb_download_videos = QLabel("...")
        l2.addWidget(self.lb_download_videos)

        l2.addWidget(QPushButton("Delete all video", clicked=self.delete_all_video))
        video_layout.addLayout(l2)

        self.video_tab.setLayout(video_layout)



        commands_layout.addWidget(tw_commands)

        l.addLayout(rasp_list_layout)
        l.addLayout(commands_layout)
        l.addLayout(output_layout)

        hlayout1.addLayout(l)

        q1.setLayout(hlayout1)

        return q1
    '''



    def shutdown_clicked(self):
        """
        Shutdown the current Raspberry Pi
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
        Populate the list widget with the Raspberry Pi that were found
        """
        self.raspberry_info = {}
        self.rasp_list.clear()
        for raspberry_id in sorted(self.RASPBERRY_IP.keys()):
            self.rasp_list.addItem(QListWidgetItem(raspberry_id))
            self.raspberry_info[raspberry_id] = dict(cfg.RPI_DEFAULTS)
            

    def connect(self, ip_address):
        """
        try to connect to http://{ip_address}/status
        """
        try:
            response = requests.get(f"http://{ip_address}{cfg.SERVER_PORT}/status", timeout=cfg.TIME_OUT)
        except requests.exceptions.ConnectionError:
            logging.debug(f"{ip_address}: failed to establish a connection")
            return

        if response.status_code != 200:
            logging.debug(f"{ip_address}: server status code != 200: {response.status_code}")
            return

        logging.info(f"{ip_address}: server available")

        # check hostname
        remote_hostname = response.json().get("hostname", "")
        if not remote_hostname:
            logging.info(f"{ip_address}: hostname not found")
            return

        self.RASPBERRY_IP[remote_hostname] = ip_address

        # set raspberry time date
        date, hour = date_iso().split(" ")
        try:
            response2 = requests.get(f"http://{ip_address}{cfg.SERVER_PORT}/sync_time/{date}/{hour}")
        except requests.exceptions.ConnectionError:
            logging.debug(f"{ip_address}: failed to synchronize datetime")
            return
        if response2.status_code != 200:
            logging.debug(f"{ip_address}: failed to synchronize datetime (status scode: {response2.status_code})")
            return
        logging.info(f"{ip_address}: datetime synchronized ({date} {hour})")



    def scan_raspberries(self, ip_base_address, interval):
        '''
        Scan network {ip_base_address} for Raspberry Pi device
        '''

        ip_mask = ".".join(ip_base_address.split(".")[0:3])
        ip_list = [f"{ip_mask}.{x}" for x in range(interval[0], interval[1] + 1)]
        self.RASPBERRY_IP = {}
        threads = []
        logging.info(f"Testing {ip_base_address} subnet")
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

            ip_base_address, interval = ip_config[0], ip_config[1]
            self.scan_raspberries(ip_base_address, interval)

            self.message_box.setText(f"Scanning done: {len(self.RASPBERRY_IP)} Raspberry Pi found on {ip_config[0]}")

        # print("self.RASPBERRY_IP", self.RASPBERRY_IP)

        self.populate_rasp_list()

        self.status_for_all_rpi()



    def show_ip_list(self):
        print(" ".join([f"pi@{self.RASPBERRY_IP[x]}" for x in self.RASPBERRY_IP]))


    def video_streaming(self, raspberry_id, action):
        """
        start/stop video streaming on client and show output
        see /etc/uv4l/uv4l-raspicam.conf for default configuration
        """
        if raspberry_id in self.RASPBERRY_IP and self.raspberry_info[raspberry_id]["status"]["status"] == "OK":

            if action == "start":

                width, height = self.raspberry_info[raspberry_id]["video mode"].split("x")
                data = {"width": width, "height": height}
                response = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/video_streaming/start", data=data)

                if response.status_code == 200 and response.json().get("msg", "") == "video streaming started":
                    self.rasp_output_lb.setText(f"Video streaming started")
                else:
                    self.rasp_output_lb.setText(f"Error starting streaming")
                    return

                time.sleep(1)
                self.media_list.setMedia(QMediaContent(QUrl(f"http://{self.RASPBERRY_IP[raspberry_id]}:9090/stream/video.mjpeg")))
                self.media_list.play()
                self.rasp_output_lb.setText(f"Streaming active")

                # generate QR code
                try:
                    import qrcode
                    img = qrcode.make(f"http://{self.RASPBERRY_IP[raspberry_id]}:9090/stream/video.mjpeg")
                    self.picture_lb[raspberry_id].setPixmap(QPixmap.fromImage(ImageQt(img)))   #.scaled(self.picture_lb[rb].size(), Qt.KeepAspectRatio))
                except:
                    logging.info("qrcode module not installed")

            if action == "stop":
                self.rasp_output_lb.setText("Video streaming stop requested")
                response = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/video_streaming/stop")
                if response.status_code == 200 and response.json().get("msg", "") == "video streaming stopped":
                    self.rasp_output_lb.setText("Video streaming stopped")
                else:
                    self.rasp_output_lb.setText(f"Error stopping video streaming (status code: {response.status_code})")

            self.get_raspberry_status(raspberry_id)
            self.update_raspberry_dashboard(raspberry_id)



    '''
    def send_public_key(self, rb):
        """
        send the public key id_rsa.pub (if any)
        """
        if rb in self.RASPBERRY_IP and self.raspberry_status[rb]:
            if (pathlib.Path.home() / pathlib.Path(".ssh") / pathlib.Path("id_rsa.pub")).is_file():
                # read content of id_rsa.pub file
                with open(pathlib.Path.home() / pathlib.Path(".ssh") / pathlib.Path("id_rsa.pub"), "r") as f_in:
                    file_content = f_in.read()

                #print(base64.b64encode(file_content.encode("utf-8")).decode('utf-8'))

                #print(f"http://{self.RASPBERRY_IP[rb]}:{SERVER_PORT}/add_key/{base64.b64encode(file_content.encode('utf-8')).decode('utf-8')}")

                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}{cfg.SERVER_PORT}/add_key/{base64.b64encode(file_content.encode('utf-8')).decode('utf-8')}")
                if r.status_code == 200:
                    self.rb_msg(rb, f"send public key: {r.text}")
                else:
                    self.rb_msg(rb, f"Error sending public key: {r.text}")
        '''


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
                r = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/video_list")
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


    def update_raspberry_dashboard(self, raspberry_id):
        """
        update the Raspberry Pi dashboard
        """

        self.datetime_lb.setText(self.raspberry_info[raspberry_id]["status"].get("server_datetime", "Not available"))
        self.cpu_temp_lb.setText(self.raspberry_info[raspberry_id]["status"].get("CPU temperature", "Not available").replace("'", "°"))
        self.status_lb.setText(self.raspberry_info[raspberry_id]["status"].get("status", "Not available"))
        self.wifi_essid_lb.setText(self.raspberry_info[raspberry_id]["status"].get("wifi_essid", "Not available"))
        self.free_sd_space_lb.setText(self.raspberry_info[raspberry_id]["status"].get("free disk space", "Not available"))
        self.camera_detected_lb.setText("Yes" if self.raspberry_info[raspberry_id]["status"].get("camera detected", "") else "No")
        self.uptime_lb.setText(self.raspberry_info[raspberry_id]["status"].get("uptime", ""))
        self.ip_address_lb.setText(self.raspberry_info[raspberry_id]["status"].get("IP_address", "Not detected"))

        self.video_recording_active_lb.setText("Yes" if self.raspberry_info[raspberry_id]["status"].get("video_recording", False) else "No")

        self.video_streaming_active_lb.setText("Yes" if self.raspberry_info[raspberry_id]["status"].get("video_streaming_active", False) else "No")

        self.time_lapse_active_lb.setText("Yes" if self.raspberry_info[raspberry_id]["status"].get("time_lapse_active", False) else "No")


    def rb_msg(self, raspberry_id, msg):

        logging.info(f"{date_iso()}: {msg}")

        if raspberry_id not in self.raspberry_output:
            self.raspberry_output[raspberry_id] = ""
        self.raspberry_output[raspberry_id] += f"<pre>{date_iso()}: {msg}</pre>"


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
                r = requests.get(f"http://{self.RASPBERRY_IP[rb]}{cfg.SERVER_PORT}/command/{cmd}")
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
                    r = requests.get(f"http://{self.RASPBERRY_IP[rb]}{cfg.SERVER_PORT}/command/{cmd}")
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


    def reboot(self, raspberry_id, force_reboot=False):
        """
        send reboot signal to Raspberry Pi
        """
        if raspberry_id not in self.RASPBERRY_IP:
            return
        if not force_reboot:
            text, ok = QInputDialog.getText(self, f"Reboot Raspberry Pi {raspberry_id}", "Please confirm writing 'yes'")
            if not ok or text != "yes":
                return
        try:
            response = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/reboot")
        except requests.exceptions.ConnectionError:
            self.rasp_output_lb.setText(f"Failed to establish a connection")
            self.get_raspberry_status(raspberry_id)
            self.update_raspberry_display(raspberry_id)
            return
        if response.status_code != 200:
            self.rasp_output_lb.setText(f"Error during reboot (status code: {response.status_code})")
            return
        self.rasp_output_lb.setText(response.json().get("msg", "Error during reboot"))


    def reboot_all(self):
        """
        shutdown all Raspberry Pi
        """
        text, ok = QInputDialog.getText(self, "Reboot all Raspberry Pi", "Please confirm writing 'yes'")
        if not ok or text != "yes":
            return

        for raspberry_id in self.RASPBERRY_IP:
            self.reboot(raspberry_id, force_reboot=True)


    def shutdown(self, raspberry_id):
        """
        send shutdown signal to Raspberry pi
        """
        if raspberry_id not in self.RASPBERRY_IP:
            return
        self.rasp_output_lb.setText("Shutdown requested")
        try:
            response = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/shutdown")
        except requests.exceptions.ConnectionError:
            self.rasp_output_lb.setText(f"Failed to establish a connection")
            self.get_raspberry_status(raspberry_id)
            self.update_raspberry_display(raspberry_id)
            return
        if response.status_code != 200:
            self.rasp_output_lb.setText(f"Error during shutdown (status code: {response.status_code})")
            return
        self.rasp_output_lb.setText(response.json().get("msg", "Error during shutdown"))


    def shutdown_all_rpi(self):
        """
        shutdown all Raspberry Pi
        """
        text, ok = QInputDialog.getText(self, "Shutdown all Rasberry Pi", "Please confirm writing 'yes'")
        if not ok or text != "yes":
            return

        for raspberry_id in self.RASPBERRY_IP:
            self.shutdown(self, raspberry_id)


    def blink(self):
        """
        blink the power led
        """
        if self.current_raspberry_id not in self.RASPBERRY_IP:
            return
        self.rasp_output_lb.setText("Blink requested")
        try:
            response = requests.get(f"http://{self.RASPBERRY_IP[self.current_raspberry_id]}{cfg.SERVER_PORT}/blink",
                                    timeout=cfg.TIME_OUT)
        except requests.exceptions.ConnectionError:
            self.rasp_output_lb.setText(f"Failed to establish a connection")
            self.get_raspberry_status(self.current_raspberry_id)
            self.update_raspberry_dashboard(self.current_raspberry_id)
            self.update_raspberry_display(self.current_raspberry_id)
            return

        if response.status_code != 200:
            self.rasp_output_lb.setText("Error during blinking")
            return
        self.rasp_output_lb.setText(response.json().get("msg", "Error during blinking"))


    def get_raspberry_status(self, raspberry_id):
        """
        get Raspberry Pi status
        """

        try:
            if raspberry_id in self.RASPBERRY_IP:

                #r1 = ping(self.RASPBERRY_IP[raspberry_id])
                r1 = True

                # check if answer to ping
                if not r1:
                    r_dict = {"status": "not available (ping failed)"}
                else:
                    r = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/status",
                                     timeout=cfg.TIME_OUT)
                    if r.status_code == 200:
                        r_dict = r.json()
                    else:
                        r_dict = {"status": f"not available (status code: {r.status_code})"}
            else:
                r_dict = {"status": f"not available ({raspberry_id} not detected)"}
        except Exception:
            r_dict = {"status": "not reachable"}

        self.raspberry_info[raspberry_id]["status"] = dict(r_dict)

        return dict(r_dict)


    def status_update_pb_clicked(self):
        """
        ask status to current raspberry pi
        """

        if not self.current_raspberry_id:
            self.rasp_output_lb.setText("Select a Raspberry Pi from the list")
            return

        self.get_raspberry_status(self.current_raspberry_id)

        self.update_raspberry_dashboard(self.current_raspberry_id)

        self.update_raspberry_display(self.current_raspberry_id)


    def update_raspberry_display(self, raspberry_id):
        """
        update the Raspberry pi status in the list
        """

        if self.raspberry_info[raspberry_id]["status"]["status"] == "OK":
            color = "green"
            if self.raspberry_info[raspberry_id]["status"].get("video_recording", False):
                color = "orange"
            if self.raspberry_info[raspberry_id]["status"].get("video_streaming_active", False):
                color = "yellow"
        else:
            color = "red"

        for x in range(self.rasp_list.count()):
            if self.rasp_list.item(x).text() == raspberry_id:
                self.rasp_list.item(x).setIcon(QIcon(f"{color}.png"))


    def status_for_all_rpi(self):
        """
        ask status to all Raspberries Pi
        """

        '''
        if output:
            for rb in sorted(self.RASPBERRY_IP.keys()):
                print(rb)
                self.status_list[rb].setStyleSheet("")
        '''

        threads = []
        for raspberry_id in self.RASPBERRY_IP:
            threads.append(threading.Thread(target=self.get_raspberry_status, args=(raspberry_id,)))
            threads[-1].start()
        for x in threads:
            x.join()

        for raspberry_id in self.RASPBERRY_IP:
            self.update_raspberry_display(raspberry_id)


    def time_synchro_clicked(self):
        """
        Synchronize time on the current raspberry
        """
        self.time_synchro(self.current_raspberry_id)


    def time_synchro(self, raspberry_id):
        """
        Set date/time on Raspberry Pi
        """
        if raspberry_id not in self.RASPBERRY_IP:
            return

        date, hour = date_iso().split(" ")
        try:
            response = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/sync_time/{date}/{hour}")
        except requests.exceptions.ConnectionError:
            self.rasp_output_lb.setText(f"Failed to establish a connection")
            self.get_raspberry_status(raspberry_id)
            self.update_raspberry_display(raspberry_id)
            return

        if response.status_code != 200:
            self.rasp_output_lb.setText(f"Error during time synchronization (status code: {response.status_code})")
            return
        self.rasp_output_lb.setText(response.json().get("msg", "Error during time synchronization"))


    def time_synchro_all(self):
        """
        synchronize all Raspberries Pi
        """

        pool = ThreadPool()
        results = pool.map_async(self.time_synchro, list(self.RASPBERRY_IP.keys()))
        return_val = results.get()


    def take_picture_clicked(self):
        """
        ask Raspberry Pi to take a picture
        """

        self.take_picture(self.current_raspberry_id)


    def take_picture(self, raspberry_id):
        """
        ask Raspberry Pi to take a picture and display it
        """

        if raspberry_id not in self.RASPBERRY_IP:
            return
        if self.raspberry_info[raspberry_id]["status"]["status"] == "OK":     # and self.raspberry_status[raspberry_id]:

            self.rasp_output_lb.setText(f"Picture requested")

            width, height = self.raspberry_info[raspberry_id]['picture resolution'].split("x")
            data = {"width": width, "height": height,
                    "brightness": self.raspberry_info[raspberry_id]['picture brightness'],
                    "contrast": self.raspberry_info[raspberry_id]['picture contrast'],
                    "saturation": self.raspberry_info[raspberry_id]['picture saturation'],
                    "sharpness": self.raspberry_info[raspberry_id]['picture sharpness'],
                    "ISO": self.raspberry_info[raspberry_id]['picture iso'],
                    "rotation": self.raspberry_info[raspberry_id]['picture rotation'],
                    "hflip": self.raspberry_info[raspberry_id]['picture hflip'],
                    "vflip": self.raspberry_info[raspberry_id]['picture vflip'],
                    "timelapse": self.raspberry_info[raspberry_id]['time lapse wait'],
                    "timeout": self.raspberry_info[raspberry_id]['time lapse duration'],
                    "annotate": self.raspberry_info[raspberry_id]['picture annotation'],
                    }
            

            try:
                response = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/take_picture",
                                        data=data)
            except requests.exceptions.ConnectionError:
                self.rasp_output_lb.setText(f"Failed to establish a connection")
                self.get_raspberry_status(raspberry_id)
                self.update_raspberry_display(raspberry_id)
                return

            if response.status_code != 200:
                self.rasp_output_lb.setText(f"Error taking picture (status code: {response.status_code})")
                return

            if response.json().get("error", True):
                self.rasp_output_lb.setText(response.json().get("msg", "Undefined error"))
                return

            # time lapse
            if self.raspberry_info[raspberry_id]['time lapse wait'] and self.raspberry_info[raspberry_id]['time lapse duration']:
                self.rasp_output_lb.setText(response.json().get("msg", "Undefined error"))
                return

            try:
                response2 = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/static/live.jpg", stream=True)
            except Exception:
                self.rasp_output_lb.setText(f"Error contacting the Raspberry Pi {raspberry_id}")
                return
            if response2.status_code != 200:
                self.rasp_output_lb.setText(f"Error retrieving the picture. Server status code: {response.status_code}")
                return

            with open(f"live_{raspberry_id}.jpg", "wb") as f:
                response2.raw.decode_content = True
                shutil.copyfileobj(response2.raw, f)

            self.picture_lb.setPixmap(QPixmap(f"live_{raspberry_id}.jpg").scaled(self.picture_lb.size(), Qt.KeepAspectRatio))
            self.rasp_output_lb.setText(f"Picture taken")


    def stop_time_lapse_clicked(self):
        """
        Stop the time lapse
        """

        self.stop_time_lapse(self.current_raspberry_id)


    def stop_time_lapse(self, raspberry_id):
        """
        Stop the time lapse
        """
        if raspberry_id not in self.RASPBERRY_IP:
            return

        try:
            response = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/stop_time_lapse")
        except requests.exceptions.ConnectionError:
            self.rasp_output_lb.setText(f"Failed to establish a connection")
            self.get_raspberry_status(raspberry_id)
            self.update_raspberry_display(raspberry_id)
            return

        if response.status_code != 200:
            self.rasp_output_lb.setText(f"Error trying to stop time lapse (status code: {response.status_code})")
            return
        self.rasp_output_lb.setText(response.json().get("msg", "Error during stopping time lapse"))



    def start_video_recording_clicked(self):

        self.start_video_recording(self.current_raspberry_id)


    def start_video_recording(self, raspberry_id):
        """
        start video recording with selected parameters
        """

        if raspberry_id in self.RASPBERRY_IP and self.raspberry_info[raspberry_id]["status"]["status"] == "OK":
            try:
                width, height = self.raspberry_info[raspberry_id]["video mode"].split("x")

                data = {"duration": self.raspberry_info[raspberry_id]["video duration"],
                        "width": width,
                        "height": height,
                        "prefix":  "",
                        "fps": self.raspberry_info[raspberry_id]["FPS"],
                        "quality": self.raspberry_info[raspberry_id]["video quality"],
                }

                self.rasp_output_lb.setText("start video recording requested")
                response = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/start_video", data=data)
                if response.status_code == 200 and response.json().get("msg", "") == "Video recording":
                    self.rasp_output_lb.setText(f"Video recording active")
                else:
                    self.rasp_output_lb.setText(response.json().get("msg", ""))

            except requests.exceptions.ConnectionError:
                self.rasp_output_lb.setText("Video not recording")

            except Exception:
                self.rasp_output_lb.setText("Video not recording")

            self.get_raspberry_status(raspberry_id)
            self.update_raspberry_dashboard(raspberry_id)


    def stop_video_recording_clicked(self):
        self.stop_video_recording(self.current_raspberry_id)


    def stop_video_recording(self, raspberry_id):
        """
        stop video recording
        """
        if raspberry_id not in self.RASPBERRY_IP:
            return

        self.rasp_output_lb.setText("stop video recording requested")
        try:
            response = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/stop_video")
            if response.status_code == 200 and response.json().get("msg", "") == "video recording stopped":
                self.rasp_output_lb.setText("Video recording stopped")
            else:
                self.rasp_output_lb.setText(response.json().get("msg", ""))

        except Exception:
            pass

        self.get_raspberry_status(raspberry_id)


    def delete_all_video(self, rb):
        """
        delete all video from Raspberry Pi
        """
        text, ok = QInputDialog.getText(self, f"Delete all video from the Raspberry Pi {rb}", "Confirm writing 'yes'")
        if not ok or text != "yes":
            return
        try:
            self.rasp_output_lb.setText("deletion of all video requested")

            r = requests.get(f"http://{self.RASPBERRY_IP[rb]}{cfg.SERVER_PORT}/delete_all_video")
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

    '''
    def get_log(self):

        if self.current_raspberry_id in self.RASPBERRY_IP and self.raspberry_info[raspberry_id]["status"]["status"] == "OK":
            try:
                r = requests.get(f"http://{self.RASPBERRY_IP[self.current_raspberry_id]}{cfg.SERVER_PORT}/get_log")
                self.rb_msg(self.current_raspberry_id, r.text)
            except Exception:
                self.rb_msg(self.current_raspberry_id, "Error")
    '''

    '''
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
                r = os.system(f"scp server.py pi@{self.RASPBERRY_IP[rb]}{cfg.CLIENT_PROJECT_DIRECTORY}")
                if not r:
                    self.rb_msg(rb, "Server updated")
                else:
                    self.rb_msg(rb, "<b>Error during server update</b>")
    '''

    '''
    def download_videos_list(self, args):

        raspberry_id, videos_list = args
        output = ""
        for video_file_name in sorted(videos_list):
            if not pathlib.Path(cfg.VIDEO_ARCHIVE + "/" + video_file_name).is_file():

                logging.info(f"Downloading  {video_file_name} from {raspberry_id}")

                with requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/static/video_archive/{video_file_name}", stream=True) as r:
                        with open(cfg.VIDEO_ARCHIVE + "/" + video_file_name, 'wb') as file_out:
                            shutil.copyfileobj(r.raw, file_out)

                logging.info(f"{video_file_name} downloaded from {raspberry_id}")
                output += f"{video_file_name} downloaded\n"

        if output == "":
            return ["No video to download"]
        else:
            return output
    '''

    def download_videos(self, raspberry_id, download_dir=""):
        """
        download all video from Raspberry Pi
        """

        def thread_finished(output):
            self.rasp_output_lb.setText("Videos downloaded")
            self.my_thread1.quit


        if download_dir == "":
            download_dir = cfg.VIDEO_ARCHIVE

        if not pathlib.Path(download_dir).is_dir():
            QMessageBox.critical(None, "Raspberry Pi coordinator",
                                 f"Destination not found!<br>{cfg.VIDEO_ARCHIVE}<br><br>Choose another directory",
                                 QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)

            new_download_dir = QFileDialog().getExistingDirectory(self, "Choose a directory to download videos",
                                                                  str(pathlib.Path.home()),
                                                                  options=QFileDialog.ShowDirsOnly)
            if new_download_dir:
                download_dir = new_download_dir
            else:
                return

        if raspberry_id in self.RASPBERRY_IP and self.raspberry_info[raspberry_id]["status"]["status"] == "OK":

            try:
                r = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/video_list")
                if r.status_code == 200:
                    self.rb_msg(raspberry_id, "download: list received (* for files not in archive)")
                    r2 = eval(r.text)
                    if "video_list" in r2:
                        self.rb_msg(raspberry_id, "Downloading videos\n")
                        '''
                        pool = ThreadPool()
                        r = pool.map_async(self.download_videos_list, ([[raspberry_id, r2["video_list"]]]), callback=self.download_videos_finished)
                        '''

                        self.my_thread1 = QThread(parent=self)
                        self.my_thread1.start()
                        self.my_worker1 = self.Download_videos_worker(self.RASPBERRY_IP)
                        self.my_worker1.moveToThread(self.my_thread1)

                        self.my_worker1.start.connect(self.my_worker1.run) #  <---- Like this instead
                        self.my_worker1.finished.connect(thread_finished)
                        self.my_worker1.start.emit(raspberry_id, r2["video_list"])


            except Exception:
                raise



    def read_process_stdout(self, rb):

        out = self.download_process[rb].readAllStandardOutput()
        self.rb_msg(rb, bytes(out).decode("utf-8").strip())


    def process_error(self, process_error, rb):
        logging.info(f"process error: {process_error}")
        logging.info(f"process state: {self.download_process[rb].state()}")
        self.rb_msg(rb, f"Error downloading video.\nProcess error: {process_error}  Process state: {self.download_process[rb].state()}")
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


        for raspberry_id in sorted(self.RASPBERRY_IP.keys()):
            if raspberry_id in self.RASPBERRY_IP and self.raspberry_info[raspberry_id]["status"]["status"] == "OK":
                self.download_all_video(raspberry_id, download_dir)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("Raspberry Pi coordinator")
    video_recording_control = Video_recording_control()

    video_recording_control.show()
    sys.exit(app.exec_())
