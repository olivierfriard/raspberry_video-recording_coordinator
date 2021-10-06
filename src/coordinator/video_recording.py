"""
Raspberry Pi coordinator

video recording module
"""

from PyQt5.QtWidgets import (QMessageBox, QTableWidgetItem)


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
