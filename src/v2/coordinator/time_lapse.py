"""
Raspberry Pi coordinator

time lapse module
"""

from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMessageBox, QTableWidgetItem
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject

import pathlib as pl
import config_coordinator as cfg
import logging
import shutil
import datetime
import time
import requests


def datetime_now_iso():
    return datetime.datetime.now().replace(microsecond=0).isoformat().replace("T", " ")


def take_picture(self, raspberry_id: str, mode: str):
    """
    start time lapse or take a picture and display it
    """

    if raspberry_id not in self.raspberry_ip:
        return

    if self.raspberry_info[raspberry_id]["status"]["status"] == "OK":  # and self.raspberry_status[raspberry_id]:

        width, height = self.raspberry_info[raspberry_id]["picture resolution"].split("x")
        data = {
            "key": self.security_key,
            "width": width,
            "height": height,
            "brightness": self.raspberry_info[raspberry_id]["picture brightness"],
            "contrast": self.raspberry_info[raspberry_id]["picture contrast"],
            "saturation": self.raspberry_info[raspberry_id]["picture saturation"],
            "sharpness": self.raspberry_info[raspberry_id]["picture sharpness"],
            # "ISO": self.raspberry_info[raspberry_id]['picture iso'],
            "gain": self.raspberry_info[raspberry_id]["picture gain"],
            "rotation": self.raspberry_info[raspberry_id]["picture rotation"],
            "hflip": self.raspberry_info[raspberry_id]["picture hflip"],
            "vflip": self.raspberry_info[raspberry_id]["picture vflip"],
            "timelapse": self.raspberry_info[raspberry_id]["time lapse wait"] if mode == "time lapse" else 0,
            "timeout": self.raspberry_info[raspberry_id]["time lapse duration"] if mode == "time lapse" else 0,
            "annotate": self.raspberry_info[raspberry_id]["picture annotation"],
        }

        # add file name based on epoch
        if mode == "one":
            data["file_name"] = f"{str(int(time.time()))}.jpg"

        response = self.request(raspberry_id, f"/take_picture", type="POST", data=data)

        if response.status_code != 200:
            self.rasp_output_lb.setText(f"Error taking picture (status code: {response.status_code})")
            return

        if response.json().get("error", True):
            self.rasp_output_lb.setText(
                f'{response.json().get("msg", "Undefined error")}  returncode: {response.json().get("error", "-")}'
            )
            return

        self.rasp_output_lb.setText(response.json().get("msg", "Undefined error"))
        # app.processEvents()

        # check if time lapse requested
        if mode == "time lapse":
            self.get_raspberry_status(raspberry_id)
            self.update_raspberry_display(raspberry_id)
            self.update_raspberry_dashboard(raspberry_id)
            return

        try:
            response2 = requests.get(
                f"{cfg.PROTOCOL}{self.raspberry_ip[raspberry_id]}{cfg.SERVER_PORT}/static/live_pictures/{data['file_name']}",
                stream=True,
                verify=False,
            )

        except Exception:
            self.rasp_output_lb.setText(f"Error contacting the Raspberry Pi {raspberry_id}")
            return

        if response2.status_code != 200:
            self.rasp_output_lb.setText(f"Error retrieving the picture. Server status code: {response.status_code}")
            return

        with open(f"live_{raspberry_id}.jpg", "wb") as f:
            response2.raw.decode_content = True
            shutil.copyfileobj(response2.raw, f)

        self.tw_picture.setCurrentIndex(2)
        self.picture_lb.setPixmap(
            QPixmap(f"live_{raspberry_id}.jpg").scaled(self.picture_lb.size(), Qt.KeepAspectRatio)
        )
        self.rasp_output_lb.setText(f"Picture received at {datetime_now_iso()}")

        self.get_raspberry_status(raspberry_id)
        self.update_raspberry_display(raspberry_id)
        self.update_raspberry_dashboard(raspberry_id)


def stop_time_lapse(self, raspberry_id):
    """
    Stop the time lapse
    """
    if raspberry_id not in self.raspberry_ip:
        return

    response = self.request(raspberry_id, "/stop_time_lapse")
    if response == None:
        return

    if response.status_code != 200:
        self.rasp_output_lb.setText(f"Error trying to stop time lapse (status code: {response.status_code})")
        return
    self.rasp_output_lb.setText(response.json().get("msg", "Error during stopping time lapse"))
    self.get_raspberry_status(raspberry_id)
    self.update_raspberry_display(raspberry_id)
    self.update_raspberry_dashboard(raspberry_id)


def schedule_time_lapse(self, raspberry_id):
    """
    Schedule the picture taking on the Raspberry Pi
    """

    if self.picture_hours_le.text() == "":
        QMessageBox.information(
            None,
            "Raspberry Pi coordinator",
            f"Specify the hour(s) to start time lapse",
            QMessageBox.Ok | QMessageBox.Default,
            QMessageBox.NoButton,
        )
        return

    if self.picture_minutes_le.text() == "":
        QMessageBox.information(
            None,
            "Raspberry Pi coordinator",
            f"Specify the minutes(s) to start time lapse",
            QMessageBox.Ok | QMessageBox.Default,
            QMessageBox.NoButton,
        )
        return

    if self.picture_days_of_week_le.text() == "":
        QMessageBox.information(
            None,
            "Raspberry Pi coordinator",
            f"Specify the day(s) of the week to start time lapse (0-6 or SUN-SAT)",
            QMessageBox.Ok | QMessageBox.Default,
            QMessageBox.NoButton,
        )
        return

    if self.picture_days_of_month_le.text() == "":
        QMessageBox.information(
            None,
            "Raspberry Pi coordinator",
            f"Specify the day(s) of the month to start time lapse (1-31)",
            QMessageBox.Ok | QMessageBox.Default,
            QMessageBox.NoButton,
        )
        return

    # check hours format
    hours = self.picture_hours_le.text().replace(" ", "")
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
            QMessageBox.information(
                None,
                "Raspberry Pi coordinator",
                f"The hour(s) format is not correct. Example; 1,2,13,15 or *",
                QMessageBox.Ok | QMessageBox.Default,
                QMessageBox.NoButton,
            )
            return
        hours_str = ",".join([str(x) for x in int_hours_list])

    # check minutes format
    minutes = self.picture_minutes_le.text().replace(" ", "")
    if minutes == "*":
        minutes_str = minutes
    else:
        minutes_splt = minutes.split(",")
        try:
            int_minutes_list = [int(x) for x in minutes_splt]
            for x in int_minutes_list:
                if not (0 <= x < 60):
                    raise
        except Exception:
            QMessageBox.information(
                None,
                "Raspberry Pi coordinator",
                f"The minutes(s) format is not correct. Example; 1,2,13,15 or *",
                QMessageBox.Ok | QMessageBox.Default,
                QMessageBox.NoButton,
            )
            return

        minutes_str = ",".join([str(x) for x in int_minutes_list])

    # check days of month format
    dom = self.picture_days_of_month_le.text().replace(" ", "")
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
            QMessageBox.information(
                None,
                "Raspberry Pi coordinator",
                f"The day(s) of month format is not correct. Example; 1,2,13,15 or *",
                QMessageBox.Ok | QMessageBox.Default,
                QMessageBox.NoButton,
            )
            return
        dom_str = ",".join([str(x) for x in int_dom_list])

    # check month format
    month = self.picture_months_le.text().replace(" ", "")
    if month == "*":
        month_str = month
    else:
        month_splt = month.split(",")
        try:
            int_month_list = [int(x) for x in month_splt]
            for x in int_month_list:
                if not (1 <= x <= 12):
                    raise
        except Exception:
            QMessageBox.information(
                None,
                "Raspberry Pi coordinator",
                f"The month format is not correct. Example; 1,2,12 or *",
                QMessageBox.Ok | QMessageBox.Default,
                QMessageBox.NoButton,
            )
            return
        month_str = ",".join([str(x) for x in int_month_list])

    # check days(s) of week format
    dow = self.picture_days_of_week_le.text().replace(" ", "")
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
                QMessageBox.information(
                    None,
                    "Raspberry Pi coordinator",
                    f"The days(s) of week format is not correct. Example; 0,1,2 or SUN,MON,TUE",
                    QMessageBox.Ok | QMessageBox.Default,
                    QMessageBox.NoButton,
                )

        dow_str = ",".join([str(x) for x in int_dow_splt])

    crontab_event = f"{minutes_str} {hours_str} {dom_str} {month_str} {dow_str}"

    logging.info(f"crontab event: {crontab_event} for {raspberry_id}")

    width, height = self.raspberry_info[raspberry_id]["picture resolution"].split("x")
    data = {
        "crontab": crontab_event,
        "timelapse": self.raspberry_info[raspberry_id]["time lapse wait"],
        "timeout": self.raspberry_info[raspberry_id]["time lapse duration"],
        "width": width,
        "height": height,
        "brightness": self.raspberry_info[raspberry_id]["picture brightness"],
        "contrast": self.raspberry_info[raspberry_id]["picture contrast"],
        "saturation": self.raspberry_info[raspberry_id]["picture saturation"],
        "sharpness": self.raspberry_info[raspberry_id]["picture sharpness"],
        "gain": self.raspberry_info[raspberry_id]["picture gain"],
        "rotation": self.raspberry_info[raspberry_id]["picture rotation"],
        "hflip": self.raspberry_info[raspberry_id]["picture hflip"],
        "vflip": self.raspberry_info[raspberry_id]["picture vflip"],
        # "annotate": self.raspberry_info[raspberry_id]["picture annotation"],
    }

    response = self.request(raspberry_id, f"/schedule_time_lapse", type="POST", data=data)

    if response == None:
        return

    if response.status_code != 200:
        self.rasp_output_lb.setText(f"Error during the time lapse scheduling (status code: {response.status_code})")
        return

    self.rasp_output_lb.setText(response.json().get("msg", "Error during time lapse scheduling"))

    self.view_time_lapse_schedule_clicked()


def view_time_lapse_schedule(self, raspberry_id):
    """
    view time lapse schedule on Raspberry Pi
    """

    response = self.request(raspberry_id, f"/view_time_lapse_schedule")
    if response == None:
        return

    if response.status_code != 200:
        self.rasp_output_lb.setText(
            f"Error during view of the time lapse scheduling (status code: {response.status_code})"
        )
        return

    crontab_content = response.json().get("msg", "")

    self.time_lapse_schedule_table.setRowCount(len(crontab_content))
    for i in range(0, len(crontab_content)):
        tokens = crontab_content[i]
        for j in range(0, 5 + 1):
            self.time_lapse_schedule_table.setItem(i, j, QTableWidgetItem(tokens[j]))

    self.time_lapse_schedule_table.resizeColumnsToContents()


def delete_time_lapse_schedule(self, raspberry_id):
    """
    delete all time lapse schedule
    """

    response = self.request(raspberry_id, f"/delete_time_lapse_schedule")
    if response == None:
        return

    if response.status_code != 200:
        self.rasp_output_lb.setText(
            f"Error during deletion of the time lapse scheduling (status code: {response.status_code})"
        )
        return
    self.rasp_output_lb.setText(response.json().get("msg", "Error during deletion of the time lapse scheduling"))

    self.view_time_lapse_schedule_clicked()


def get_pictures_list(self, raspberry_id):
    """
    request the list of recorded pictures to Raspberry Pi
    """

    response = self.request(raspberry_id, "/pictures_list")
    if response == None:
        return

    if response.status_code != 200:
        self.rasp_output_lb.setText(
            f"Error requiring the list of recorded pictures (status code: {response.status_code})"
        )
        return
    if "pictures_list" not in response.json():
        self.rasp_output_lb.setText(f"Error requiring the list of recorded pictures")
        return

    return sorted(list(response.json()["pictures_list"]))


class Download_pict_worker(QObject):
    def __init__(self, raspberry_ip):
        super().__init__()
        # list of Raspberry Pi IP addresses
        self.raspberry_ip = raspberry_ip

    start = pyqtSignal(str, list, str, str)
    progress = pyqtSignal(str)
    finished = pyqtSignal(list)

    def run(self, raspberry_id, pictures_list, download_dir, remote_pictures_archive_dir):

        downloaded_pictures = []
        count = 0
        for picture_file_name, picture_size in sorted(pictures_list):

            if (pl.Path(download_dir) / pl.Path(picture_file_name)).is_file():
                if (pl.Path(download_dir) / pl.Path(picture_file_name)).stat().st_size == picture_size:
                    count += 1
                    continue

            logging.info(f"Downloading {picture_file_name} from {raspberry_id}")

            with requests.get(
                f"{cfg.PROTOCOL}{self.raspberry_ip[raspberry_id]}{cfg.SERVER_PORT}{remote_pictures_archive_dir}/{picture_file_name}",
                stream=True,
                verify=False,
            ) as r:
                with open((pl.Path(download_dir) / pl.Path(picture_file_name)), "wb") as file_out:
                    shutil.copyfileobj(r.raw, file_out)

            logging.info(f"{picture_file_name} downloaded from {raspberry_id}")

            downloaded_pictures.append(picture_file_name)
            count += 1
            self.progress.emit(f"{count}/{len(pictures_list)} pictures downloaded")

        self.finished.emit(downloaded_pictures)


def download_timelapse_pictures(self, raspberry_id, download_dir):
    """
    Download the time lapse pictures from Raspberry Pi
    """

    def thread_progress(output):
        self.rasp_output_lb.setText(output)

    def thread_finished(downloaded_pictures_list):
        self.rasp_output_lb.setText(f"{len(downloaded_pictures_list)} pictures downloaded in <b>{download_dir}</b>")
        self.video_list_clicked()
        self.pict_download_thread.quit

    remote_pictures_list = get_pictures_list(self, raspberry_id)
    if len(remote_pictures_list) == 0:
        self.rasp_output_lb.setText(f"No pictures to download")
        return

    # get pictures archive directory
    response = self.request(raspberry_id, "/timelapse_pictures_archive_dir")
    if response == None:
        return
    if response.status_code != 200:
        self.rasp_output_lb.setText(
            f"Error requiring the pictures archive directory (status code: {response.status_code})"
        )
        return
    if response.json().get("error", True):
        self.rasp_output_lb.setText(f"Error requiring the pictures archive directory")
        return
    remote_pictures_archive_dir = response.json().get("msg", "")

    self.pict_download_thread = QThread(parent=self)
    self.pict_download_thread.start()
    self.pict_download_worker = Download_pict_worker(self.raspberry_ip)
    self.pict_download_worker.moveToThread(self.pict_download_thread)

    self.pict_download_worker.start.connect(self.pict_download_worker.run)
    self.pict_download_worker.progress.connect(thread_progress)
    self.pict_download_worker.finished.connect(thread_finished)
    self.pict_download_worker.start.emit(raspberry_id, remote_pictures_list, download_dir, remote_pictures_archive_dir)


def download_live_pictures(self, raspberry_id, download_dir):
    """
    Download the live pictures from Raspberry Pi
    """

    def thread_progress(output):
        self.rasp_output_lb.setText(output)

    def thread_finished(downloaded_pictures_list):
        self.rasp_output_lb.setText(f"{len(downloaded_pictures_list)} pictures downloaded in <b>{download_dir}</b>")
        self.video_list_clicked()
        self.pict_download_thread.quit

    remote_pictures_list = get_pictures_list(self, raspberry_id)
    if len(remote_pictures_list) == 0:
        self.rasp_output_lb.setText(f"No pictures to download")
        return

    # get pictures archive directory
    response = self.request(raspberry_id, "/live_pictures_archive_dir")
    if response == None:
        return
    if response.status_code != 200:
        self.rasp_output_lb.setText(
            f"Error requiring the pictures archive directory (status code: {response.status_code})"
        )
        return
    if response.json().get("error", True):
        self.rasp_output_lb.setText(f"Error requiring the pictures archive directory")
        return
    remote_pictures_archive_dir = response.json().get("msg", "")

    self.pict_download_thread = QThread(parent=self)
    self.pict_download_thread.start()
    self.pict_download_worker = Download_pict_worker(self.raspberry_ip)
    self.pict_download_worker.moveToThread(self.pict_download_thread)

    self.pict_download_worker.start.connect(self.pict_download_worker.run)
    self.pict_download_worker.progress.connect(thread_progress)
    self.pict_download_worker.finished.connect(thread_finished)
    self.pict_download_worker.start.emit(raspberry_id, remote_pictures_list, download_dir, remote_pictures_archive_dir)
