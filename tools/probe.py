#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""READ-ONLY probe of the Razer Tarantula (1532:0102) hidden HID reports.

Only issues HID GET_REPORT requests (via hidraw HIDIOCGFEATURE / HIDIOCGINPUT).
Never sends SET_REPORT. Run as root:  sudo python3 -I probe.py
"""
import errno, fcntl, glob, os, sys

def IOC(d, t, nr, size):
    return (d << 30) | (size << 16) | (ord(t) << 8) | nr

def hidraw_for(intf):
    for h in sorted(glob.glob('/sys/class/hidraw/hidraw*')):
        dev = os.path.realpath(os.path.join(h, 'device'))
        if ':1532:0102.' in dev.upper().replace('0003:', ':') or '1532:0102' in dev.upper():
            if os.path.basename(os.path.dirname(dev)).endswith(f':1.{intf}'):
                return '/dev/' + os.path.basename(h)
    return None

def get(fd, kind, rid, length):
    nr = {'feature': 0x07, 'input': 0x0A}[kind]
    buf = bytearray(length + 1)
    buf[0] = rid
    try:
        n = fcntl.ioctl(fd, IOC(3, 'H', nr, len(buf)), buf, True)
        return bytes(buf[:n]) if n >= 0 else None, None
    except OSError as e:
        return None, errno.errorcode.get(e.errno, str(e.errno))

def cs_ok(p):
    return len(p) >= 8 and p[6] == p[0] ^ p[2] ^ p[4] and p[7] == p[1] ^ p[3] ^ p[5]

def main():
    for intf in (0, 1):
        path = hidraw_for(intf)
        print(f'== interface {intf}: {path}')
        if not path:
            continue
        fd = os.open(path, os.O_RDWR)
        for rid, ln in ((2, 8), (5, 8), (6, 8), (8, 8), (3, 0x1d8)):
            for kind in ('feature', 'input'):
                data, err = get(fd, kind, rid, ln)
                if err:
                    print(f'  id {rid} {kind:7s}: {err}')
                    continue
                body = data[1:] if data and data[0] == rid else data
                extra = f' checksum={"ok" if cs_ok(body) else "no"}' if ln == 8 else ''
                print(f'  id {rid} {kind:7s}: {len(data)} bytes{extra}')
                for i in range(0, len(data), 32):
                    print('    ' + data[i:i + 32].hex(' '))
        os.close(fd)


if __name__ == '__main__':
    main()
