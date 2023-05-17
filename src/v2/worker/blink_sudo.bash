#!/bin/bash

# https://raspberrypi.stackexchange.com/questions/70013/raspberry-pi-3-model-b-system-leds

echo gpio | sudo tee /sys/class/leds/led1/trigger

# (Optional) Turn on (1) or off (0) the PWR LED.


for i in {1..10}; do
    echo 0 | sudo tee /sys/class/leds/led1/brightness;
    sleep 0.5;
    echo 1 | sudo tee /sys/class/leds/led1/brightness;
    sleep 0.5;
    done

# Revert the PWR LED back to 'under-voltage detect' mode.
echo input | sudo tee /sys/class/leds/led1/trigger
