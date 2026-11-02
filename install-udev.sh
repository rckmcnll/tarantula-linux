#!/bin/sh
# Give the logged-in user access to the Razer Tarantula hidraw nodes (no sudo needed for tarantula.py).
set -e
RULE=/etc/udev/rules.d/70-razer-tarantula.rules
echo 'KERNEL=="hidraw*", ATTRS{idVendor}=="1532", ATTRS{idProduct}=="0102", TAG+="uaccess"' | sudo tee "$RULE"
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw --action=change
sleep 1
ls -l /dev/hidraw*
