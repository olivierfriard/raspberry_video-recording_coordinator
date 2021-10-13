"""
Raspberry Pi coordinator

video recording module
"""

import config_coordinator_local as cfg
from PyQt5.QtWidgets import (QMessageBox, QTableWidgetItem)
from PyQt5.QtCore import (QThread, pyqtSignal, QObject, Qt)
import pathlib as pl
import logging
import requests
import shutil
import json


class Download_videos_worker(QObject):

    def __init__(self, raspberry_ip):
        super().__init__()
        # list of Raspberry Pi IP
        self.raspberry_ip = raspberry_ip

    start = pyqtSignal(str, list, str, str)
    progress = pyqtSignal(str)
    finished = pyqtSignal(list)

    def run(self, raspberry_id, videos_list, download_dir, video_archive_dir):

        downloaded_video = []
        count = 0
        for video_file_name, video_size in sorted(videos_list):

            if (pl.Path(download_dir) / pl.Path(video_file_name)).is_file():
                if (pl.Path(download_dir) / pl.Path(video_file_name)).stat().st_size == video_size:
                    count += 1
                    continue

            logging.info(f"Downloading  {video_file_name} from {raspberry_id}")

            with requests.get(
                    f"{cfg.PROTOCOL}{self.raspberry_ip[raspberry_id]}{cfg.SERVER_PORT}{video_archive_dir}/{video_file_name}",
                    stream=True,
                    verify=False) as r:
                with open((pl.Path(download_dir) / pl.Path(video_file_name)), "wb") as file_out:
                    shutil.copyfileobj(r.raw, file_out)

            logging.info(f"{video_file_name} downloaded from {raspberry_id}")

            downloaded_video.append(video_file_name)
            count += 1
            self.progress.emit(f"{count}/{len(videos_list)} video downloaded")

        self.finished.emit(downloaded_video)


def start_video_recording(self, raspberry_id):
    """
    start video recording with selected parameters
    """

    width, height = self.raspberry_info[raspberry_id]["video mode"].split("x")
    data = {
        "key": self.security_key,
        "timeout": self.raspberry_info[raspberry_id]["video duration"] * 1000,
        "width": width,
        "height": height,
        "prefix": "",
        "framerate": self.raspberry_info[raspberry_id]["FPS"],
        "bitrate": self.raspberry_info[raspberry_id]["video quality"] * 1_000_000,
        "brightness": self.raspberry_info[raspberry_id]['video brightness'],
        "contrast": self.raspberry_info[raspberry_id]['video contrast'],
        "saturation": self.raspberry_info[raspberry_id]['video saturation'],
        "sharpness": self.raspberry_info[raspberry_id]['video sharpness'],
        "ISO": self.raspberry_info[raspberry_id]['video iso'],
        "rotation": self.raspberry_info[raspberry_id]['video rotation'],
        "hflip": self.raspberry_info[raspberry_id]['video hflip'],
        "vflip": self.raspberry_info[raspberry_id]['video vflip'],
    }

    self.rasp_output_lb.setText("start video recording requested")
    response = self.request(raspberry_id, "/start_video", data=data)
    if response == None:
        return

    if response.status_code != 200:
        self.rasp_output_lb.setText(f"Failed to start recording video (status code: {response.status_code})")
        return

    self.rasp_output_lb.setText(response.json().get("msg", "Error recording video"))

    self.get_raspberry_status(raspberry_id)
    self.update_raspberry_display(raspberry_id)
    self.update_raspberry_dashboard(raspberry_id)


def stop_video_recording(self, raspberry_id):
    """
    stop video recording
    """

    self.rasp_output_lb.setText("stop video recording requested")
    response = self.request(raspberry_id, "/stop_video")
    if response == None:
        return

    if response.status_code != 200:
        self.rasp_output_lb.setText(f"Failed to stop recording video (status code: {response.status_code})")
        return
    self.rasp_output_lb.setText(response.json().get("msg", "Failed to stop recording video"))

    self.get_raspberry_status(raspberry_id)
    self.update_raspberry_display(raspberry_id)
    self.update_raspberry_dashboard(raspberry_id)

    self.video_list_clicked()


def schedule_video_recording(self, raspberry_id):
    """
    Schedule the video recording on the Raspberry Pi
    """

    if self.hours_le.text() == "":
        QMessageBox.information(None, "Raspberry Pi coordinator", f"Specify the hour(s) to start video recording",
                                QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
        return

    if self.minutes_le.text() == "":
        QMessageBox.information(None, "Raspberry Pi coordinator", f"Specify the minutes(s) to start video recording",
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

    data = {
        "crontab": crontab_event,
        "timeout": self.raspberry_info[raspberry_id]["video duration"] * 1000,
        "width": width,
        "height": height,
        "prefix": "",
        "framerate": self.raspberry_info[raspberry_id]["FPS"],
        "bitrate": self.raspberry_info[raspberry_id]["video quality"] * 1_000_000,
        "brightness": self.raspberry_info[raspberry_id]['video brightness'],
        "contrast": self.raspberry_info[raspberry_id]['video contrast'],
        "saturation": self.raspberry_info[raspberry_id]['video saturation'],
        "sharpness": self.raspberry_info[raspberry_id]['video sharpness'],
        "ISO": self.raspberry_info[raspberry_id]['video iso'],
        "rotation": self.raspberry_info[raspberry_id]['video rotation'],
        "hflip": self.raspberry_info[raspberry_id]['video hflip'],
        "vflip": self.raspberry_info[raspberry_id]['video vflip'],
    }

    response = self.request(raspberry_id, f"/schedule_video_recording", data=data)
    if response == None:
        return

    if response.status_code != 200:
        self.rasp_output_lb.setText(
            f"Error during the video recording scheduling (status code: {response.status_code})")
        return

    self.rasp_output_lb.setText(response.json().get("msg", "Error during video recording scheduling"))
    self.view_video_recording_schedule_clicked()


def view_video_recording_schedule(self, raspberry_id):
    """
    view schedule on Raspberry Pi
    """
    response = self.request(raspberry_id, f"/view_video_recording_schedule")
    if response == None:
        return

    if response.status_code != 200:
        self.rasp_output_lb.setText(
            f"Error during view of the video recording scheduling (status code: {response.status_code})")
        return

    crontab_content = response.json().get("msg", "")

    self.video_rec_schedule_table.setRowCount(len(crontab_content))
    for i in range(0, len(crontab_content)):
        tokens = crontab_content[i]
        for j in range(0, 5 + 1):
            self.video_rec_schedule_table.setItem(i, j, QTableWidgetItem(tokens[j]))

    self.video_rec_schedule_table.resizeColumnsToContents()


def delete_video_recording_schedule(self, raspberry_id):
    """
    delete all video recording schedule
    """

    response = self.request(raspberry_id, f"/delete_video_recording_schedule")
    if response == None:
        return

    if response.status_code != 200:
        self.rasp_output_lb.setText(
            f"Error during deletion of the video recording scheduling (status code: {response.status_code})")
        return
    self.rasp_output_lb.setText(response.json().get("msg", "Error during deletion of the video recording scheduling"))
    self.view_video_recording_schedule_clicked()


def video_list(self, raspberry_id: str) -> list:
    """
    request the list of recorded video to Raspberry Pi
    """

    response = self.request(raspberry_id, "/video_list")
    if response == None:
        return

    if response.status_code != 200:
        self.rasp_output_lb.setText(
            f"Error requiring the list of recorded video (status code: {response.status_code})")
        return
    if "video_list" not in response.json():
        self.rasp_output_lb.setText(f"Error requiring the list of recorded video")
        return

    return sorted(list(response.json()["video_list"]))



def download_videos(self, raspberry_id, download_dir=""):
    """
    download all video from Raspberry Pi
    """

    def thread_progress(output):
        self.rasp_output_lb.setText(output)

    def thread_finished(downloaded_video_list):
        self.rasp_output_lb.setText(f"{len(downloaded_video_list)} videos downloaded in <b>{download_dir}</b>")
        self.video_list_clicked()
        self.video_download_thread.quit

    '''
    if download_dir == "":
        download_dir = cfg.VIDEO_ARCHIVE

    if not pl.Path(download_dir).is_dir():
        QMessageBox.critical(None, "Raspberry Pi coordinator",
                                f"Destination not found!<br>{cfg.VIDEO_ARCHIVE}<br><br>Choose another directory",
                                QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)

        new_download_dir = QFileDialog().getExistingDirectory(self,
                                                                "Choose a directory to download videos",
                                                                str(pathlib.Path.home()),
                                                                options=QFileDialog.ShowDirsOnly)
        if new_download_dir:
            download_dir = new_download_dir
        else:
            return
    '''

    remote_video_list = video_list(self, raspberry_id)
    video_list_to_download = []

    for idx in range(self.video_list_lw.count()):
        if self.video_list_lw.item(idx).checkState() == Qt.Checked:
            for video_file_name, video_size in remote_video_list:
                if self.video_list_lw.item(idx).text() == video_file_name:
                    video_list_to_download.append((video_file_name, video_size))
                    break

    # get video archive dir
    response = self.request(raspberry_id, "/video_archive_dir")
    if response == None:
        return
    if response.status_code != 200:
        self.rasp_output_lb.setText(
            f"Error requiring the video archive dir (status code: {response.status_code})")
        return
    if response.json().get("error", True):
        self.rasp_output_lb.setText(f"Error requiring the video archive dir")
        return
    remote_video_archive_dir = response.json().get("msg", "")


    self.video_download_thread = QThread(parent=self)
    self.video_download_thread.start()
    self.video_download_worker = Download_videos_worker(self.raspberry_ip)
    self.video_download_worker.moveToThread(self.video_download_thread)

    self.video_download_worker.start.connect(self.video_download_worker.run)
    self.video_download_worker.progress.connect(thread_progress)
    self.video_download_worker.finished.connect(thread_finished)
    self.video_download_worker.start.emit(raspberry_id, video_list_to_download, download_dir, remote_video_archive_dir)



def delete_videos(self, raspberry_id):
    """
    delete video from Raspberry Pi
    """
    self.rasp_output_lb.setText("Deletion of videos requested")

    remote_video_list = video_list(self, raspberry_id)
    video_list_to_delete = []

    for idx in range(self.video_list_lw.count()):
        if self.video_list_lw.item(idx).checkState() == Qt.Checked:
            for video_file_name, video_size in remote_video_list:
                if self.video_list_lw.item(idx).text() == video_file_name:
                    video_list_to_delete.append((video_file_name, video_size))
                    break

    response = self.request(raspberry_id, "/delete_video", data={"video list": json.dumps(video_list_to_delete)})
    if response == None:
        return

    if response.status_code != 200:
        self.rasp_output_lb.setText(f"Error deleting the video (status code: {response.status_code})")
        return

    self.all_video_cb.setCheckState(False)
    self.all_new_video_cb.setCheckState(False)
    self.rasp_output_lb.setText(response.json().get("msg", "Error during deleting the video"))
    self.video_list_clicked()
    self.get_raspberry_status(raspberry_id)
    self.update_raspberry_display(raspberry_id)