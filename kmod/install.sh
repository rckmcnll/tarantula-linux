#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Install tarantula_ctl via DKMS (signed with the enrolled DKMS MOK key, rebuilt on kernel updates),
# load it, autoload at boot, and give the logged-in user access to /dev/tarantula.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
NAME=tarantula-ctl
VER=1.0

if dkms status -m $NAME -v $VER | grep -q .; then
    sudo dkms remove -m $NAME -v $VER --all
fi
sudo rm -rf /usr/src/$NAME-$VER
sudo mkdir -p /usr/src/$NAME-$VER
sudo cp "$SRC"/tarantula_ctl.c "$SRC"/tarantula_ctl.h "$SRC"/Makefile "$SRC"/dkms.conf /usr/src/$NAME-$VER/
sudo dkms add -m $NAME -v $VER
sudo dkms build -m $NAME -v $VER
sudo dkms install -m $NAME -v $VER

echo 'KERNEL=="tarantula", SUBSYSTEM=="misc", TAG+="uaccess"' | sudo tee /etc/udev/rules.d/71-tarantula-ctl.rules >/dev/null
echo tarantula_ctl | sudo tee /etc/modules-load.d/tarantula_ctl.conf >/dev/null
sudo udevadm control --reload-rules

sudo modprobe -r tarantula_ctl 2>/dev/null || true
sudo modprobe tarantula_ctl
sleep 1
modinfo tarantula_ctl | grep -E '^(filename|signer|sig_key)'
ls -l /dev/tarantula
getfacl -p /dev/tarantula 2>/dev/null | grep "user:$USER" || echo "note: ACL for $USER not shown (log out/in if access is denied)"
