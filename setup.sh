#!/bin/bash

# TODO add an option for pip and or virtual env setup
apt-get update && \
apt-get install python3-smbus2 wiringpi
cp ./init/lcdops /etc/init.d
cp ./init/librespot /etc/init.d

echo "dtoverlay=audremap,pins_12_13 # for pins 12 and 13" > /etc/default/raspi-firmware-custom
echo "This will take a while..."
update-initramfs -u -k all 

service librespot start
service lcdops start
