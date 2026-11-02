#!/usr/bin/env python3
"""READ-ONLY probe #5: hidraw only, no detach, GET_REPORT only. Run as root.
Reads each report 3x on IF0 (wIndex 0) and IF1 (wIndex 1) with exact lengths to check stability.
Saves 472-byte group settings to ~/tarantula-re/dumps/hidraw_if<N>_group.bin.
"""
import errno, fcntl, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe import hidraw_for, IOC  # noqa

OUT = '/home/examiner/tarantula-re/dumps'
REPORTS = ((6, 8, 'FWVERSION'), (5, 8, 'PROFILEID'), (2, 8, 'RESULT'), (3, 0x1d8, 'GROUP_SETTING'))

def xor(b):
    r = 0
    for x in b:
        r ^= x
    return r

def verdict(d):
    if not any(d):
        return 'ALL ZERO'
    return 'cs ok' if d[-2] == xor(d[:-2:2]) and d[-1] == xor(d[1:-2:2]) else 'cs BAD'

def getf(fd, rid, length):
    buf = bytearray(length); buf[0] = rid
    try:
        n = fcntl.ioctl(fd, IOC(3, 'H', 0x07, length), buf, True)
        return bytes(buf[:n]), None
    except OSError as e:
        return None, errno.errorcode.get(e.errno, str(e.errno))

for intf in (0, 1):
    path = hidraw_for(intf)
    print(f'== IF{intf} {path}')
    fd = os.open(path, os.O_RDWR)
    for rid, ln, name in REPORTS:
        for attempt in range(3):
            d, err = getf(fd, rid, ln)
            if err:
                print(f'  {name:13s} #{attempt}: {err}')
                continue
            print(f'  {name:13s} #{attempt}: {verdict(d):8s} {d[:16].hex(" ")}')
            if ln > 8 and any(d):
                f = os.path.join(OUT, f'hidraw_if{intf}_group.bin')
                open(f, 'wb').write(d); os.chown(f, 1000, 1000)
    os.close(fd)
