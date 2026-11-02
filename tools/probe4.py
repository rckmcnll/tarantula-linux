#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""READ-ONLY probe #4 (GET_REPORT only). Run as root.
1) GET_FWVERSION with interface recipient wIndex=1 (IF1 detached briefly): does fw answer on wIndex!=0?
2) GET_GROUP_SETTING wIndex=0 again (IF0 detached ~1s): reproducible?
3) hidraw HIDIOCGFEATURE with exact 8-byte length (no detach): usable without usbfs?
"""
import ctypes, errno, fcntl, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_usbfs import Ctrl, CONTROL, CLAIM, RELEASE, DISCONNECT, CONNECT, find_dev, kernel_ioctl  # noqa
from probe import hidraw_for, IOC  # noqa

def get(fd, rtype, value, index, length):
    buf = ctypes.create_string_buffer(length)
    c = Ctrl(rtype, 0x01, value, index, length, 1000, ctypes.cast(buf, ctypes.c_void_p))
    try:
        return buf.raw[:fcntl.ioctl(fd, CONTROL, c)], None
    except OSError as e:
        return None, errno.errorcode.get(e.errno, str(e.errno))

def show(label, data, err):
    if err:
        print(f'{label}: {err}')
    elif not any(data):
        print(f'{label}: {len(data)} bytes ALL ZERO')
    else:
        print(f'{label}: {len(data)} bytes  {data[:16].hex(" ")}{" ..." if len(data) > 16 else ""}')

def with_intf(fd, intf, fn):
    try:
        kernel_ioctl(fd, intf, DISCONNECT)
        fcntl.ioctl(fd, CLAIM, struct.pack('I', intf))
        return fn()
    finally:
        try:
            fcntl.ioctl(fd, RELEASE, struct.pack('I', intf))
        except OSError:
            pass
        print(f'  (IF{intf} reattach: {kernel_ioctl(fd, intf, CONNECT)})')

fd = os.open(find_dev(), os.O_RDWR)
r = with_intf(fd, 1, lambda: [get(fd, 0xA1, 0x0006, 1, 8), get(fd, 0xA1, 0x0005, 1, 8)])
show('1) GET_FWVERSION wIndex=1', *r[0])
show('1) GET_PROFILEID wIndex=1', *r[1])
r = with_intf(fd, 0, lambda: [get(fd, 0xA1, 0x0006, 0, 8), get(fd, 0xA1, 0x0003, 0, 0x1d8)])
show('2) GET_FWVERSION wIndex=0', *r[0])
show('2) GET_GROUP_SETTING wIndex=0', *r[1])
os.close(fd)

h = hidraw_for(0)
hfd = os.open(h, os.O_RDWR)
for rid in (6, 5):
    buf = bytearray(8); buf[0] = rid
    try:
        n = fcntl.ioctl(hfd, IOC(3, 'H', 0x07, 8), buf, True)
        show(f'3) hidraw {h} feature id {rid} len 8', bytes(buf[:n]), None)
    except OSError as e:
        show(f'3) hidraw {h} feature id {rid} len 8', None, errno.errorcode.get(e.errno))
os.close(hfd)
