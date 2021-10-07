"""
time lapse module
"""

from PyQt5.QtWidgets import (QMessageBox, QTableWidgetItem, )

def schedule_time_lapse(self, raspberry_id):
    """
    Schedule the picture taking on the Raspberry Pi
    """

    if self.picture_hours_le.text() == "":
        QMessageBox.information(None, "Raspberry Pi coordinator",
                                f"Specify the hour(s) to start time lapse",
                                QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
        return

    if self.picture_minutes_le.text() == "":
        QMessageBox.information(None, "Raspberry Pi coordinator",
                                f"Specify the minutes(s) to start time lapse",
                                QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
        return

    if self.picture_days_of_week_le.text() == "":
        QMessageBox.information(None, "Raspberry Pi coordinator",
                                f"Specify the day(s) of the week to start time lapse (0-6 or SUN-SAT)",
                                QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
        return

    if self.picture_days_of_month_le.text() == "":
        QMessageBox.information(None, "Raspberry Pi coordinator",
                                f"Specify the day(s) of the month to start time lapse (1-31)",
                                QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
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
            QMessageBox.information(None, "Raspberry Pi coordinator",
                                f"The hour(s) format is not correct. Example; 1,2,13,15 or *",
                                QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
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
            QMessageBox.information(None, "Raspberry Pi coordinator",
                                f"The minutes(s) format is not correct. Example; 1,2,13,15 or *",
                                QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
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
            QMessageBox.information(None, "Raspberry Pi coordinator",
                                f"The day(s) of month format is not correct. Example; 1,2,13,15 or *",
                                QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
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
            QMessageBox.information(None, "Raspberry Pi coordinator",
                                f"The month format is not correct. Example; 1,2,12 or *",
                                QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)
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
                QMessageBox.information(None, "Raspberry Pi coordinator",
                                f"The days(s) of week format is not correct. Example; 0,1,2 or SUN,MON,TUE",
                                QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)

        dow_str = ",".join([str(x) for x in int_dow_splt])

    crontab_event = f"{minutes_str} {hours_str} {dom_str} {month_str} {dow_str}"

    width, height = self.raspberry_info[raspberry_id]['picture resolution'].split("x")
    data = {"crontab": crontab_event,
            "timelapse": self.raspberry_info[raspberry_id]['time lapse wait'],
            "timeout": self.raspberry_info[raspberry_id]['time lapse duration'],

            "width": width, "height": height,
            "brightness": self.raspberry_info[raspberry_id]['picture brightness'],
            "contrast": self.raspberry_info[raspberry_id]['picture contrast'],
            "saturation": self.raspberry_info[raspberry_id]['picture saturation'],
            "sharpness": self.raspberry_info[raspberry_id]['picture sharpness'],
            "ISO": self.raspberry_info[raspberry_id]['picture iso'],
            "rotation": self.raspberry_info[raspberry_id]['picture rotation'],
            "hflip": self.raspberry_info[raspberry_id]['picture hflip'],
            "vflip": self.raspberry_info[raspberry_id]['picture vflip'],
            "annotate": self.raspberry_info[raspberry_id]['picture annotation'],
            }

    response = self.request(raspberry_id, f"/schedule_time_lapse",
                            data=data)
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
        self.rasp_output_lb.setText(f"Error during view of the time lapse scheduling (status code: {response.status_code})")
        return

    crontab_content = response.json().get("msg", "")

    self.time_lapse_schedule_table.setRowCount(len(crontab_content))
    for i in range(0, len(crontab_content)):
        tokens = crontab_content[i]
        for j in range(0, 5 +1):
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
        self.rasp_output_lb.setText(f"Error during deletion of the time lapse scheduling (status code: {response.status_code})")
        return
    self.rasp_output_lb.setText(response.json().get("msg", "Error during deletion of the time lapse scheduling"))

    self.view_time_lapse_schedule_clicked()
