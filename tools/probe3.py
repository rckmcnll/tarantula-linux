#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""READ-ONLY probe #3 (GET_REPORT only, nothing is written to the keyboard).

A) Device-recipient GETs (bmRequestType 0xA0): needs no detach at all.
   GET_FWVERSION, then GET_GROUP_SETTING for wIndex = profile 0..5.
B) Reference: interface-recipient (0xA1) GET_GROUP_SETTING wIndex=1, which requires
   briefly detaching usbhid from IF1 (media/power keys only; typing is unaffected).
Saves every 472-byte block to ~/tarantula-re/dumps/. Run as root.
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_usbfs import Ctrl, CONTROL, CLAIM, RELEASE, DISCONNECT, CONNECT, find_dev, kernel_ioctl, cs_ok  # noqa
import ctypes, errno, fcntl

OUT = '/home/examiner/tarantula-re/dumps'

def get(fd, rtype, value, index, length):
    buf = ctypes.create_string_buffer(length)
    c = Ctrl(rtype, 0x01, value, index, length, 1000, ctypes.cast(buf, ctypes.c_void_p))
    try:
        return buf.raw[:fcntl.ioctl(fd, CONTROL, c)], None
    except OSError as e:
        return None, errno.errorcode.get(e.errno, str(e.errno))

def show(label, data, err, save=None):
    if err:
        print(f'{label}: {err}'); return
    ok = cs_ok(data) if len(data) == 8 else (data[-2] == xor(data[:-2:2]) and data[-1] == xor(data[1:-2:2]))
    print(f'{label}: {len(data)} bytes checksum={"ok" if ok else "BAD"}  head={data[:8].hex(" ")}')
    if save:
        open(os.path.join(OUT, save), 'wb').write(data)
        os.chown(os.path.join(OUT, save), 1000, 1000)

def xor(b):
    r = 0
    for x in b:
        r ^= x
    return r

fd = os.open(find_dev(), os.O_RDWR)
print('-- A: device recipient (0xA0), no detach')
show('GET_FWVERSION', *get(fd, 0xA0, 0x0006, 0, 8))
show('GET_PROFILEID', *get(fd, 0xA0, 0x0005, 0, 8))
for p in range(6):
    show(f'GET_GROUP_SETTING profile {p}', *get(fd, 0xA0, 0x0003, p, 0x1d8), save=f'devrecip_profile{p}.bin')

print('-- B: interface recipient (0xA1) wIndex=1, IF1 detached briefly')
res = (None, 'not run')
try:
    print('detach IF1:', kernel_ioctl(fd, 1, DISCONNECT))
    fcntl.ioctl(fd, CLAIM, struct.pack('I', 1))
    res = get(fd, 0xA1, 0x0003, 1, 0x1d8)
finally:
    try:
        fcntl.ioctl(fd, RELEASE, struct.pack('I', 1))
    except OSError:
        pass
    print('reattach IF1:', kernel_ioctl(fd, 1, CONNECT))
show('GET_GROUP_SETTING profile 1 (0xA1)', *res, save='intfrecip_profile1.bin')
os.close(fd)

a, b = os.path.join(OUT, 'devrecip_profile1.bin'), os.path.join(OUT, 'intfrecip_profile1.bin')
if os.path.exists(a) and os.path.exists(b):
    print('device-recipient == interface-recipient for profile 1:', open(a, 'rb').read() == open(b, 'rb').read())
