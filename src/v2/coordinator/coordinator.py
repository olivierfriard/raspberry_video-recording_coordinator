"""
Raspberry Pi coordinator (via TCP/IP)

https://www.raspberrypi.com/documentation/accessories/camera.html#common-command-line-options

TODO:

* scan network with QThread

"""

__version__ = "21"
__version_date__ = "2023-05-16"

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QHBoxLayout,
    QSizePolicy,
    QMessageBox,
    QFileDialog,
    QInputDialog,
    QListWidgetItem,
)
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import QTimer, Qt, QUrl, QSettings
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtMultimediaWidgets import (
    QVideoWidget,
)  #  sudo apt install libqt5multimedia5-plugins

# from qt_material import apply_stylesheet

import os
import time
import sys
import pathlib as pl
import datetime
import subprocess
from functools import partial
import urllib3
import base64


import requests
import threading
import logging
import socket

import struct
from http import HTTPStatus

from multiprocessing.pool import ThreadPool
import platform

import argparse

import video_recording
import time_lapse
import output_window
import connections

from coordinator_ui import Ui_MainWindow

urllib3.disable_warnings()

try:
    import config_coordinator_local as cfg
except Exception:
    print("file config_coordinator_local.py not found")
    try:
        import config_coordinator as cfg
    except Exception:
        print("file config_coordinator.py not found")
        sys.exit()

logging.basicConfig(
    filename="coordinator.log",
    filemode="a",
    format="%(asctime)s, %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)


def date_iso():
    """
    return current date in ISO 8601 format
    """
    return datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", " ")


'''
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
'''


def ping(host):
    """
    Returns True if host (str) responds to a ping request.
    """

    command = ["ping", "-W", "1", "-c", "1", host]

    return subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


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


def get_wlan_ip_address() -> str:
    """
    get IP of wireless connection
    """

    if platform.system() == "Linux":
        import fcntl

        # https://stackoverflow.com/questions/3837069/how-to-get-network-interface-card-names-in-python/58191277
        for ifname in os.listdir("/sys/class/net/"):
            if ifname.startswith("wl"):
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    return socket.inet_ntoa(
                        fcntl.ioctl(
                            s.fileno(),
                            0x8915,
                            struct.pack("256s", ifname.encode("utf-8")[:15]),  # SIOCGIFADDR
                        )[20:24]
                    )
                except OSError:
                    return "not connected"

    if platform.system() == "Windows":
        result = subprocess.run("ipconfig", stdout=subprocess.PIPE, text=True).stdout.lower()
        scan = 0
        for i in result.split("\n"):
            if "wireless" in i:
                scan = 1
            if scan:
                if "ipv4" in i:
                    return i.split(":")[1].strip()

    return ""


def get_wifi_ssid() -> str:
    """
    get the SSID of the connected wifi network
    """
    if platform.system() == "Linux":
        process = subprocess.run(["iwgetid"], stdout=subprocess.PIPE)
        output = process.stdout.decode("utf-8").strip()
        if output:
            try:
                return output.split('"')[1]
            except Exception:
                return output
        else:
            return "not connected to wifi"

    if platform.system() == "Windows":
        # https://stackoverflow.com/questions/19575444/find-name-of-current-wifi-network-on-windows
        process = subprocess.run(["netsh", "wlan", "show", "interfaces"], stdout=subprocess.PIPE)
        output = process.stdout.decode("utf-8").strip().split("\n")
        for line in output:
            if "SSID" in line:
                return line.split(":")[1].strip()

    return ""


class RPI_coordinator(QMainWindow, Ui_MainWindow):
    raspberry_ip = {}
    raspberry_info = {}
    raspberry_saved_settings = {}

    def __init__(self, parent=None):
        super().__init__()

        self.current_raspberry_id = ""

        # super(MainWindow, self).__init__(parent)
        self.setupUi(self)

        self.showMaximized()
        # .showFullScreen()

        connections.connect(self)

        self.define_connections()

        self.setWindowTitle("Raspberry Pi coordinator")
        self.statusBar().showMessage(
            f"v. {__version__} - {__version_date__}    WIFI SSID: {get_wifi_ssid()} ({get_wlan_ip_address()})    IP address: {get_ip()}"
        )

        # self.setGeometry(0, 0, 1300, 768)

        if app.password is not None:
            self.security_key = app.password
        else:
            # read security key from environment
            try:
                self.security_key = os.environ["RPI_CONFIG_SECURITY_KEY"]
            except KeyError:
                self.security_key, ok = QInputDialog.getText(self, "Security key to access the Raspberry Pi", "Security key")
                if not ok:
                    sys.exit()

        self.scan_network()

        raspberry_saved_settings = self.read_settings()

        for raspberry_ip in self.raspberry_info:
            if raspberry_ip in raspberry_saved_settings:
                self.raspberry_info[raspberry_ip] = dict(raspberry_saved_settings[raspberry_ip])

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.get_status_for_all_rpi)
        self.status_timer.setInterval(cfg.REFRESH_INTERVAL * 1000)
        self.status_timer.start()

    def define_connections(self):
        """
        Define connections between widget and functions
        """
        self.pb_scan_network.clicked.connect(self.scan_network)
        self.rpi_list.itemClicked.connect(self.rpi_list_clicked)

        # menu
        self.actionExit.triggered.connect(self.close)

        # tools
        self.actionShow_IP_address.triggered.connect(self.show_ip_list)
        self.action_convert_h264_video_files.triggered.connect(self.convert_h264)

        self.rpi_tw.setCurrentIndex(0)
        self.rpi_tw.currentChanged.connect(self.rpi_tw_changed)

        # commands
        self.status_update_pb.clicked.connect(self.status_update_pb_clicked)
        self.time_synchro_pb.clicked.connect(self.time_synchro_clicked)
        self.get_log_pb.clicked.connect(self.get_log_clicked)
        self.blink_pb.clicked.connect(self.blink)
        self.pb_send_command.clicked.connect(self.send_command)
        self.reboot_pb.clicked.connect(self.reboot_clicked)
        self.shutdown_pb.clicked.connect(self.shutdown_clicked)

        # picture
        self.take_picture_pb.clicked.connect(self.take_picture_clicked)
        self.start_time_lapse_pb.clicked.connect(self.take_picture_clicked)
        self.stop_time_lapse_pb.clicked.connect(self.stop_time_lapse_clicked)

        self.picture_lb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.picture_lb.setAlignment(Qt.AlignCenter)
        self.picture_lb.setStyleSheet("QLabel {background-color: black;}")

        for resolution in cfg.PICTURE_RESOLUTIONS:
            self.picture_resolution_cb.addItem(resolution)
        self.picture_resolution_cb.setCurrentIndex(cfg.DEFAULT_PICTURE_RESOLUTION)

        self.cb_enable_picture_parameters.clicked.connect(self.enable_picture_parameters)

        self.configure_picture_pb.clicked.connect(self.schedule_time_lapse_clicked)
        self.view_picture_schedule_pb.clicked.connect(self.view_time_lapse_schedule_clicked)
        self.delete_picture_schedule_pb.clicked.connect(self.delete_time_lapse_schedule_clicked)

        self.download_live_pictures_pb.clicked.connect(self.download_live_pictures_clicked)
        self.download_pictures_pb.clicked.connect(self.download_timelapse_pictures_clicked)

        self.pb_delete_live_pictures.clicked.connect(self.delete_live_pictures_clicked)
        self.pb_delete_timelapse_pictures.clicked.connect(self.delete_timelapse_pictures_clicked)

        # video streaming
        self.pb_start_video_streaming.clicked.connect(partial(self.video_streaming_clicked, "start"))
        self.pb_stop_video_streaming.clicked.connect(partial(self.video_streaming_clicked, "stop"))

        self.streaming_wdg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.streaming_wdg.setAlignment(Qt.AlignCenter)

        # video recording
        self.start_video_recording_pb.clicked.connect(self.start_video_recording_clicked)
        self.stop_video_recording_pb.clicked.connect(self.stop_video_recording_clicked)

        self.configure_video_recording_pb.clicked.connect(self.schedule_video_recording_clicked)
        self.view_video_recording_schedule_pb.clicked.connect(self.view_video_recording_schedule_clicked)
        self.delete_video_recording_schedule_pb.clicked.connect(self.delete_video_recording_schedule_clicked)

        self.download_videos_pb.clicked.connect(self.download_videos_clicked)
        self.delete_videos_pb.clicked.connect(self.delete_videos_clicked)
        self.video_list_pb.clicked.connect(self.video_list_clicked)
        self.all_video_cb.clicked.connect(self.all_video_clicked)
        self.all_new_video_cb.clicked.connect(self.all_new_video_clicked)

        self.media_list = QMediaPlayer(None, QMediaPlayer.VideoSurface)
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
        self.get_status_all_pb.clicked.connect(self.get_status_for_all_rpi)
        self.time_synchro_all_pb.clicked.connect(self.time_synchro_all)
        self.shutdown_all_pb.clicked.connect(self.shutdown_all_rpi)

    def convert_h264(self):
        """
        convert all h264 files from a directory to mp4 with ffmpeg
        ffmpeg must be on the path
        """
        # select a directory to convert video
        directory_path = QFileDialog.getExistingDirectory(
            self,
            "Select Directory",
            str(pl.Path.home()),
            options=QFileDialog.ShowDirsOnly,
        )

        if not directory_path:
            return
        file_count: int = 0
        converted_file_count: int = 0
        new_converted_file_count: int = 0
        for file_path in pl.Path(directory_path).glob("*.h264"):
            file_count += 1
            if file_path.with_suffix(".mp4").is_file():
                converted_file_count += 1
                continue
            self.statusBar().showMessage(f"Converting {file_path} in MP4")
            app.processEvents()

            if platform.system() == "Linux":
                subprocess.run(["MP4Box", "-add", f"{file_path}", f'{file_path.with_suffix(".mp4")}'], stdout=subprocess.PIPE)
                new_converted_file_count += 1

            if platform.system() == "Windows":
                # download from https://gpac.io/downloads/
                subprocess.run(["mp4box.exe", "-add", f"{file_path}", f'{file_path.with_suffix(".mp4")}'], stdout=subprocess.PIPE)
                new_converted_file_count += 1

        if file_count and file_count == converted_file_count:
            self.message_box.setText(f"{file_count} file(s) already converted in MP4")
        if new_converted_file_count:
            self.message_box.setText(f"{new_converted_file_count} file(s) converted")

    def rpi_tw_changed(self, index):
        """
        raspberry Pi tablewidget change index
        """

        if index == cfg.VIDEO_REC_TAB_INDEX:  # video rec tab is activated
            # update list of videos
            self.video_list_clicked()
            # update crontab content
            self.view_video_recording_schedule_clicked()

        if index == cfg.TIME_LAPSE_TAB_INDEX:  # time lapse tab is activated
            # update crontab content
            self.view_time_lapse_schedule_clicked()

    def closeEvent(self, event):
        self.save_settings()

    def read_settings(self):
        iniFilePath = pl.Path.home() / pl.Path(".rpi_coordinator.conf")

        logging.debug(f"read config file from {iniFilePath}")

        settings = QSettings(str(iniFilePath), QSettings.IniFormat)

        return settings.value("rpi_config", {})

    def save_settings(self):
        iniFilePath = pl.Path.home() / pl.Path(".rpi_coordinator.conf")

        logging.debug(f"save config file in {iniFilePath}")

        settings = QSettings(str(iniFilePath), QSettings.IniFormat)

        settings.setValue("rpi_config", self.raspberry_info)

    '''
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
        hlayout_all_buttons.addWidget(QPushButton("Reboot all", clicked=self.reboot_all))
        hlayout_all_buttons.addWidget(QPushButton("Scan network", clicked=partial(self.scan_network, output=True)))

        return hlayout_all_buttons
    '''

    def rpi_list_clicked(self, item):
        """
        update the current Raspberry Pi
        """

        self.current_raspberry_id = item.text()
        self.get_raspberry_status(self.current_raspberry_id)
        self.raspberry_id_lb.setText(self.current_raspberry_id)
        self.update_raspberry_dashboard(self.current_raspberry_id)
        self.update_raspberry_display(self.current_raspberry_id)

        self.rpi_tw.setEnabled(True)

    def request(self, raspberry_id, route, type="GET", data={}, time_out=None):
        """
        wrapper for contacting Raspberry Pi using requests
        security key is sent
        """

        if data:
            data_to_send = {**{"key": self.security_key}, **data}
        else:
            data_to_send = {"key": self.security_key}

        try:
            if type == "GET":
                response = requests.get(
                    f"{cfg.PROTOCOL}{self.raspberry_ip[raspberry_id]}{cfg.SERVER_PORT}{route}",
                    data=data_to_send,
                    timeout=time_out,
                    verify=False,
                )
            if type == "POST":
                response = requests.post(
                    f"{cfg.PROTOCOL}{self.raspberry_ip[raspberry_id]}{cfg.SERVER_PORT}{route}",
                    data=data_to_send,
                    timeout=time_out,
                    verify=False,
                )

            return response
        except requests.exceptions.ConnectionError:
            self.rasp_output_lb.setText("Failed to establish a connection")
            # self.get_raspberry_status(raspberry_id)
            self.scan_network()
            # self.update_raspberry_display(raspberry_id)
            return None

    def verif(func):
        """
        check if a Raspberry Pi is selected
        """

        def wrapper(*args, **kwargs):
            if args[0].current_raspberry_id not in args[0].raspberry_ip:
                QMessageBox.information(
                    None,
                    "Raspberry Pi coordinator",
                    "Select a Raspberry Pi before",
                    QMessageBox.Ok | QMessageBox.Default,
                    QMessageBox.NoButton,
                )
            else:
                if len(args) == 3:  # function has 2 arguments (self and an other)
                    func(args[0], args[1])
                else:
                    func(args[0])  # function has only the self argument

        return wrapper

    @verif
    def video_streaming_clicked(self, action):
        """
        Start video streaming on the current raspberry
        """

        self.video_streaming(self.current_raspberry_id, action)

    def video_streaming(self, raspberry_id, action):
        """
        start/stop video streaming on client and show output
        """
        if action == "start":
            width, height = self.raspberry_info[raspberry_id]["video mode"].split("x")
            data = {"width": width, "height": height}

            response = self.request(raspberry_id, "/video_streaming/start", type="POST", data=data)
            if response is None:
                return

            if response.status_code != HTTPStatus.OK:
                self.rasp_output_lb.setText(f"Error during the video streaming (status code: {response.status_code})")
                return

            if self.rasp_output_lb.setText(response.json().get("error", "")):
                self.rasp_output_lb.setText("Error starting streaming")
                return
            self.rasp_output_lb.setText(response.json().get("msg", "Error starting streaming"))

            time.sleep(1)

            self.media_list.setMedia(
                # QMediaContent(QUrl(f"http://{self.raspberry_ip[raspberry_id]}:9090/stream/video.mjpeg")
                QMediaContent(
                    # QUrl(f"rtsp://{self.raspberry_ip[raspberry_id]}:8554/stream")
                    # QUrl(f"udp://{self.raspberry_ip[raspberry_id]}:6000")
                    QUrl(f"tcp://{self.raspberry_ip[raspberry_id]}:6000")
                )
            )

            os.system(f'ffplay tcp://{self.raspberry_ip[raspberry_id]}:6000 -vf "setpts=N/30" -fflags nobuffer -flags low_delay -framedrop')

            # self.media_list.play()
            self.rasp_output_lb.setText("Video streaming active")

            # self.media_list.play()

            # generate QR code
            """
            try:
                import qrcode
                img = qrcode.make(f"http://{self.raspberry_ip[raspberry_id]}:9090/stream/video.mjpeg")
                self.picture_lb[raspberry_id].setPixmap(QPixmap.fromImage(ImageQt(img)))   #.scaled(self.picture_lb[rb].size(), Qt.KeepAspectRatio))
            except:
                logging.info("qrcode module not installed")
            """

        if action == "stop":
            self.rasp_output_lb.setText("Video streaming stop requested")
            response = self.request(raspberry_id, "/video_streaming/stop")
            if response is None:
                return

            if response.status_code != HTTPStatus.OK:
                self.rasp_output_lb.setText(f"Error stopping the video streaming (status code: {response.status_code})")
                return

            self.rasp_output_lb.setText(response.json().get("msg", "Error stopping the video streaming"))

        self.get_raspberry_status(raspberry_id)
        self.update_raspberry_dashboard(raspberry_id)
        self.update_raspberry_display(raspberry_id)

    @verif
    def schedule_time_lapse_clicked(self):
        """
        Schedule picture taking on the current Raspberry Pi
        """

        time_lapse.schedule_time_lapse(self, self.current_raspberry_id)

    @verif
    def view_time_lapse_schedule_clicked(self):
        """
        view time lapse schedule on current Raspberry Pi
        """

        time_lapse.view_time_lapse_schedule(self, self.current_raspberry_id)

    @verif
    def delete_time_lapse_schedule_clicked(self):
        """
        Delete the time lapse schedule on Raspberry Pi
        """

        text, ok = QInputDialog.getText(
            self,
            "Delete the time lapse schedule on the Raspberry Pi",
            "Please confirm writing 'yes'",
        )
        if not ok or text != "yes":
            return

        time_lapse.delete_time_lapse_schedule(self, self.current_raspberry_id)

    @verif
    def schedule_video_recording_clicked(self):
        """
        Schedule the video recording on the current Raspberry Pi
        """

        video_recording.schedule_video_recording(self, self.current_raspberry_id)

    @verif
    def view_video_recording_schedule_clicked(self):
        """
        view schedule on current raspberry
        """

        video_recording.view_video_recording_schedule(self, self.current_raspberry_id)

    @verif
    def delete_video_recording_schedule_clicked(self):
        """
        Delete the video recording schedule on Raspberry Pi
        """

        text, ok = QInputDialog.getText(
            self,
            "Delete the video recording schedule on the Raspberry Pi",
            "Please confirm writing 'yes'",
        )
        if not ok or text != "yes":
            return

        video_recording.delete_video_recording_schedule(self, self.current_raspberry_id)

    @verif
    def download_videos_clicked(self):
        """
        Download videos from current Raspberry Pi
        """

        if not self.video_list_lw.count():
            QMessageBox.information(
                None,
                "Raspberry Pi coordinator",
                "No video to download",
                QMessageBox.Ok | QMessageBox.Default,
                QMessageBox.NoButton,
            )
            return

        for idx in range(self.video_list_lw.count()):
            if self.video_list_lw.item(idx).checkState() == Qt.Checked:
                break
        else:
            QMessageBox.information(
                None,
                "Raspberry Pi coordinator",
                "Select the video to download",
                QMessageBox.Ok | QMessageBox.Default,
                QMessageBox.NoButton,
            )
            return

        # select a directory to save video
        directory_path = str(
            QFileDialog.getExistingDirectory(
                self,
                "Select Directory",
                str(pl.Path.home()),
                options=QFileDialog.ShowDirsOnly,
            )
        )
        if not directory_path:
            return

        video_recording.download_videos(self, self.current_raspberry_id, download_dir=directory_path)

    @verif
    def download_timelapse_pictures_clicked(self):
        """
        Download time lapse pictures on current Raspberry Pi
        """

        # select a directory to save pictures
        directory_path = str(
            QFileDialog.getExistingDirectory(
                self,
                "Select a directory to save the time lapse pictures",
                str(pl.Path.home()),
                options=QFileDialog.ShowDirsOnly,
            )
        )

        time_lapse.download_timelapse_pictures(self, self.current_raspberry_id, directory_path)

    @verif
    def download_live_pictures_clicked(self):
        """
        Download live pictures on current Raspberry Pi
        """

        # select a directory to save the live pictures
        directory_path = str(
            QFileDialog.getExistingDirectory(
                self,
                "Select a directory to save the live pictures",
                str(pl.Path.home()),
                options=QFileDialog.ShowDirsOnly,
            )
        )

        time_lapse.download_live_pictures(self, self.current_raspberry_id, directory_path)

    @verif
    def delete_live_pictures_clicked(self):
        """
        delete all live pictures from current raspberry pi
        """
        text, ok = QInputDialog.getText(
            self,
            f"Delete all live pictures from Rasperry Pi {self.current_raspberry_id}",
            "Please confirm writing 'yes'",
        )
        if not ok or text != "yes":
            return

        time_lapse.delete_live_pictures(self, self.current_raspberry_id)

    @verif
    def delete_timelapse_pictures_clicked(self):
        """
        delete all time lapse pictures from current raspberry pi
        """
        text, ok = QInputDialog.getText(
            self,
            f"Delete all time lapse pictures from Rasperry Pi {self.current_raspberry_id}",
            "Please confirm writing 'yes'",
        )
        if not ok or text != "yes":
            return

        time_lapse.delete_timelapse_pictures(self, self.current_raspberry_id)

    '''
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

            new_download_dir = QFileDialog().getExistingDirectory(self,
                                                                  "Choose a directory to download video",
                                                                  str(pathlib.Path.home()),
                                                                  options=QFileDialog.ShowDirsOnly)

            if not new_download_dir:
                return
            else:
                download_dir = new_download_dir
        else:
            download_dir = cfg.VIDEO_ARCHIVE

        for raspberry_id in sorted(self.raspberry_ip.keys()):
            if self.raspberry_info[raspberry_id]["status"]["status"] == "OK":
                self.download_all_video(raspberry_id, download_dir)
    '''

    @verif
    def video_list_clicked(self):
        """
        Download list of recorded videos from current Raspberry Pi
        """

        video_list = video_recording.video_list(self, self.current_raspberry_id)

        self.video_list_lw.clear()
        for video_file_name, video_size in video_list:
            item = QListWidgetItem()
            item.setText(video_file_name)

            # check if file present in archive
            if not (pl.Path(cfg.VIDEO_ARCHIVE) / pl.Path(video_file_name)).is_file():
                font = QFont()
                font.setBold(True)
                item.setFont(font)

            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.video_list_lw.addItem(item)

    '''
    def video_list_from_all(self):
        """
        request a list of video to all raspberries
        """
        for rb in sorted(self.raspberry_ip.keys()):
            self.video_list(rb)
    '''

    def all_video_clicked(self):
        """
        Select or deselect all video
        """

        for idx in range(self.video_list_lw.count()):
            self.video_list_lw.item(idx).setCheckState(Qt.Checked if self.all_video_cb.isChecked() else Qt.Unchecked)
        self.all_new_video_cb.setCheckState(False)

    def all_new_video_clicked(self):
        """
        Select or deselect all new video
        """

        for idx in range(self.video_list_lw.count()):
            if not self.video_list_lw.item(idx).font().bold():
                continue
            self.video_list_lw.item(idx).setCheckState(Qt.Checked if self.all_new_video_cb.isChecked() else Qt.Unchecked)
        self.all_video_cb.setCheckState(False)

    @verif
    def delete_videos_clicked(self):
        """
        delete video from Raspberry Pi
        """

        if not self.video_list_lw.count():
            QMessageBox.information(
                None,
                "Raspberry Pi coordinator",
                "No video to delete",
                QMessageBox.Ok | QMessageBox.Default,
                QMessageBox.NoButton,
            )
            return

        for idx in range(self.video_list_lw.count()):
            if self.video_list_lw.item(idx).checkState() == Qt.Checked:
                break
        else:
            QMessageBox.information(
                None,
                "Raspberry Pi coordinator",
                "Select the video to delete",
                QMessageBox.Ok | QMessageBox.Default,
                QMessageBox.NoButton,
            )
            return

        text, ok = QInputDialog.getText(
            self,
            f"Delete videos on the Raspberry Pi {self.current_raspberry_id}",
            "Confirm writing 'yes'",
        )
        if not ok or text != "yes":
            return

        video_recording.delete_videos(self, self.current_raspberry_id)

    def populate_rpi_list(self):
        """
        Populate the list widget with the Raspberry Pi that were found
        """

        raspberry_info_updated = {}

        # self.raspberry_info = {}

        self.rpi_list.clear()
        for raspberry_id in sorted(self.raspberry_ip.keys()):
            item = QListWidgetItem(raspberry_id)
            self.rpi_list.addItem(item)
            # if one Raspberry Pi found select it
            raspberry_info_updated[raspberry_id] = dict(cfg.RPI_DEFAULTS)
            if len(self.raspberry_ip) == 1:
                self.rpi_list.setCurrentItem(item)

                # self.rpi_list_clicked(item)

        # remove rpi that does not respond
        rpi_id_to_remove = []
        for id in self.raspberry_info:
            if id not in raspberry_info_updated:
                rpi_id_to_remove.append(id)

        for id in rpi_id_to_remove:
            del self.raspberry_info[id]

        # add new discovered rpi
        for id in self.raspberry_ip:
            if id not in self.raspberry_info:
                self.raspberry_info[id] = dict(cfg.RPI_DEFAULTS)

    def connect(self, ip_address):
        """
        ask status to raspberry pi using protocol and port number
        """
        try:
            response = requests.get(
                f"{cfg.PROTOCOL}{ip_address}{cfg.SERVER_PORT}/status",
                data={"key": self.security_key},
                timeout=cfg.TIME_OUT,
                verify=False,
            )
        except requests.exceptions.ConnectionError:
            logging.debug(f"{ip_address}: failed to establish a connection")
            return

        if response.status_code != HTTPStatus.OK:
            logging.debug(f"{ip_address}: server status code != 200: {response.status_code}")
            return

        logging.info(f"{ip_address}: server available")

        # check hostname
        raspberry_id = response.json().get("hostname", "")
        if not raspberry_id:
            logging.info(f"{ip_address}: hostname not found")
            return

        self.raspberry_ip[raspberry_id] = ip_address

        # set raspberry time date
        self.time_synchro(raspberry_id)

    def scan_raspberries(self, ip_base_address, interval):
        """
        Scan network {ip_base_address} for Raspberry Pi device
        """

        ip_mask = ".".join(ip_base_address.split(".")[0:3])
        ip_list = [f"{ip_mask}.{x}" for x in range(interval[0], interval[1] + 1)]
        self.raspberry_ip = {}
        threads = []
        logging.info(f"Testing {ip_base_address} subnet")
        for ip in ip_list:
            threads.append(threading.Thread(target=self.connect, args=(ip,)))
            threads[-1].start()
        for x in threads:
            x.join()
        logging.info(f"testing subnet done: found {len(self.raspberry_ip)} clients: {self.raspberry_ip}")

        return 0

    def scan_network(self):
        """
        scan all networks defined in IP_RANGES
        populate the raspberry pi list
        ask status
        """
        self.message_box.setText("Scanning network...")
        app.processEvents()

        for ip_config in cfg.IP_RANGES:
            ip_base_address, interval = ip_config[0], ip_config[1]
            self.scan_raspberries(ip_base_address, interval)

            if len(self.raspberry_ip):
                self.message_box.setText(f"Scanning done: {len(self.raspberry_ip)} Raspberry Pi found on {ip_config[0]}")
            else:
                self.message_box.setText(f"Scanning done. No Raspberry Pi found were found on {ip_config[0]}")

        self.populate_rpi_list()

        self.get_status_for_all_rpi()

    def show_ip_list(self):
        """
        show the IP for all Raspberry Pi
        """

        self.results = output_window.ResultsWidget()
        self.results.setWindowTitle("IP addresses")
        self.results.ptText.clear()
        self.results.ptText.setReadOnly(True)
        self.results.ptText.appendHtml(" ".join([f"{self.raspberry_ip[x]}" for x in self.raspberry_ip]))
        self.results.show()

    def go_left(self):
        pass

    def go_right(self):
        pass

    def update_raspberry_dashboard(self, raspberry_id):
        """
        update the Raspberry Pi dashboard
        """

        self.datetime_lb.setText(self.raspberry_info[raspberry_id]["status"].get("server_datetime", "Not available"))
        self.cpu_temp_lb.setText(self.raspberry_info[raspberry_id]["status"].get("CPU temperature", "Not available"))
        self.status_lb.setText(self.raspberry_info[raspberry_id]["status"].get("status", "Not available"))
        self.server_version_lb.setText(self.raspberry_info[raspberry_id]["status"].get("server_version", "Not available"))
        self.wifi_essid_lb.setText(self.raspberry_info[raspberry_id]["status"].get("wifi_essid", "Not available"))
        self.free_sd_space_lb.setText(self.raspberry_info[raspberry_id]["status"].get("free disk space", "Not available"))
        self.camera_detected_lb.setText("Yes" if self.raspberry_info[raspberry_id]["status"].get("camera detected", "") else "No")
        self.uptime_lb.setText(self.raspberry_info[raspberry_id]["status"].get("uptime", ""))
        self.ip_address_lb.setText(self.raspberry_info[raspberry_id]["status"].get("IP_address", "Not detected"))

        self.video_recording_active_lb.setText("Yes" if self.raspberry_info[raspberry_id]["status"].get("video_recording", False) else "No")
        self.video_streaming_active_lb.setText(
            "Yes" if self.raspberry_info[raspberry_id]["status"].get("video_streaming_active", False) else "No"
        )
        self.time_lapse_active_lb.setText("Yes" if self.raspberry_info[raspberry_id]["status"].get("time_lapse_active", False) else "No")

        # buttons
        self.start_video_recording_pb.setEnabled(not self.raspberry_info[raspberry_id]["status"].get("video_recording", False))
        self.stop_video_recording_pb.setEnabled(self.raspberry_info[raspberry_id]["status"].get("video_recording", False))

        self.start_time_lapse_pb.setEnabled(not self.raspberry_info[raspberry_id]["status"].get("time_lapse_active", False))
        self.stop_time_lapse_pb.setEnabled(self.raspberry_info[raspberry_id]["status"].get("time_lapse_active", False))
        self.take_picture_pb.setEnabled(not self.raspberry_info[raspberry_id]["status"].get("time_lapse_active", False))

        self.pb_start_video_streaming.setEnabled(not self.raspberry_info[raspberry_id]["status"].get("video_streaming_active", False))
        self.pb_stop_video_streaming.setEnabled(self.raspberry_info[raspberry_id]["status"].get("video_streaming_active", False))

        # tabs icon
        if self.raspberry_info[raspberry_id]["status"].get("video_recording", False):
            self.rpi_tw.setTabIcon(cfg.VIDEO_REC_TAB_INDEX, QIcon("red.png"))
        else:
            self.rpi_tw.setTabIcon(cfg.VIDEO_REC_TAB_INDEX, QIcon())

        if self.raspberry_info[raspberry_id]["status"].get("video_streaming_active", False):
            self.rpi_tw.setTabIcon(cfg.VIDEO_STREAMING_TAB_INDEX, QIcon("red.png"))
        else:
            self.rpi_tw.setTabIcon(cfg.VIDEO_STREAMING_TAB_INDEX, QIcon())

        if self.raspberry_info[raspberry_id]["status"].get("time_lapse_active", False):
            self.rpi_tw.setTabIcon(cfg.TIME_LAPSE_TAB_INDEX, QIcon("red.png"))
        else:
            self.rpi_tw.setTabIcon(cfg.TIME_LAPSE_TAB_INDEX, QIcon())

        connections.update_rpi_settings(self, raspberry_id)

    '''
    def send_command(self, rb):
        """
        send command to a raspberry and retrieve output
        """
        if rb in self.raspberry_ip and self.raspberry_status[rb]:
            text, ok = QInputDialog.getText(self, "Send a command", "Command:")
            if not ok:
                return
            self.rb_msg(rb, f"sent command: {text}")
            try:
                cmd = base64.b64encode(text.encode('utf-8')).decode('utf-8')
                r = requests.get(f"http://{self.raspberry_ip[rb]}{cfg.SERVER_PORT}/command/{cmd}")
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

        for rb in sorted(self.raspberry_ip.keys()):
            if self.raspberry_status[rb]:
                self.rb_msg(rb, f"sent command: {text}")
                try:
                    cmd = base64.b64encode(text.encode('utf-8')).decode('utf-8')
                    r = requests.get(f"http://{self.raspberry_ip[rb]}{cfg.SERVER_PORT}/command/{cmd}")
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

    @verif
    def reboot_clicked(self):
        """
        Reboot the current Raspberry Pi
        """
        text, ok = QInputDialog.getText(
            self,
            f"Reboot the Raspberry Pi {self.current_raspberry_id}",
            "Please confirm writing 'yes'",
        )
        if not ok or text != "yes":
            return

        self.reboot(self.current_raspberry_id)

    def reboot(self, raspberry_id):
        """
        send reboot signal to Raspberry Pi
        """
        if raspberry_id not in self.raspberry_ip:
            return

        response = self.request(raspberry_id, "/reboot")
        if response is None:
            return

        if response.status_code != HTTPStatus.OK:
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

        for raspberry_id in self.raspberry_ip:
            self.reboot(raspberry_id, force_reboot=True)

    @verif
    def time_synchro_clicked(self):
        """
        Set the date/time on the current raspberry
        """
        self.time_synchro(self.current_raspberry_id)

    def time_synchro(self, raspberry_id):
        """
        Set the date/time on Raspberry Pi
        """
        if raspberry_id not in self.raspberry_ip:
            return

        date, hour = date_iso().split(" ")
        response = self.request(raspberry_id, f"/sync_time/{date}/{hour}")
        if response is None:
            return

        if response.status_code != HTTPStatus.OK:
            self.rasp_output_lb.setText(f"Error during time synchronization (status code: {response.status_code})")
            return
        self.rasp_output_lb.setText(response.json().get("msg", "Error during time synchronization"))

    def time_synchro_all(self):
        """
        Set the date/time on all Raspberry Pi
        """

        pool = ThreadPool()
        results = pool.map_async(self.time_synchro, list(self.raspberry_ip.keys()))
        _ = results.get()

    @verif
    def shutdown_clicked(self):
        """
        Shutdown the current Raspberry Pi
        """
        text, ok = QInputDialog.getText(
            self,
            f"Shutdown Rasberry Pi {self.current_raspberry_id}",
            "Please confirm writing 'yes'",
        )
        if not ok or text != "yes":
            return

        self.shutdown(self.current_raspberry_id)

    def shutdown(self, raspberry_id):
        """
        send shutdown signal to Raspberry pi
        """
        if raspberry_id not in self.raspberry_ip:
            return
        self.rasp_output_lb.setText("Shutdown requested")
        response = self.request(raspberry_id, "/shutdown")
        if response is None:
            return

        if response.status_code != HTTPStatus.OK:
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

        for raspberry_id in self.raspberry_ip:
            self.shutdown(self, raspberry_id)

    def blink(self):
        """
        blink the power led of the current Raspberry Pi
        """
        if self.current_raspberry_id not in self.raspberry_ip:
            return
        self.rasp_output_lb.setText("Blink requested")
        response = self.request(self.current_raspberry_id, "/blink", time_out=cfg.TIME_OUT)
        if response is None:
            return

        if response.status_code != HTTPStatus.OK:
            self.rasp_output_lb.setText("Error during blinking")
            return
        self.rasp_output_lb.setText(response.json().get("msg", "Error during blinking"))

    def send_command(self):
        """
        send command to current rasberry pi
        """

        text, ok = QInputDialog.getText(self, "Send a command", "Command:")
        if not ok:
            return

        cmd = base64.b64encode(text.encode("utf-8")).decode("utf-8")

        response = self.request(self.current_raspberry_id, f"/command/{cmd}", type="GET")
        if response is None:
            return

        if response.status_code != HTTPStatus.OK:
            self.rasp_output_lb.setText(f"Error sending command (status code: {response.status_code})")
            return

    def get_raspberry_status(self, raspberry_id):
        """
        get Raspberry Pi status
        """

        self.rasp_output_lb.setText("")

        response = self.request(raspberry_id, "/status", time_out=cfg.TIME_OUT)
        if response is None:
            if raspberry_id in self.raspberry_info:
                self.raspberry_info[raspberry_id]["status"] = {"status": "not reachable"}
            return {"status": "not reachable"}
        if response.status_code != HTTPStatus.OK:
            self.raspberry_info[raspberry_id]["status"] = {"status": f"not available (status code: {response.status_code})"}
            return {"status": f"not available (status code: {response.status_code})"}

        print(f"{self.raspberry_info = }")

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

        color = "green" if (self.raspberry_info[raspberry_id]["status"]["status"] == "OK") else "red"
        for x in range(self.rpi_list.count()):
            if self.rpi_list.item(x).text() == raspberry_id:
                self.rpi_list.item(x).setIcon(QIcon(f"{color}.png"))

    def get_status_for_all_rpi(self):
        """
        get status for all Raspberries Pi
        """

        threads = []
        for raspberry_id in self.raspberry_ip:
            threads.append(threading.Thread(target=self.get_raspberry_status, args=(raspberry_id,)))
            threads[-1].start()
        for x in threads:
            x.join()

        for raspberry_id in self.raspberry_ip:
            self.update_raspberry_display(raspberry_id)
            if self.current_raspberry_id == raspberry_id:
                self.update_raspberry_dashboard(raspberry_id)

    def enable_picture_parameters(self):
        self.lb_brightness.setEnabled(self.cb_enable_picture_parameters.isChecked())
        self.picture_brightness_sb.setEnabled(self.cb_enable_picture_parameters.isChecked())

        self.lb_contrast.setEnabled(self.cb_enable_picture_parameters.isChecked())
        self.picture_contrast_sb.setEnabled(self.cb_enable_picture_parameters.isChecked())

        self.lb_sharpness.setEnabled(self.cb_enable_picture_parameters.isChecked())
        self.picture_sharpness_sb.setEnabled(self.cb_enable_picture_parameters.isChecked())

        self.lb_saturation.setEnabled(self.cb_enable_picture_parameters.isChecked())
        self.picture_saturation_sb.setEnabled(self.cb_enable_picture_parameters.isChecked())

        self.lb_gain.setEnabled(self.cb_enable_picture_parameters.isChecked())
        self.picture_gain_sb.setEnabled(self.cb_enable_picture_parameters.isChecked())

    @verif
    def take_picture_clicked(self):
        """
        ask Raspberry Pi to take a picture
        """

        if self.sender().objectName() == "take_picture_pb":
            self.rasp_output_lb.setText("Picture requested")
            app.processEvents()
            time_lapse.take_picture(self, self.current_raspberry_id, mode="one")

        if self.sender().objectName() == "start_time_lapse_pb":
            self.rasp_output_lb.setText("Time lapse requested")
            app.processEvents()
            time_lapse.take_picture(self, self.current_raspberry_id, mode="time lapse")

    @verif
    def stop_time_lapse_clicked(self):
        """
        Stop the time lapse
        """

        time_lapse.stop_time_lapse(self, self.current_raspberry_id)

    @verif
    def start_video_recording_clicked(self):
        """
        start video recording with selected parameters
        """

        video_recording.start_video_recording(self, self.current_raspberry_id)

    @verif
    def stop_video_recording_clicked(self):
        """
        Stop current video recording
        """

        video_recording.stop_video_recording(self, self.current_raspberry_id)

    @verif
    def get_log_clicked(self):
        """
        get the log of the current Raspberry Pi
        """
        response = self.request(self.current_raspberry_id, "/get_log")
        if response.status_code != HTTPStatus.OK:
            self.rasp_output_lb.setText(f"Failed to start recording video (status code: {response.status_code})")
            return

        self.results = output_window.ResultsWidget()
        self.results.setWindowTitle("IP addresses")
        self.results.ptText.clear()
        self.results.ptText.setReadOnly(True)
        self.results.ptText.appendHtml(f'<pre>{response.json().get("msg", "")}</pre>')
        self.results.show()

    '''
    def update_all(self):
        """
        update server on all raspberries
        """
        text, ok = QInputDialog.getText(self, "Update server on all raspberries", "confirm writing 'yes'")
        if not ok or text != "yes":
            return

        for rb in sorted(self.raspberry_ip.keys()):
            if self.raspberry_status[rb]:
                self.rb_msg(rb, "Server update requested")
                r = os.system(f"scp server.py pi@{self.raspberry_ip[rb]}{cfg.CLIENT_PROJECT_DIRECTORY}")
                if not r:
                    self.rb_msg(rb, "Server updated")
                else:
                    self.rb_msg(rb, "<b>Error during server update</b>")
    '''
    """
    def download_videos_list(self, args):

        raspberry_id, videos_list = args
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
            return ["No video to download"]
        else:
            return output
    """


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="",
    )
    parser.add_argument("-p", "--password", action="store", dest="password")
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s v.{__version__} {__version_date__} (c) Olivier Friard 2021",
        help="Display the help",
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("Raspberry Pi coordinator")
    app.password = args.password
    rpi_coordinator = RPI_coordinator()

    # apply_stylesheet(app, theme='light_blue.xml', invert_secondary=True,)

    rpi_coordinator.show()
    sys.exit(app.exec_())
