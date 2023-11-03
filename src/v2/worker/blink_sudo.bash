#!/bin/bash

# https://raspberrypi.stackexchange.com/questions/70013/raspberry-pi-3-model-b-system-leds

#echo gpio | sudo tee /sys/class/leds/led1/trigger
sudo sh -c 'echo input > /sys/class/leds/PWR/trigger'


# (Optional) Turn on (1) or off (0) the PWR LED.


for i in {1..10}; do
    # echo 0 | sudo tee /sys/class/leds/led1/brightness;
    sudo sh -c 'echo 0 > /sys/class/leds/PWR/brightness'
    sleep 0.5;
    # echo 1 | sudo tee /sys/class/leds/led1/brightness;
    sudo sh -c 'echo 1 > /sys/class/leds/PWR/brightness'
    sleep 0.5;
    done

# Revert the PWR LED back to 'under-voltage detect' mode.
# echo input | sudo tee /sys/class/leds/led1/trigger
sudo sh -c 'echo none > /sys/class/leds/PWR/trigger'
