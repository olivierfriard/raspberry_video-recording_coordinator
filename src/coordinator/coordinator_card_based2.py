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

security_key = "abc123"

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
    """
    get IP of wireless connection
    """

    for ifname in os.listdir('/sys/class/net/'):  # https://stackoverflow.com/questions/3837069/how-to-get-network-interface-card-names-in-python/58191277
        if ifname.startswith("wl"):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
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


def md5sum(file_path):
    """
    Return the MD5 sum of the file content
    """
    md5_hash = hashlib.md5()

    with open("test.txt", "rb") as a_file:
        content = a_file.read()

    md5_hash.update(content)

    digest = md5_hash.hexdigest()

    return digest


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
                        with open(cfg.VIDEO_ARCHIVE + "/" + video_file_name, "wb") as file_out:
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
        self.reboot_pb.clicked.connect(self.reboot_clicked)
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
        self.configure_video_recording_pb.clicked.connect(self.schedule_video_recording_clicked)
        self.view_video_recording_schedule_pb.clicked.connect(self.view_video_recording_schedule_clicked)
        self.delete_video_recording_schedule_pb.clicked.connect(self.delete_video_recording_schedule_clicked)

        self.video_mode_cb.currentIndexChanged.connect(self.video_mode_changed)
        self.video_duration_sb.valueChanged.connect(self.video_duration_changed)
        self.video_quality_sb.valueChanged.connect(self.video_quality_changed)
        self.video_fps_sb.valueChanged.connect(self.video_fps_changed)

        self.video_brightness_sb.valueChanged.connect(self.video_brightness_changed)
        self.video_contrast_sb.valueChanged.connect(self.video_contrast_changed)
        self.video_sharpness_sb.valueChanged.connect(self.video_sharpness_changed)
        self.video_saturation_sb.valueChanged.connect(self.video_saturation_changed)
        self.video_iso_sb.valueChanged.connect(self.video_iso_changed)
        self.video_rotation_sb.valueChanged.connect(self.video_rotation_changed)
        self.video_hflip_cb.clicked.connect(self.video_hflip_changed)
        self.video_vflip_cb.clicked.connect(self.video_vflip_changed)


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

        # commands for all Raspberry Pi
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


    def video_brightness_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["video brightness"] = self.video_brightness_sb.value()
    def video_contrast_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["video contrast"] = self.video_contrast_sb.value()
    def video_sharpness_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["video sharpness"] = self.video_sharpness_sb.value()
    def video_saturation_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["video saturation"] = self.video_saturation_sb.value()
    def video_iso_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["video iso"] = self.video_iso_sb.value()
    def video_rotation_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["video rotation"] = self.video_rotation_sb.value()
    def video_hflip_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["video hflip"] = self.video_hflip_cb.isChecked()
    def video_vflip_changed(self):
        if self.current_raspberry_id:
            self.raspberry_info[self.current_raspberry_id]["video vflip"] = self.video_vflip_cb.isChecked()


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



    def request(self, raspberry_id, route, data= {}, time_out=None):
        """
        wrapper for contacting Raspberry Pi using requests
        """

        if data:
            data_to_send =  {**{'key': security_key}, **data}
        else:
            data_to_send = {'key': security_key}
        return requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}{route}",
                            data=data_to_send,
                            timeout=time_out
                            )





    def video_streaming_clicked(self, action):
        """
        Start video streaming on the current raspberry
        """
        self.video_streaming(self.current_raspberry_id, action)


    def schedule_video_recording_clicked(self):
        """
        Schedule the video recording on the current Raspberry Pi
        """
        self.schedule_video_recording(self.current_raspberry_id)


    def schedule_video_recording(self, raspberry_id):
        """
        Schedule the video recording on the Raspberry Pi
        """

        if self.hours_le.text() == "":
            QMessageBox.information(None, "Raspberry Pi coordinator",
                                 f"Specify the hour(s) to start video recording",
                                 QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
            return

        if self.minutes_le.text() == "":
            QMessageBox.information(None, "Raspberry Pi coordinator",
                                 f"Specify the minutes(s) to start video recording",
                                 QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
            return

        if self.days_of_week_le.text() == "":
            QMessageBox.information(None, "Raspberry Pi coordinator",
                                 f"Specify the day(s) of the week to start video recording (0-6 or SUN-SAT)",
                                 QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
            return

        if self.days_of_month_le.text() == "":
            QMessageBox.information(None, "Raspberry Pi coordinator",
                                 f"Specify the day(s) of the month to start video recording (1-31)",
                                 QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
            return

        # check hours format
        hours = self.hours_le.text().replace(" ", "")
        if hours == "*":
            hours_str = "*"
        else:
            hours_splt = hours.split(",")
            try:
                int_hours_list = [int(x) for x in hours_splt]
                for x in int_hours_list:
                    if not (0 <= x < 24):
                        raise
            except Exception:
                QMessageBox.information(None, "Raspberry Pi coordinator",
                                    f"The hour(s) format is not correct. Example; 1,2,13,15 or *",
                                    QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
                return
            hours_str = ",".join([str(x) for x in int_hours_list])

        # check minutes format
        minutes = self.minutes_le.text().replace(" ", "")
        if minutes == "*":
            minutes_str = minutes
        else:
            minutes_splt = minutes.split(",")
            print(minutes_splt)
            try:
                int_minutes_list = [int(x) for x in minutes_splt]
                for x in int_minutes_list:
                    if not (0 <= x < 60):
                        raise
            except Exception:
                QMessageBox.information(None, "Raspberry Pi coordinator",
                                    f"The minutes(s) format is not correct. Example; 1,2,13,15 or *",
                                    QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
                return

            minutes_str = ",".join([str(x) for x in int_minutes_list])

        # check days of month format
        dom = self.days_of_month_le.text().replace(" ", "")
        if dom == "*":
            dom_str = dom
        else:
            dom_splt = dom.split(",")
            try:
                int_dom_list = [int(x) for x in dom_splt]
                for x in int_dom_list:
                    if not (1 <= x <= 31):
                        raise
            except Exception:
                QMessageBox.information(None, "Raspberry Pi coordinator",
                                    f"The day(s) of month format is not correct. Example; 1,2,13,15 or *",
                                    QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
                return
            dom_str = ",".join([str(x) for x in int_dom_list])

        # check month format
        month = self.months_le.text().replace(" ", "")
        if month == "*":
            month_str = month
        else:
            month_splt = month.split(",")
            print(month_splt)
            try:
                int_month_list = [int(x) for x in month_splt]
                for x in int_month_list:
                    if not (1 <= x <= 12):
                        raise
            except Exception:
                QMessageBox.information(None, "Raspberry Pi coordinator",
                                    f"The month format is not correct. Example; 1,2,12 or *",
                                    QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
                return
            month_str = ",".join([str(x) for x in int_month_list])

        # check days(s) of week format
        dow = self.days_of_week_le.text().replace(" ", "")
        if dow == "*":
            dow_str = dow
        else:
            dow_splt = dow.split(",")
            try:
                int_dow_splt = [int(x) for x in dow_splt]
            except Exception:
                try:
                    for x in dow_splt:
                        if x.upper() not in ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]:
                            raise
                    int_dow_splt = dow_splt
                except Exception:
                    QMessageBox.information(None, "Raspberry Pi coordinator",
                                    f"The days(s) of week format is not correct. Example; 0,1,2 or SUN,MON,TUE",
                                    QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)

            dow_str = ",".join([str(x) for x in int_dow_splt])

        crontab_event = f"{minutes_str} {hours_str} {dom_str} {month_str} {dow_str}"


        width, height = self.raspberry_info[raspberry_id]["video mode"].split("x")


        data = {"crontab": crontab_event,
                "duration": self.raspberry_info[raspberry_id]["video duration"],
                "width": width,
                "height": height,
                "prefix":  "",
                "fps": self.raspberry_info[raspberry_id]["FPS"],
                "quality": self.raspberry_info[raspberry_id]["video quality"],
                "brightness": self.raspberry_info[raspberry_id]['video brightness'],
                "contrast": self.raspberry_info[raspberry_id]['video contrast'],
                "saturation": self.raspberry_info[raspberry_id]['video saturation'],
                "sharpness": self.raspberry_info[raspberry_id]['video sharpness'],
                "ISO": self.raspberry_info[raspberry_id]['video iso'],
                "rotation": self.raspberry_info[raspberry_id]['video rotation'],
                "hflip": self.raspberry_info[raspberry_id]['video hflip'],
                "vflip": self.raspberry_info[raspberry_id]['video vflip'],
        }

        try:
            response = self.request(raspberry_id, f"/schedule_video_recording",
                                    data=data)
        except requests.exceptions.ConnectionError:
            self.rasp_output_lb.setText(f"Failed to establish a connection")
            self.get_raspberry_status(raspberry_id)
            self.update_raspberry_display(raspberry_id)
            return

        if response.status_code != 200:
            self.rasp_output_lb.setText(f"Error during the video recording scheduling (status code: {response.status_code})")
            return
        self.rasp_output_lb.setText(response.json().get("msg", "Error during video recording scheduling"))


    def view_video_recording_schedule_clicked(self):
        """
        view schedule on current raspberry
        """
        self.view_video_recording_schedule(self.current_raspberry_id)


    def view_video_recording_schedule(self, raspberry_id):
        """
        view schedule on Raspberry Pi
        """
        try:
            response = self.request(raspberry_id, f"/view_video_recording_schedule")
        except requests.exceptions.ConnectionError:
            self.rasp_output_lb.setText(f"Failed to establish a connection")
            self.get_raspberry_status(raspberry_id)
            self.update_raspberry_display(raspberry_id)
            return

        if response.status_code != 200:
            self.rasp_output_lb.setText(f"Error during view of the video recording scheduling (status code: {response.status_code})")
            return

        QMessageBox.information(None, "Raspberry Pi coordinator",
                                      response.json().get("msg", "Error during view of the video recording scheduling"),
                                      QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)

        #self.rasp_output_lb.setText(response.json().get("msg", "Error during view of the video recording scheduling"))





    def delete_video_recording_schedule_clicked(self):
        self.delete_video_recording_schedule(self.current_raspberry_id)


    def delete_video_recording_schedule(self, raspberry_id):
        """
        delete all video recording scheduling
        """

        try:
            response = self.request(raspberry_id, f"/delete_video_recording_schedule")
        except requests.exceptions.ConnectionError:
            self.rasp_output_lb.setText(f"Failed to establish a connection")
            self.get_raspberry_status(raspberry_id)
            self.update_raspberry_display(raspberry_id)
            return

        if response.status_code != 200:
            self.rasp_output_lb.setText(f"Error during deletion of the video recording scheduling (status code: {response.status_code})")
            return
        self.rasp_output_lb.setText(response.json().get("msg", "Error during deletion of the video recording scheduling"))



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
            response = requests.get(f"http://{ip_address}{cfg.SERVER_PORT}/status",
                                    data={'key': security_key},
                                    timeout=cfg.TIME_OUT)
        except requests.exceptions.ConnectionError:
            logging.debug(f"{ip_address}: failed to establish a connection")
            return

        if response.status_code != 200:
            logging.debug(f"{ip_address}: server status code != 200: {response.status_code}")
            return

        logging.info(f"{ip_address}: server available")

        # check hostname
        raspberry_id = response.json().get("hostname", "")
        if not raspberry_id:
            logging.info(f"{ip_address}: hostname not found")
            return

        self.RASPBERRY_IP[raspberry_id] = ip_address

        # set raspberry time date
        self.time_synchro(raspberry_id)



    def scan_raspberries(self, ip_base_address, interval):
        """
        Scan network {ip_base_address} for Raspberry Pi device
        """

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
        scan all networks defined in IP_RANGES
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
                try:
                    response = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/video_streaming/start",
                                            data=data)
                except requests.exceptions.ConnectionError:
                    return

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



    def go_left(self):
        pass


    def go_right(self):
        pass


    def video_list(self, raspberry_id):
        """
        request a list of video to Raspberry Pi
        """

        try:
            response = self.request(raspberry_id, "/video_list")
        except requests.exceptions.ConnectionError:
            self.rasp_output_lb.setText(f"Failed to establish a connection")
            self.get_raspberry_status(raspberry_id)
            self.update_raspberry_display(raspberry_id)
            return

        if response.status_code != 200:
            self.rasp_output_lb.setText(f"Error requiring the list of video (status code: {response.status_code})")
            return
        if "video_list" not in response.json():
            self.rasp_output_lb.setText(f"Error requiring the list of video")
            return
        #self.rasp_output_lb.setText(f"List of video received ({len(response.json()["video_list"])} video)")

        return list(response.json()["video_list"])


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
        self.server_version_lb.setText(self.raspberry_info[raspberry_id]["status"].get("server_version", "Not available"))
        self.wifi_essid_lb.setText(self.raspberry_info[raspberry_id]["status"].get("wifi_essid", "Not available"))
        self.free_sd_space_lb.setText(self.raspberry_info[raspberry_id]["status"].get("free disk space", "Not available"))
        self.camera_detected_lb.setText("Yes" if self.raspberry_info[raspberry_id]["status"].get("camera detected", "") else "No")
        self.uptime_lb.setText(self.raspberry_info[raspberry_id]["status"].get("uptime", ""))
        self.ip_address_lb.setText(self.raspberry_info[raspberry_id]["status"].get("IP_address", "Not detected"))

        self.video_recording_active_lb.setText("Yes" if self.raspberry_info[raspberry_id]["status"].get("video_recording", False) else "No")

        self.video_streaming_active_lb.setText("Yes" if self.raspberry_info[raspberry_id]["status"].get("video_streaming_active", False) else "No")

        self.time_lapse_active_lb.setText("Yes" if self.raspberry_info[raspberry_id]["status"].get("time_lapse_active", False) else "No")


    '''
    def send_command(self, rb):
        """
        send command to a raspberry and retrieve output
        """
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
    '''

    '''
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
    '''

    def reboot_clicked(self):
        """
        Reboot the current Raspberry Pi
        """
        if self.current_raspberry_id in self.RASPBERRY_IP and self.raspberry_status[self.current_raspberry_id]:
            text, ok = QInputDialog.getText(self, f"Reboot the Raspberry Pi {self.current_raspberry_id}", "Please confirm writing 'yes'")
            if not ok or text != "yes":
                return

        self.reboot(self.current_raspberry_id)


    def reboot(self, raspberry_id):
        """
        send reboot signal to Raspberry Pi
        """
        if raspberry_id not in self.RASPBERRY_IP:
            return

        try:
            response = self.request(raspberry_id, "/reboot")
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


    def time_synchro_clicked(self):
        """
        Set the date/time on the current raspberry
        """
        self.time_synchro(self.current_raspberry_id)


    def time_synchro(self, raspberry_id):
        """
        Set the date/time on Raspberry Pi
        """
        if raspberry_id not in self.RASPBERRY_IP:
            return

        date, hour = date_iso().split(" ")
        try:
            response = self.request(raspberry_id, f"/sync_time/{date}/{hour}")
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
        Set the date/time on all Raspberry Pi
        """

        pool = ThreadPool()
        results = pool.map_async(self.time_synchro, list(self.RASPBERRY_IP.keys()))
        return_val = results.get()



    def shutdown_clicked(self):
        """
        Shutdown the current Raspberry Pi
        """
        if self.current_raspberry_id in self.RASPBERRY_IP and self.raspberry_status[self.current_raspberry_id]:
            text, ok = QInputDialog.getText(self, f"Shutdown Rasberry Pi {self.current_raspberry_id}", "Please confirm writing 'yes'")
            if not ok or text != "yes":
                return

        self.shutdown(self.current_raspberry_id)


    def shutdown(self, raspberry_id):
        """
        send shutdown signal to Raspberry pi
        """
        if raspberry_id not in self.RASPBERRY_IP:
            return
        self.rasp_output_lb.setText("Shutdown requested")
        try:
            response = self.request(raspberry_id, "/shutdown")
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
        text, ok = QInputDialog.getText(self, "Shutdown all Raspberry Pi", "Please confirm writing 'yes'")
        if not ok or text != "yes":
            return

        for raspberry_id in self.RASPBERRY_IP:
            self.shutdown(self, raspberry_id)


    def blink(self):
        """
        blink the power led of the current Raspberry Pi
        """
        if self.current_raspberry_id not in self.RASPBERRY_IP:
            return
        self.rasp_output_lb.setText("Blink requested")
        try:
            response = self.request(self.current_raspberry_id, "/blink", time_out=cfg.TIME_OUT)
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

        if raspberry_id not in self.RASPBERRY_IP:
            return

        #r1 = ping(self.RASPBERRY_IP[raspberry_id])
        r1 = True

        # check if answer to ping
        if not r1:
            self.raspberry_info[raspberry_id]["status"] = {"status": "not available (ping failed)"}
            return {"status": "not available (ping failed)"}
        else:
            try:
                response = self.request(raspberry_id, "/status", time_out=cfg.TIME_OUT)
            except requests.exceptions.ConnectionError:
                self.raspberry_info[raspberry_id]["status"] = {"status": "not reachable"}
                return {"status": "not reachable"}
            if response.status_code != 200:
                self.raspberry_info[raspberry_id]["status"] = {"status": f"not available (status code: {response.status_code})"}
                return {"status": f"not available (status code: {response.status_code})"}

            self.raspberry_info[raspberry_id]["status"] = response.json()
            return response.json()


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
            data = {"key": security_key,
                    "width": width, "height": height,
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
                self.rasp_output_lb.setText(f'{response.json().get("msg", "Undefined error")}  returncode: {response.json().get("error", "-")}')
                return

            # time lapse
            if self.raspberry_info[raspberry_id]['time lapse wait'] and self.raspberry_info[raspberry_id]['time lapse duration']:
                self.rasp_output_lb.setText(response.json().get("msg", "Undefined error"))
                return

            try:
                response2 = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/static/live.jpg",
                                         stream=True)
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
            response = self.request(raspberry_id, "/stop_time_lapse")
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

        if raspberry_id not in self.RASPBERRY_IP:
            return

        width, height = self.raspberry_info[raspberry_id]["video mode"].split("x")
        data = {"key": security_key,
                "duration": self.raspberry_info[raspberry_id]["video duration"],
                "width": width,
                "height": height,
                "prefix":  "",
                "fps": self.raspberry_info[raspberry_id]["FPS"],
                "quality": self.raspberry_info[raspberry_id]["video quality"],
        }

        self.rasp_output_lb.setText("start video recording requested")
        try:
            response = requests.get(f"http://{self.RASPBERRY_IP[raspberry_id]}{cfg.SERVER_PORT}/start_video",
                                    data=data)
        except requests.exceptions.ConnectionError:
            self.rasp_output_lb.setText(f"Failed to establish a connection")
            self.get_raspberry_status(raspberry_id)
            self.update_raspberry_display(raspberry_id)
            return

        if response.status_code != 200:
            self.rasp_output_lb.setText(f"Failed to start recording video (status code: {response.status_code})")
            return

        self.rasp_output_lb.setText(response.json().get("msg", "Error recording video"))

        self.get_raspberry_status(raspberry_id)
        self.update_raspberry_dashboard(raspberry_id)


    def stop_video_recording_clicked(self):
        """
        Stop current video recording
        """
        self.stop_video_recording(self.current_raspberry_id)


    def stop_video_recording(self, raspberry_id):
        """
        stop video recording
        """
        if raspberry_id not in self.RASPBERRY_IP:
            return

        self.rasp_output_lb.setText("stop video recording requested")
        try:
            response = self.request(raspberry_id, "/stop_video")
        except requests.exceptions.ConnectionError:
            self.rasp_output_lb.setText(f"Failed to establish a connection")
            self.get_raspberry_status(raspberry_id)
            self.update_raspberry_display(raspberry_id)
            return

        if response.status_code != 200:
            self.rasp_output_lb.setText(f"Failed to stop recording video (status code: {response.status_code})")
            return
        self.rasp_output_lb.setText(response.json().get("msg", "Failed to stop recording video"))

        self.get_raspberry_status(raspberry_id)
        self.update_raspberry_dashboard(raspberry_id)


    def delete_all_video(self, raspberry_id):
        """
        delete all video from Raspberry Pi
        """
        text, ok = QInputDialog.getText(self, f"Delete all video on the Raspberry Pi {raspberry_id}", "Confirm writing 'yes'")
        if not ok or text != "yes":
            return
        self.rasp_output_lb.setText("Deletion of all video requested")
        try:
            response = self.request(raspberry_id, "/delete_all_video")
        except requests.exceptions.ConnectionError:
            self.rasp_output_lb.setText(f"Failed to establish a connection")
            self.get_raspberry_status(raspberry_id)
            self.update_raspberry_display(raspberry_id)
            return
        if response.status_code != 200:
            self.rasp_output_lb.setText(f"Error deleting the video (status code: {response.status_code})")
            return

        self.rasp_output_lb.setText(response.json().get("msg", "Error during delteing the video"))

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

        if raspberry_id not in self.RASPBERRY_IP:
            return

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

        video_list = self.video_list(raspberry_id)

        self.my_thread1 = QThread(parent=self)
        self.my_thread1.start()
        self.my_worker1 = self.Download_videos_worker(self.RASPBERRY_IP)
        self.my_worker1.moveToThread(self.my_thread1)

        self.my_worker1.start.connect(self.my_worker1.run) #  <---- Like this instead
        self.my_worker1.finished.connect(thread_finished)
        self.my_worker1.start.emit(raspberry_id, video_list)


    def download_all_video_from_all(self):
        """
        download all video from all Raspberry Pi
        """
        text, ok = QInputDialog.getText(self, "Download video from all Raspberry Pi", "Please confirm writing 'yes'")
        if not ok or text != "yes":
            return

        if not pathlib.Path(cfg.VIDEO_ARCHIVE).is_dir():
            QMessageBox.critical(None, "Raspberry Pi coordinator",
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
            if self.raspberry_info[raspberry_id]["status"]["status"] == "OK":
                self.download_all_video(raspberry_id, download_dir)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("Raspberry Pi coordinator")
    video_recording_control = Video_recording_control()

    video_recording_control.show()
    sys.exit(app.exec_())
