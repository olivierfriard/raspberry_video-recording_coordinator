"""
Raspberry Pi configurator

notes:
predictable network interface names
sudo iw dev wlx74da38de4952

wifi access list for windows:
https://stackoverflow.com/questions/31868486/list-all-wireless-networks-python-for-pc


current wifi access point:
https://stackoverflow.com/questions/19575444/find-name-of-current-wifi-network-on-windows

ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no pi@192.168.1.4

"""

__version__ = '1'
__version_date__ = "2021-09-18"

import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QPushButton,
                             QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPlainTextEdit,
                             QInputDialog)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot

import getpass
import os
import subprocess
import pathlib

class Rpi_configurator(QMainWindow):

    def __init__(self):
        super().__init__()
        self.title = 'Raspberry Pi configurator'
        self.left = 100
        self.top = 100
        self.width = 640
        self.height = 480
        self.initUI()

        self.rpi_device = ""


    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        vl = QVBoxLayout()

        vl.addWidget(QPushButton('Detect Raspberry Pi SD card', self, clicked=self.detect_rpi_sd_card))
        self.rpi_detected = QPlainTextEdit("")
        vl.addWidget(self.rpi_detected)

        hl = QHBoxLayout()

        self.hostname_lb = QLabel("Raspberry Pi hostname")
        self.hostname_lb.setEnabled(False)
        hl.addWidget(self.hostname_lb)

        self.hostname_le = QLineEdit()
        self.hostname_le.setEnabled(False)
        hl.addWidget(self.hostname_le)

        self.hostname_btn = QPushButton("Set hostname", self, clicked=self.set_hostname)
        self.hostname_btn.setEnabled(False)
        hl.addWidget(self.hostname_btn)

        vl.addLayout(hl)

        hl = QHBoxLayout()

        self.wifi_lb = QLabel("WiFi network")
        self.wifi_lb.setEnabled(False)
        hl.addWidget(self.wifi_lb)

        self.essid_le = QLineEdit()
        self.essid_le.setEnabled(False)
        hl.addWidget(self.essid_le)

        self.wifi_passwd_le = QLineEdit()
        self.wifi_passwd_le.setEnabled(False)
        hl.addWidget(self.wifi_passwd_le)


        self.wifi_country_le = QLineEdit()
        self.wifi_country_le.setEnabled(False)
        hl.addWidget(self.wifi_country_le)


        self.wifi_btn = QPushButton("Configure WiFi", self, clicked=self.wifi_config)
        self.wifi_btn.setEnabled(False)
        hl.addWidget(self.wifi_btn)

        vl.addLayout(hl)

        hl = QHBoxLayout()

        self.security_key_lb = QLabel("Security key")
        self.security_key_lb.setEnabled(False)
        hl.addWidget(self.security_key_lb)

        self.security_key_le = QLineEdit()
        self.security_key_le.setEnabled(False)
        hl.addWidget(self.security_key_le)

        self.key_btn = QPushButton("Set key", self, clicked=self.set_security_key)
        self.key_btn.setEnabled(False)
        hl.addWidget(self.key_btn)

        vl.addLayout(hl)


        main_widget = QWidget(self)
        main_widget.setLayout(vl)

        self.setCentralWidget(main_widget)

        self.show()


    def button_status(self, action):
        """
        Change widget status (enable/disable)
        """
        for wdgt in [self.hostname_btn, self.hostname_le, self.hostname_lb,
                     self.wifi_lb, self.essid_le, self.wifi_passwd_le, self.wifi_country_le, self.wifi_btn,
                     self.security_key_lb,  self.security_key_le, self.key_btn]:
            wdgt.setEnabled(action=="enable")


    @pyqtSlot()
    def detect_rpi_sd_card(self):
        """
        Detect if a Raspberry Pi SD card is inserted
        """

        # print("currentuser:", getpass.getuser())
        current_user = getpass.getuser()

        if sys.platform.startswith("linux"):
            if os.path.ismount(f"/media/{current_user}/boot"):

                out = f"Raspberry Pi SD card found in /media/{current_user}/boot\n"

                self.rpi_device = pathlib.Path(f"/media/{current_user}/boot")

                self.button_status("enable")

                # check current hostname on other partition
                try:
                    with open(f"/media/{current_user}/rootfs/etc/hostname", "r") as file_in:
                        hostname = file_in.read().strip()
                        self.hostname_le.setText(hostname)
                except Exception:
                    hostname = ""
                out += f"\nCurrent hostname: {hostname}"

                # check current wifi network on other partition
                try:
                    with open(f"/media/{current_user}/rootfs/etc/wpa_supplicant/wpa_supplicant.conf", "r") as file_in:
                        wpa_supplicant = file_in.read()
                except Exception:
                    wpa_supplicant = "None"
                out += f"\n\nCurrent WiFi network configuration:\n{wpa_supplicant}\n"

                # security key
                try:
                    with open(f"/media/{current_user}/boot/worker_security_key", "r") as file_in:
                        security_key = file_in.read().strip()
                        self.security_key_le.setText(security_key)
                except Exception:
                    security_key = ""
                out += f"\nCurrent hostname: {security_key}"


                self.rpi_detected.setPlainText(out)
            else:
                self.rpi_detected.setPlainText(f"No Raspberry Pi SD card found")


        if sys.platform.startswith('win'):
            self.rpi_device = ""
            drvArr = ['c:', 'd:', 'e:', 'f:', 'g:', 'h:', 'i:', 'j:', 'k:', 'l:']
            for dl in drvArr:
                try:
                    if (os.path.isdir(dl) != 0):
                        val = subprocess.check_output(["cmd", "/c vol " + dl])
                        if ('is boot' in str(val)) and (pathlib.Path(dl) / pathlib.Path("cmdline.txt")).is_file():
                            self.rpi_device = pathlib.Path(dl)
                            out = f"Raspberry Pi SD card found in {dl}"

                            self.button_status("enable")
                            break
                except:
                    print("Error: findDriveByDriveLabel(): exception")
            else:
                out = "No Raspberry Pi SD card found"

            self.rpi_detected.setPlainText(out)


    @pyqtSlot()
    def set_hostname(self):
        """
        Set hostname
        hostname is defined in the /boot/hostname and set during execution of /et
        """
        if "_" in self.hostname_le.text():
            return

        if " " in self.hostname_le.text():
            return

        try:
            with open(self.rpi_device / "hostname", "w") as f_out:
                f_out.write(self.hostname_le.text())
        except Exception:
            print("Error writing /boot/hostname file")


    @pyqtSlot()
    def set_security_key(self):
        """
        Set security key
        """
        if not self.security_key_le.text():
            (self.rpi_device / pathlib("worker_security_key")).unlink(missing_ok = True)
            return
        try:
            with open(self.rpi_device / "worker_security_key", "w") as f_out:
                f_out.write(self.security_key_le.text())
        except Exception:
            print("Error writing /boot/worker_security_key file")


    @pyqtSlot()
    def wifi_config(self):
        '''
        wifi_name, ok = QInputDialog().getText(self, "WiFi Network ", "name:", QLineEdit.Normal, "")
        if not ok or not wifi_name:
            return
        wifi_password, ok = QInputDialog().getText(self, "WiFi Network ", "Password", QLineEdit.Normal, "")
        if not ok or not wifi_password:
            return
        wifi_country, ok = QInputDialog().getText(self, "WiFi Network ", "Country (2 letters code)", QLineEdit.Normal, "")
        if not ok or not wifi_country:
            return
        '''

        wpa_template = f"""country={self.wifi_country_le.text()}
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
ssid="{self.essid_le.text()}"
psk="{self.wifi_passwd_le.text()}"
key_mgmt=WPA-PSK
}}
"""
        try:
            with open(self.rpi_device / "wpa_supplicant.conf", "w") as f_out:
                f_out.write(wpa_template)
        except Exception:
            print("Error writing wpa file")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Rpi_configurator()
    sys.exit(app.exec_())
