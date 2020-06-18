"""
Raspberry Pi video recording coordinator (TCP/IP)

"""

from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QProcess, QTimer
import os
import sys
import json
import pathlib
import datetime
import subprocess
from functools import partial
import requests
import shutil
import threading
import logging
from config_coordinator import *

__version__ = "3"
__version_date__ = "2019-05-29"


SERVER_PORT = 5000
DEBUG = False


logging.basicConfig(filename="master.log",
                    filemode="a",
                    format='%(asctime)s, %(message)s',
                    datefmt='%H:%M:%S',
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

    return subprocess.call(command) == 0


class View_image(QWidget):

    def __init__(self):
        super().__init__()

        hbox = QVBoxLayout(self)

        self.label = QLabel()
        hbox.addWidget(self.label)


        hbox2 = QHBoxLayout()
        spacer_item = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        hbox2.addItem(spacer_item)

        self.pbOK = QPushButton("OK")
        self.pbOK.clicked.connect(self.ok)
        hbox2.addWidget(self.pbOK)

        hbox.addLayout(hbox2)
        self.setLayout(hbox)

        self.setGeometry(0, 0, 600, 400)

    def ok(self):
        self.hide()



class Video_recording_control(QMainWindow):

    raspberry_msg = {}
    status_list, text_list, download_button, record_button = [], {}, {}, {}
    (start_time, duration, interval, video_mode,
     video_quality, fps, prefix, resolution) = {}, {}, {}, {}, {}, {}, {}, {}
    download_process = {}


    def __init__(self):
        super().__init__()

        self.setWindowTitle("Raspberry - Video recording")
        self.statusBar().showMessage("v. {} - {}".format(__version__, __version_date__))

        self.setGeometry(0, 0, 1300, 768)

        layout = QVBoxLayout()
        hlayout1 = QHBoxLayout()

        self.tw = QTabWidget()

        q1 = QWidget()

        self.raspberry_status = {}
        rasp_count = 0


        for rb in sorted(RASPBERRY_IP):
            self.download_process[rb] = QProcess()
            rasp_count += 1

            l = QHBoxLayout()
            # l.addWidget(QLabel("<b>" + rb + "</b>"))

            # command output
            self.text_list[rb] = QTextEdit()
            self.text_list[rb].setLineWrapMode(QTextEdit.NoWrap)
            self.text_list[rb].setFontFamily("Monospace")
            l.addWidget(self.text_list[rb])

            right_layout = QVBoxLayout()

            l2 = QHBoxLayout()

            self.status_list.append(QPushButton("Status"))
            self.status_list[-1].clicked.connect(partial(self.status, rb, output=True))
            l2.addWidget(self.status_list[-1])

            q = QPushButton("Sync time")
            q.clicked.connect(partial(self.sync_time, rb))
            l2.addWidget(q)

            q = QPushButton("Get log")
            q.clicked.connect(partial(self.get_log, rb))
            l2.addWidget(q)

            q = QPushButton("Clear output")
            q.clicked.connect(partial(self.clear_output, rb))
            l2.addWidget(q)

            q = QPushButton("Blink")
            q.clicked.connect(partial(self.blink, rb))
            l2.addWidget(q)

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

            q = QPushButton("Take one picture")
            q.clicked.connect(partial(self.one_picture, rb))
            right_layout.addWidget(q)

            right_layout.addWidget(QLabel("<b>Video</b>"))
            l2 = QHBoxLayout()

            self.record_button[rb] = QPushButton("Start video recording")
            self.record_button[rb].clicked.connect(partial(self.start_video_recording, rb))
            l2.addWidget(self.record_button[rb])

            q = QPushButton("Stop video recording")
            q.clicked.connect(partial(self.stop_video_recording, rb))
            l2.addWidget(q)
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

            self.download_button[rb] = QPushButton("Download all video")
            self.download_button[rb].clicked.connect(partial(self.download_all_video, rb, ""))
            l2.addWidget(self.download_button[rb])

            q = QPushButton("Delete all video")
            q.clicked.connect(partial(self.delete_all_video, rb))
            l2.addWidget(q)
            right_layout.addLayout(l2)

            right_layout.addWidget(QLabel("<b>System commands</b>"))

            l2 = QHBoxLayout()
            q = QPushButton("Send command")
            q.clicked.connect(partial(self.send_command, rb))
            l2.addWidget(q)

            q = QPushButton("Reboot")
            q.clicked.connect(partial(self.reboot, rb))
            l2.addWidget(q)

            q = QPushButton("Shutdown")
            q.clicked.connect(partial(self.shutdown, rb))
            l2.addWidget(q)

            right_layout.addLayout(l2)

            verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
            right_layout.addItem(verticalSpacer)

            l.addLayout(right_layout)
            hlayout1.addLayout(l)

            if rasp_count % GUI_COLUMNS_NUMBER == 0 or rasp_count == len(RASPBERRY_IP):
                q1.setLayout(hlayout1)
                self.tw.addTab(q1, rb)

                hlayout1 = QHBoxLayout()
                q1 = QWidget()

        # status buttons
        hlayout_status_buttons = QHBoxLayout()
        self.status_buttons = []
        for rb in sorted(RASPBERRY_IP):
            self.status_buttons.append(QPushButton(rb))
            self.status_buttons[-1].clicked.connect(partial(self.change_tab, rb))
            hlayout_status_buttons.addWidget(self.status_buttons[-1])

        layout.addLayout(hlayout_status_buttons)

        # "all" buttons
        hlayout_all_buttons = QHBoxLayout()

        pb = QPushButton("Status from all")
        pb.clicked.connect(partial(self.status_all, True))
        hlayout_all_buttons.addWidget(pb)

        pb = QPushButton("Sync time all")
        pb.clicked.connect(self.sync_all)
        hlayout_all_buttons.addWidget(pb)

        pb = QPushButton("video list from all")
        pb.clicked.connect(self.video_list_from_all)
        hlayout_all_buttons.addWidget(pb)


        pb = QPushButton("Download video from all")
        pb.clicked.connect(self.download_all_video_from_all)
        hlayout_all_buttons.addWidget(pb)

        pb = QPushButton("Update all server")
        pb.clicked.connect(self.update_all)
        hlayout_all_buttons.addWidget(pb)

        pb = QPushButton("Send command to all")
        pb.clicked.connect(self.send_command_all)
        hlayout_all_buttons.addWidget(pb)

        pb = QPushButton("Clear all output")
        pb.clicked.connect(self.clear_all_output)
        hlayout_all_buttons.addWidget(pb)

        pb = QPushButton("Reboot all")
        pb.clicked.connect(self.reboot_all)
        hlayout_all_buttons.addWidget(pb)

        pb = QPushButton("Shutdown all")
        pb.clicked.connect(self.shutdown_all)
        hlayout_all_buttons.addWidget(pb)

        layout.addLayout(hlayout_all_buttons)

        # add navigation buttons
        hlayout_navigation_buttons = QHBoxLayout()
        pb = QPushButton("<-")
        pb.clicked.connect(self.go_left)
        hlayout_navigation_buttons.addWidget(pb)
        pb = QPushButton("->")
        pb.clicked.connect(self.go_right)
        hlayout_navigation_buttons.addWidget(pb)
        hlayout_navigation_buttons.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        layout.addLayout(hlayout_navigation_buttons)

        # add tab widget
        layout.addWidget(self.tw)

        main_widget = QWidget(self)
        main_widget.setLayout(layout)

        self.setCentralWidget(main_widget)

        # create widget for viewing image
        self.view_image_widget = View_image()

        self.show()
        self.status_all(output=True)

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(lambda: self.status_all(output=False))
        self.status_timer.setInterval(REFRESH_INTERVAL * 1000)
        self.status_timer.start()


    def change_tab(self, rb):
        """
        change tab when button clicked
        """
        self.tw.setCurrentIndex(sorted(list(RASPBERRY_IP.keys())).index(rb))

    def go_left(self):
        self.tw.setCurrentIndex(self.tw.currentIndex() - 1)

    def go_right(self):
        self.tw.setCurrentIndex(self.tw.currentIndex() + 1)



    def video_list(self, rb):
        """
        request a list of video to server
        """

        if rb in RASPBERRY_IP and self.raspberry_status[rb]:
            try:
                r = requests.get("http://{ip}:{port}/video_list".format(ip=RASPBERRY_IP[rb], port=SERVER_PORT))
                if r.status_code == 200:
                    self.rb_msg(rb, "list received (* for files not in archive)")
                    r2 = eval(r.text)
                    if "video_list" in r2:
                        for x in sorted(r2["video_list"]):
                            if not pathlib.Path(VIDEO_ARCHIVE + "/" + x).is_file():
                                self.text_list[rb].append("<b>* {}</b>".format(x))
                            else:
                                self.text_list[rb].append(x)
                else:
                    self.rb_msg(rb, "<b>Error status code: {}</b>".format(r.status_code))
                    self.status(rb, output=False)
            except Exception:
                self.rb_msg(rb, "<b>Error</b>")
                self.status(rb, output=False)


    def video_list_from_all(self):
        """
        request a list of video to all raspberries
        """
        for rb in sorted(RASPBERRY_IP.keys()):
            self.video_list(rb)



    def rb_msg(self, rb, msg):
        self.text_list[rb].append("<pre>{}: {}</pre>".format(date_iso(), msg))
        app.processEvents()


    def send_command(self, rb):
        if rb in RASPBERRY_IP and self.raspberry_status[rb]:
            text, ok = QInputDialog.getText(self, "Send a command", "Command:")
            if not ok:
                return
            self.rb_msg(rb, "sent command: {}".format(text))
            try:
                r = requests.get("http://{ip}:{port}/command/{text}".format(ip=RASPBERRY_IP[rb], port=SERVER_PORT, text=text))
                # r = requests.get('http://' + RASPBERRY_IP[rb] + ":5000/command/" + text)
                if r.status_code == 200:
                    r2 = eval(r.text)
                    if r2.get("status", "") != "error":
                        self.rb_msg(rb, "Return code: {}".format(r2.get("return_code", "-")))
                        self.rb_msg(rb, "output:\n" + r2.get("output", "-"))
                    else:
                        self.rb_msg(rb, "<b>Error</b>")
                else:
                    self.rb_msg(rb, "<b>Error status_code: {}</b>".format(r.status_code))
            except Exception:
                self.rb_msg(rb, "<b>Error</b>")
                self.status(rb, output=False)


    def send_command_all(self):
        """
        send command to all rasp
        """
        text, ok = QInputDialog.getText(self, "Send a command to all", "Command:")
        if not ok:
            return

        for rb in sorted(RASPBERRY_IP.keys()):
            if self.raspberry_status[rb]:
                self.rb_msg(rb, "sent command: " + text)
                try:
                    # r = requests.get('http://' + RASPBERRY_IP[rb] + ":5000/command/" + text)
                    r = requests.get("http://{ip}:{port}/command/{text}".format(ip=RASPBERRY_IP[rb], port=SERVER_PORT, text=text))
                    if r.status_code == 200:
                        r2 = eval(r.text)
                        self.rb_msg(rb, "Return code: {}".format(r2.get("return_code", "-")))
                        self.rb_msg(rb, "output:\n" + r2.get("output", "-"))
                    else:
                        self.rb_msg(rb, "Error. Status_code: {} ".format(r.status_code))
                except Exception:
                    if DEBUG:
                        raise
                    self.rb_msg(rb, "Error2")
                    self.status(rb, output=False)


    def reboot(self, rb):
        """
        send reboot signal to raspberry
        """
        if rb in RASPBERRY_IP and self.raspberry_status[rb]:
            text, ok = QInputDialog.getText(self, "Reboot rasberry", "confirm writing 'yes'")
            if not ok or text != "yes":
                return
            try:
                r = requests.get("http://{ip}:{port}/reboot".format(ip=RASPBERRY_IP[rb], port=SERVER_PORT))
                #r = requests.get('http://' + RASPBERRY_IP[rb] + ":5000/reboot")
                if r.status_code == 200:
                    self.rb_msg(rb, r.text)
                else:
                    self.rb_msg(rb, "Error status code: {}".format(r.status_code))
            except Exception:
                self.rb_msg(rb, "Error")
                self.status(rb, output=False)

    def reboot_all(self):
        """
        shutdown all raspberries
        """
        text, ok = QInputDialog.getText(self, "Reboot all rasberries", "confirm writing 'yes'")
        if not ok or text != "yes":
            return

        for rb in sorted(RASPBERRY_IP.keys()):
            if self.raspberry_status[rb]:
                try:
                    r = requests.get("http://{ip}:{port}/reboot".format(ip=RASPBERRY_IP[rb], port=SERVER_PORT))
                    #r = requests.get('http://' + RASPBERRY_IP[rb] + ":5000/reboot")
                except Exception:
                    self.rb_msg(rb, "Error")
                    self.status(rb)


    def shutdown(self, rb):
        """
        send shutdown signal to raspberry
        """
        if rb in RASPBERRY_IP and self.raspberry_status[rb]:
            text, ok = QInputDialog.getText(self, "Shutdown rasberry", "confirm writing 'yes'")
            if not ok or text != "yes":
                return
            try:
                r = requests.get("http://{ip}:{port}/shutdown".format(ip=RASPBERRY_IP[rb], port=SERVER_PORT))
                #r = requests.get('http://' + RASPBERRY_IP[rb] + ":5000/shutdown")
                if r.status_code == 200:
                    self.rb_msg(rb, r.text)
                else:
                    self.rb_msg(rb, "Error status code: {}".format(r.status_code))
            except Exception:
                self.rb_msg(rb, "Error")
                self.status(rb)


    def shutdown_all(self):
        """
        shutdown all raspberries
        """
        text, ok = QInputDialog.getText(self, "Shutdown all rasberries", "confirm writing 'yes'")
        if not ok or text != "yes":
            return

        for rb in sorted(RASPBERRY_IP.keys()):
            if self.raspberry_status[rb]:
                try:
                    r = requests.get("http://{ip}:{port}/shutdown".format(ip=RASPBERRY_IP[rb], port=SERVER_PORT))
                    #r = requests.get('http://' + RASPBERRY_IP[rb] + ":5000/shutdown")
                except Exception:
                    self.rb_msg(rb, "Error")
                    self.status(rb)



    def clear_all_output(self):
        for rb in RASPBERRY_IP:
             self.text_list[rb].clear()


    def clear_output(self, rb):
        self.text_list[rb].clear()


    def blink(self, rb):
        """
        blink the powed led
        """
        if rb in RASPBERRY_IP and RASPBERRY_IP[rb]:
            self.rb_msg(rb, "blink requested")
            try:
                r = requests.get('http://' + RASPBERRY_IP[rb] + ":5000/blink", timeout=2)
            except Exception:
                self.rb_msg(rb, "Error")
                self.status(rb)



    def status(self, rb, output=True):

        try:
            if rb in RASPBERRY_IP and RASPBERRY_IP[rb]:

                r1 = ping(RASPBERRY_IP[rb])

                # check if answer to ping
                if not r1:
                    color = "red"
                else:
                    if output:
                        self.rb_msg(rb, "status requested")
                    r = requests.get('http://' + RASPBERRY_IP[rb] + ":5000/status", timeout=1)
                    if output:
                        logging.info("raspberry: {} status_code: {}".format(rb, r.status_code))
                    if r.status_code == 200:
                        if output:
                            self.rb_msg(rb, json_formater(r.text))
                        r2 = eval(r.text)
                        color = "green" if r2["status"] == "OK" else "red"
                    else:
                        color = "red"
            else:
                color = "red"
        except Exception:
            color = "red"

        # check if recording
        if color == "green":
            if "video_recording" in r2:
                if r2["video_recording"]:
                    color = "orange"
                    self.record_button[rb].setStyleSheet("background: orange;")
                else:
                    self.record_button[rb].setStyleSheet("")
            else:
                self.record_button[rb].setStyleSheet("")

        self.status_list[sorted(list(RASPBERRY_IP.keys())).index(rb)].setStyleSheet("background: {color};".format(color=color))

        self.status_buttons[sorted(list(RASPBERRY_IP.keys())).index(rb)].setStyleSheet("background: {color};".format(color=color))

        self.raspberry_status[rb] = (color != "red")

        if color == "red" and output:
            self.rb_msg(rb, "status: not available")


    def status_all(self, output=True):
        """
        ask status to all raspberries
        """
        if output:
            for rb in sorted(RASPBERRY_IP):
                self.status_buttons[sorted(list(RASPBERRY_IP.keys())).index(rb)].setStyleSheet("")
                self.status_list[sorted(list(RASPBERRY_IP.keys())).index(rb)].setStyleSheet("")

        for rb in sorted(RASPBERRY_IP):
            self.status(rb, output=output)
            app.processEvents()


    def sync_time(self, rb):
        """
        Set date/time on raspberry
        """
        if rb in RASPBERRY_IP and self.raspberry_status[rb]:
            date, hour = date_iso().split(" ")
            self.rb_msg(rb, "Time synchronization requested")
            try:
                r = requests.get('http://' + RASPBERRY_IP[rb] + ":5000/sync_time/{}/{}".format(date, hour))
                self.rb_msg(rb, json_formater(r.text))
            except Exception:
                self.rb_msg(rb, "Error")
                self.status(rb)


    def sync_all(self):
        """
        synchronize all raspberries
        """
        for rb in sorted(RASPBERRY_IP.keys()):
            self.sync_time(rb)


    def one_picture(self, rb):
        """
        ask one picture
        """
        if rb in RASPBERRY_IP and self.raspberry_status[rb]:
            try:
                # r = requests.get('http://' + RASPBERRY_IP[rb] + ":5000/one_picture")
                self.rb_msg(rb, "picture requested")
                w, h = self.resolution[rb].currentText().split("x")
                r = requests.get("http://" + RASPBERRY_IP[rb] + ":5000/one_picture?w={w}&h={h}".format(w=w, h=h))

                r2 = eval(r.text)
                if r2["result"] == "OK":
                    r = requests.get('http://' + RASPBERRY_IP[rb] + ":5000/static/live.jpg", stream=True)
                    if r.status_code == 200:
                        with open("live_{rb}.jpg".format(rb=rb), 'wb') as f:
                            r.raw.decode_content = True
                            shutil.copyfileobj(r.raw, f)
                        self.rb_msg(rb, "OK")

                        self.pixmap = QPixmap("live_{rb}.jpg".format(rb=rb))
                        self.view_image_widget.label.setPixmap(self.pixmap)
                        self.view_image_widget.show()

                    else:
                        self.rb_msg(rb, "Error1")
                else:
                    self.rb_msg(rb, "Error2")

            except requests.exceptions.ConnectionError:
                self.rb_msg(rb, "Connection refused")

            except Exception:
                if DEBUG:
                    raise
                self.rb_msg(rb, "Error3")


    def start_video_recording(self, rb):

        if rb in RASPBERRY_IP and self.raspberry_status[rb]:
            w, h = self.video_mode[rb].currentText().split("x")
            try:
                r = requests.get("http://{ip}:5000/start_video?duration={duration}&w={w}&h={h}&prefix={prefix}&fps={fps}&quality={quality}".format(
                        ip=RASPBERRY_IP[rb],
                        duration=self.duration[rb].value(),
                        w=w,
                        h=h,
                        prefix=self.prefix[rb].text().replace(" ", "_"),
                        fps=10,
                        quality=1
                        ))

                self.rb_msg(rb, r.text)
                self.status(rb)

            except requests.exceptions.ConnectionError:
                self.rb_msg(rb, "Connection refused")
                self.status(rb, output=False)

            except Exception:
                self.rb_msg(rb, "Error")
                self.status(rb, output=False)


    def stop_video_recording(self, rb):
        if rb in RASPBERRY_IP and self.raspberry_status[rb]:
            try:
                self.rb_msg(rb, "stop video recording requested")
                r = requests.get('http://' + RASPBERRY_IP[rb] + ":5000/stop_video")
                self.rb_msg(rb, r.text)
                self.status(rb, output=False)
            except Exception:
                self.rb_msg(rb, "Error")
                self.status(rb, output=False)


    '''
    def download_one_video(self, rb):
        """
        download one video
        """
        text, ok = QInputDialog.getText(self, "Download video", "File name:")
        if not ok:
            return
        try:
            r = requests.get('http://' + RASPBERRY_IP[rb] + ":5000/static/" + VIDEO_ARCHIVE + "/" + text, stream=True)

            if r.status_code == 200:
                with open(VIDEO_ARCHIVE + "/" + text, "wb") as f:
                    r.raw.decode_content = True
                    shutil.copyfileobj(r.raw, f)
                self.rb_msg(rb, "Video downloaded")

        except Exception:
            self.rb_msg(rb, "Error")
    '''



    def delete_all_video(self, rb):
        """
        delete all video from server
        """
        text, ok = QInputDialog.getText(self, "Delete all video from server", "confirm writing 'yes'")
        if not ok or text != "yes":
            return
        try:
            self.rb_msg(rb, "deletion of all video requested")
            r = requests.get('http://' + RASPBERRY_IP[rb] + ":5000/delete_all_video")
            if r.status_code == 200:
                r2 = eval(r.text)
                if r2.get("status", "") == "OK":
                    self.rb_msg(rb, "All video deleted")
                if r2.get("status", "") == "error":
                    self.rb_msg(rb, "<b>Error deleting all video</b>")

            else:
                self.rb_msg(rb, "<b>Error status code: {}</b>".format(r.status_code))
        except Exception:
            self.rb_msg(rb, "<b>Error</b>")


    def get_log(self, rb):

        if rb in RASPBERRY_IP and self.raspberry_status[rb]:
            try:
                r = requests.get('http://' + RASPBERRY_IP[rb] + ":5000/get_log")
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

        for rb in sorted(RASPBERRY_IP):
            if self.raspberry_status[rb]:
                self.rb_msg(rb, "Server update requested")
                r = os.system("scp server.py pi@{IP}:{CLIENT_PROJECT_DIRECTORY}".format(IP=RASPBERRY_IP[rb],
                                                                                     CLIENT_PROJECT_DIRECTORY=CLIENT_PROJECT_DIRECTORY))
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
            QMessageBox.critical(None, "Raspberry controller", "Destination not found!<br>" + VIDEO_ARCHIVE + "<br><br>Choose another directory",
                                 QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)

            new_download_dir = QFileDialog().getExistingDirectory(self, "Choose a directory to download video",
                                                                  os.path.expanduser("~"),
                                                                  options=QFileDialog.ShowDirsOnly)
            if new_download_dir:
                download_dir = new_download_dir
            else:
                return

        if rb in RASPBERRY_IP and self.raspberry_status[rb]:


            self.clear_output(rb)
            self.download_button[rb].setStyleSheet("background: red;")
            app.processEvents()
            self.download_process[rb] = QProcess()
            self.download_process[rb].setProcessChannelMode(QProcess.MergedChannels)
            self.download_process[rb].readyReadStandardOutput.connect(lambda: self.read_process_stdout(rb))
            self.download_process[rb].error.connect(lambda x: self.process_error(x, rb))
            self.download_process[rb].finished.connect(lambda exitcode: self.download_finished(exitcode, rb))

            '''
            print(" ".join(["rsync", "-avz",
                            "pi@{IP}:{CLIENT_PROJECT_DIRECTORY}/static/video_archive/".format(IP=RASPBERRY_IP[rb],
                                                                    CLIENT_PROJECT_DIRECTORY=CLIENT_PROJECT_DIRECTORY),
                               download_dir]))
            '''

            self.download_process[rb].start("rsync",
                                            ["-avz",
                                             "pi@{IP}:{CLIENT_PROJECT_DIRECTORY}/static/video_archive/".format(IP=RASPBERRY_IP[rb],
                                                                                                               CLIENT_PROJECT_DIRECTORY=CLIENT_PROJECT_DIRECTORY),
                                             download_dir])



    def read_process_stdout(self, rb):

        out = self.download_process[rb].readAllStandardOutput()
        self.rb_msg(rb, bytes(out).decode("utf-8").strip())
        #print(out.toHex().decode('ascii'))
        #print(str(self.process1.readAllStandardOutput()))

    def process_error(self, process_error, rb):
        print("process error", process_error)
        print("process state", self.download_process[rb].state())
        self.rb_msg(rb, "Error downloading video.\nProcess error: {}  Process state: {}".format(process_error, self.download_process[rb].state()))
        self.download_button[rb].setStyleSheet("")


    def download_finished(self, exitcode, rb):
        """
        download finished
        """
        print("exit code", exitcode)
        if exitcode:
            self.rb_msg(rb, "Error downloading video.\nExit code: {}".format(exitcode))
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
            QMessageBox.critical(None, "Raspberry - Video recording", "Destination not found!<br>" + VIDEO_ARCHIVE + "<br><br>Choose another directory",
                                 QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)

            new_download_dir = QFileDialog().getExistingDirectory(self, "Choose a directory to download video",
                                                                  os.path.expanduser("~"),
                                                                  options=QFileDialog.ShowDirsOnly)

            if not new_download_dir:
                return
            else:
                download_dir = new_download_dir
        else:
            download_dir = VIDEO_ARCHIVE


        for rb in sorted(RASPBERRY_IP):
            if self.raspberry_status[rb]:
                self.download_all_video(rb, download_dir)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    video_recording_control = Video_recording_control()
    sys.exit(app.exec_())
