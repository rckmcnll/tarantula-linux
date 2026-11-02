#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""READ-ONLY probe #2: replicate the Windows driver's exact HID class GET_REPORT URBs
(bmRequestType 0xA1, bRequest 0x01, wValue = 0x00<id>, i.e. report type 0) via usbfs.

Interface 0 (the keyboard) is detached from usbhid for ~1 s and always reattached.
Only GET requests are sent; nothing is written to the keyboard. Run as root.
"""
import ctypes, errno, fcntl, glob, os, struct

def IOC(d, nr, size):
    return (d << 30) | (size << 16) | (ord('U') << 8) | nr

class Ctrl(ctypes.Structure):
    _fields_ = [('bRequestType', ctypes.c_uint8), ('bRequest', ctypes.c_uint8),
                ('wValue', ctypes.c_uint16), ('wIndex', ctypes.c_uint16),
                ('wLength', ctypes.c_uint16), ('timeout', ctypes.c_uint32),
                ('data', ctypes.c_void_p)]

class UIoctl(ctypes.Structure):
    _fields_ = [('ifno', ctypes.c_int), ('ioctl_code', ctypes.c_int), ('data', ctypes.c_void_p)]

CONTROL = IOC(3, 0, ctypes.sizeof(Ctrl))
CLAIM = IOC(2, 15, 4)
RELEASE = IOC(2, 16, 4)
USBIOCTL = IOC(3, 18, ctypes.sizeof(UIoctl))
DISCONNECT = IOC(0, 22, 0)
CONNECT = IOC(0, 23, 0)

def find_dev():
    for d in glob.glob('/sys/bus/usb/devices/*'):
        try:
            if open(d + '/idVendor').read().strip() == '1532' and open(d + '/idProduct').read().strip() == '0102':
                b, n = int(open(d + '/busnum').read()), int(open(d + '/devnum').read())
                return f'/dev/bus/usb/{b:03d}/{n:03d}'
        except OSError:
            pass
    raise SystemExit('Tarantula 1532:0102 not found')

def kernel_ioctl(fd, ifno, code):
    u = UIoctl(ifno, code, None)
    try:
        fcntl.ioctl(fd, USBIOCTL, u)
        return 'ok'
    except OSError as e:
        return errno.errorcode.get(e.errno, str(e.errno))

def get_report(fd, value, index, length):
    buf = ctypes.create_string_buffer(length)
    c = Ctrl(0xA1, 0x01, value, index, length, 1000, ctypes.cast(buf, ctypes.c_void_p))
    try:
        n = fcntl.ioctl(fd, CONTROL, c)
        return buf.raw[:n], None
    except OSError as e:
        return None, errno.errorcode.get(e.errno, str(e.errno))

def cs_ok(p):
    return len(p) >= 8 and p[6] == p[0] ^ p[2] ^ p[4] and p[7] == p[1] ^ p[3] ^ p[5]

def main():
    path = find_dev()
    print('device', path)
    fd = os.open(path, os.O_RDWR)
    results = []
    try:
        print('detach usbhid from IF0:', kernel_ioctl(fd, 0, DISCONNECT))
        fcntl.ioctl(fd, CLAIM, struct.pack('I', 0))
        for name, value, length in (('GET_FWVERSION', 0x0006, 8), ('GET_PROFILEID', 0x0005, 8),
                                    ('GET_RESULT', 0x0002, 8), ('GET_GROUP_SETTING[0]', 0x0003, 0x1d8),
                                    ('GET_FWVERSION type=feature', 0x0306, 8)):
            results.append((name, value) + get_report(fd, value, 0, length))
    finally:
        try:
            fcntl.ioctl(fd, RELEASE, struct.pack('I', 0))
        except OSError:
            pass
        print('reattach usbhid to IF0:', kernel_ioctl(fd, 0, CONNECT))
        os.close(fd)

    for name, value, data, err in results:
        if err:
            print(f'{name:28s} wValue=0x{value:04x}: {err}')
            continue
        extra = f' checksum={"ok" if cs_ok(data) else "no"}' if len(data) == 8 else ''
        print(f'{name:28s} wValue=0x{value:04x}: {len(data)} bytes{extra}')
        for i in range(0, len(data), 32):
            print('    ' + data[i:i + 32].hex(' '))


if __name__ == '__main__':
    main()
