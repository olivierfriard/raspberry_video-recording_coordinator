#!/usr/bin/env python3

# Raspberry Pi configuration script


import time
import sys
import os
import subprocess
import json

if os.path.isfile("/home/pi/raspberry_configuration.json"):
    print("Raspberry Pi configuration already done")
    print("Remove the raspberry_configuration.json file to reset")
    sys.exit()


os.system("clear")

print("Configuration of the Raspberry Pi")
print("=================================")
print()

# ask user the Raspberry Pi ID
while True:
    raspberry_id = input("Input the Raspberry Pi ID (no spaces): ")
    if ' ' in raspberry_id:
        continue
    r = input("\nConfirm '{raspberry_id}' ? [y/n] ".format(raspberry_id=raspberry_id)).upper()
    if r == 'Y':
        break


# save hostname
with open("/tmp/hostname", "w") as f:
    print(raspberry_id, file=f)

r = subprocess.getoutput('sudo mv /tmp/hostname /etc/hostname')




print("\nThe Raspberry Pi ID was set to: ", raspberry_id)


# WiFi
print("\nWiFi activation\n")
os.system("sudo rfkill unblock wlan")

r = subprocess.getoutput('sudo iwlist wlan0 scan | grep ESSID | sort | uniq')

wifi_dict = dict([(idx + 1, x.replace("ESSID:", "").replace('"', '').replace(" ", "")) for idx, x in enumerate(r.split("\n"))])

# print(wifi_dict)


while True:

    print("Available WiFi:")

    for idx in wifi_dict:
        print("{idx}: {wifi}".format(idx=idx, wifi=wifi_dict[idx]))

    print("\nq: Cancel\n")

    wifi_choice = input("Choose WiFi: ")
    if wifi_choice.upper() == 'Q':
        sys.exit()

    try:
        if int(wifi_choice) in wifi_dict:
            break
        else:
            print("\n{wifi_choice} not found!\n".format(wifi_choice=wifi_choice))
    except Exception:
        print("\nChoose a number!\n")


selected_wifi = wifi_dict[int(wifi_choice)]

print(f"WiFi selected: {selected_wifi}".format(selected_wifi=selected_wifi))

wifi_password = input("\nWiFi password: ")

while True:
    wifi_country = input("\nWiFi country (2 letters country code, q to quit): ").upper()
    if wifi_country == 'Q':
        sys.exit()

    if len(wifi_country) != 2:
        print("\nThe country code must be 2 letters long!")
    else:
        r = input("\nConfirm '{wifi_country}' ? [y/n]".format(wifi_country=wifi_country)).upper()
        if r == 'Y':
            break






wpa_template = """ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=###WIFI_COUNTRY###

network={
        ssid="###SELECTED_WIFI###"
        psk="###WIFI_PASSWORD###"
}

"""


wpa_supplicant_content  = wpa_template.replace("###WIFI_COUNTRY###", wifi_country).replace("###WIFI_PASSWORD###", wifi_password).replace("###SELECTED_WIFI###", selected_wifi)


with open("/tmp/wpa_supplicant.conf", "w") as f:
    print(wpa_supplicant_content, file=f)

r = subprocess.getoutput('sudo mv /tmp/wpa_supplicant.conf /etc/wpa_supplicant')

print("\nWiFi configuration done")


config = {"wifi": selected_wifi,
          "raspberry id": raspberry_id}

with open("/home/pi/raspberry_configuration.json", "w") as f:
    print(json.dumps(config), file=f)



print("\nRaspberry Pi configuration done successfully")


print("\nRebooting in 10 s")

time.sleep(10)


subprocess.getoutput('sudo reboot')



