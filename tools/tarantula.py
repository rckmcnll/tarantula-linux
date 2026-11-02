#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""tarantula.py - Linux config tool for the Razer Tarantula keyboard (USB 1532:0102).

Protocol reverse-engineered from the Razer v2.10 Windows driver (UsbFltr.sys + razerhid.exe).
Talks to the keyboard through /dev/hidraw (HID feature reports); no kernel driver detach needed.

  info                       firmware version, active profile, last result
  dump   [-p N] [--raw]      decode a profile block (N = 0 factory default, 1 user profile)
  backup -p N FILE           save the raw 472-byte block
  write  -p 1 FILE --yes     write a 472-byte block to the keyboard, then verify by reading back
  keys                       list internal key codes and names
  remap SRC DST [--yes]      make physical key SRC send DST (profile 1); dry run without --yes
  reset-keymap [--yes]       restore the identity key map (macros untouched)
  macro SLOT SPEC.. [--yes]  program macro key ML1..ML5/MR1..MR5, e.g.
                               macro ML3 lctrl+c            (Ctrl+C)
                               macro MR1 h e l l o wait:200 enter
                             --default restores the factory behaviour of that key
  Every write auto-backs-up the current profile to ~/tarantula-re/dumps/auto-*.bin first.

Transport: /dev/tarantula (kmod/tarantula_ctl, all profiles 1-5 + switch) if loaded,
otherwise hidraw (profiles 0/1 only, because wIndex = interface number = profile number).
  switch N                   make profile N the active one (kernel module only)
  maps                       show key maps A and B of each profile (* = active)
  remap/reset-keymap -m B    edit map B without activating it
  togglemap [-p N]           swap A/B now (what the profile key does)
  daemon                     run the profile-key listener (systemd user unit)
  -p N on dump/backup/write/remap/macro/reset-keymap selects the profile (default 1)
"""
import argparse, errno, fcntl, glob, os, struct, sys, time

VID_PID = '1532:0102'
BLOCK = 0x1d8            # 472 bytes
KEYMAP_OFF, KEYMAP_LEN = 6, 144     # internal key codes 0x10..0x9F
MACRO_OFF, MACRO_LEN, MACRO_SLOTS = 0x96, 32, 10
RID_FW, RID_PROFILEID, RID_RESULT, RID_GROUP = 6, 5, 2, 3
RID_GROUP_SET, RID_SET_PROFILEID = 1, 4
RESULT_BUSY = 0x01

# internal code -> key name; from razercfg.exe code->HID-usage table at file offset 0x3c9f8
KEYS = {
    0x10: '`',
    0x11: '1',
    0x12: 'Q',
    0x13: 'Tab',
    0x14: 'A',
    0x15: 'Esc',
    0x16: 'Z',
    0x17: 'Intl5',
    0x18: 'F1',
    0x19: '2',
    0x1a: 'W',
    0x1b: 'CapsLock',
    0x1c: 'S',
    0x1d: 'ISO\\',
    0x1e: 'X',
    0x1f: 'Lang2',
    0x20: 'F2',
    0x21: '3',
    0x22: 'E',
    0x23: 'F3',
    0x24: 'D',
    0x25: 'F4',
    0x26: 'C',
    0x27: 'Lang1',
    0x28: '5',
    0x29: '4',
    0x2a: 'R',
    0x2b: 'T',
    0x2c: 'F',
    0x2d: 'G',
    0x2e: 'V',
    0x2f: 'B',
    0x30: '6',
    0x31: '7',
    0x32: 'U',
    0x33: 'Y',
    0x34: 'J',
    0x35: 'H',
    0x36: 'M',
    0x37: 'N',
    0x38: '=',
    0x39: '8',
    0x3a: 'I',
    0x3b: ']',
    0x3c: 'K',
    0x3d: 'F6',
    0x3e: ',',
    0x3f: 'Intl1',
    0x40: 'F8',
    0x41: '9',
    0x42: 'O',
    0x43: 'F7',
    0x44: 'L',
    0x45: 'Intl4',
    0x46: '.',
    0x47: 'Intl2',
    0x48: '-',
    0x49: '0',
    0x4a: 'P',
    0x4b: '[',
    0x4c: ';',
    0x4d: "'",
    0x4e: 'ISO#',
    0x4f: '/',
    0x50: 'F9',
    0x51: 'F10',
    0x52: 'code52',
    0x53: 'Backspace',
    0x54: 'Intl3',
    0x55: 'F5',
    0x56: 'Enter',
    0x57: 'Space',
    0x58: 'Insert',
    0x59: 'F12',
    0x5a: 'KP8',
    0x5b: 'KP5',
    0x5c: 'KP2',
    0x5d: 'KP0',
    0x5e: 'KP/',
    0x5f: 'Right',
    0x60: 'Delete',
    0x61: 'F11',
    0x62: 'KP7',
    0x63: 'KP4',
    0x64: 'KP1',
    0x65: 'code65',
    0x66: 'NumLock',
    0x67: 'Down',
    0x68: 'PageUp',
    0x69: 'PageDown',
    0x6a: 'KP9',
    0x6b: 'KP6',
    0x6c: 'KP3',
    0x6d: 'KP.',
    0x6e: 'KP*',
    0x6f: 'KP-',
    0x70: 'Home',
    0x71: 'End',
    0x72: 'KP+',
    0x73: 'code73',
    0x74: 'KPEnter',
    0x75: 'Up',
    0x76: 'Pause',
    0x77: 'Left',
    0x78: 'code78',
    0x79: 'ScrollLock',
    0x7a: 'PrintScreen',
    0x7b: 'code7b',
    0x7c: 'code7c',
    0x7d: 'LAlt',
    0x7e: 'code7e',
    0x7f: 'RAlt',
    0x80: 'ML1',
    0x81: 'ML2',
    0x82: 'ML3',
    0x83: 'LShift',
    0x84: 'ML4',
    0x85: 'ML5',
    0x86: 'RShift',
    0x87: 'Profile',
    0x88: 'LCtrl',
    0x89: 'MR1',
    0x8a: 'MR2',
    0x8b: 'MR3',
    0x8c: 'MR4',
    0x8d: 'MR5',
    0x8e: 'RCtrl',
    0x8f: 'Mute',
    0x90: 'MediaSelect',
    0x91: 'PlayPause',
    0x92: 'VolDown',
    0x93: 'VolUp',
    0x94: 'code94',
    0x95: 'code95',
    0x96: 'VolUp_96',
    0x97: 'VolDown_97',
    0x98: 'code98',
    0x99: 'WWWHome',
    0x9a: 'Menu?',
    0x9b: 'code9b',
    0x9c: 'LWin?',
    0x9d: 'ZoomIn',
    0x9e: 'ZoomOut',
    0x9f: 'code9f',
}
NAME2CODE = {v.lower(): k for k, v in KEYS.items()}
NAME2CODE.update({'ctrl': 0x88, 'shift': 0x83, 'alt': 0x7d, 'win': 0x9c, 'super': 0x9c, 'menu': 0x9a,
                  'esc': 0x15, 'escape': 0x15, 'return': 0x56, 'caps': 0x1b, 'del': 0x60, 'ins': 0x58,
                  'pgup': 0x68, 'pgdn': 0x69, 'bksp': 0x53, 'lwin': 0x9c})


def _ioc(d, nr, size):
    return (d << 30) | (size << 16) | (ord('H') << 8) | nr

HIDIOCSFEATURE = lambda n: _ioc(3, 0x06, n)
HIDIOCGFEATURE = lambda n: _ioc(3, 0x07, n)


def xor(b):
    r = 0
    for x in b:
        r ^= x
    return r


def checksum_ok(d):
    return any(d) and d[-2] == xor(d[:-2:2]) and d[-1] == xor(d[1:-2:2])


def fix_checksum(d):
    d = bytearray(d)
    d[-2], d[-1] = xor(d[:-2:2]), xor(d[1:-2:2])
    return bytes(d)


def hidraw(intf):
    path = find_hidraw(intf)
    if path is None:
        sys.exit(f'Tarantula interface {intf} not found (is it plugged in?)')
    return path


def find_hidraw(intf):
    for h in sorted(glob.glob('/sys/class/hidraw/hidraw*')):
        dev = os.path.realpath(os.path.join(h, 'device'))
        if VID_PID.upper() in os.path.basename(dev).upper() and \
                os.path.basename(os.path.dirname(dev)).endswith(f':1.{intf}'):
            return '/dev/' + os.path.basename(h)
    return None


KMOD_DEV = '/dev/tarantula'
TAR_IOC_XFER = (3 << 30) | (16 << 16) | (ord('T') << 8) | 0x01   # _IOWR('T', 1, struct tarantula_xfer)
_kmod_fd = None


def kmod():
    """fd of /dev/tarantula (kernel module tarantula_ctl) or None."""
    global _kmod_fd
    if _kmod_fd is None and os.path.exists(KMOD_DEV):
        try:
            _kmod_fd = os.open(KMOD_DEV, os.O_RDWR)
        except PermissionError:
            sys.exit(f'No permission for {KMOD_DEV}: log out/in or check the udev rule')
    return _kmod_fd


def max_profile():
    return 5 if kmod() is not None else 1


def _kmod_xfer(direction, rid, windex, buf):
    import ctypes
    b = (ctypes.c_char * len(buf)).from_buffer(buf)
    x = bytearray(struct.pack('<BBBBHHQ', direction, rid, 0, 0, windex, len(buf), ctypes.addressof(b)))
    # mutable arg + mutate_flag=True makes fcntl return the ioctl's int result (bytes transferred)
    return fcntl.ioctl(kmod(), TAR_IOC_XFER, x, True)


def get_report(rid, length, windex=0):
    buf = bytearray(length)
    if kmod() is not None:
        n = _kmod_xfer(1, rid, windex, buf)
        return bytes(buf[:n])
    if windex > 1:
        sys.exit(f'profile {windex} needs the tarantula_ctl kernel module (kmod/install.sh)')
    buf[0] = rid
    fd = _open_hidraw(windex)
    try:
        n = fcntl.ioctl(fd, HIDIOCGFEATURE(length), buf, True)
    finally:
        os.close(fd)
    return bytes(buf[:n])


def set_report(rid, data, windex=0):
    buf = bytearray(data)
    if kmod() is not None:
        _kmod_xfer(0, rid, windex, buf)
        return
    if windex > 1 or buf[0] != rid:
        sys.exit('this command needs the tarantula_ctl kernel module (kmod/install.sh)')
    fd = _open_hidraw(windex)
    try:
        fcntl.ioctl(fd, HIDIOCSFEATURE(len(buf)), buf, True)
    finally:
        os.close(fd)


def _open_hidraw(intf):
    path = hidraw(intf)
    try:
        return os.open(path, os.O_RDWR)
    except PermissionError:
        sys.exit(f'No permission for {path}: run with sudo or install the udev rule')


def short(rid):
    p = get_report(rid, 8)
    if not any(p) or p[6] != p[0] ^ p[2] ^ p[4] or p[7] != p[1] ^ p[3] ^ p[5]:
        raise RuntimeError(f'bad reply on report {rid}: {p.hex(" ")}')
    return p


def cmd_packet(cmd, a=0, b=0):
    p = bytearray([0x00, 0x08, 0x00, cmd, a, b, 0, 0])
    p[6], p[7] = p[0] ^ p[2] ^ p[4], p[1] ^ p[3] ^ p[5]
    return bytes(p)


def read_block(profile):
    d = get_report(RID_GROUP, BLOCK, profile)
    if not checksum_ok(d):
        raise RuntimeError(f'profile {profile}: bad checksum or empty block')
    if d[5] != profile:
        raise RuntimeError(f'profile {profile}: header says profile {d[5]}')
    return d


def cmd_info(a):
    fw, pid, res = short(RID_FW), short(RID_PROFILEID), short(RID_RESULT)
    print(f'transport       : {KMOD_DEV + " (profiles 1-5)" if kmod() is not None else hidraw(0) + " / " + hidraw(1) + " (profile 1 only)"}')
    print(f'firmware        : raw {fw[4]:02x} {fw[5]:02x}  ({fw[4]} -> v{fw[4] // 100}.{fw[4] % 100:02d}?)')
    print(f'active profile  : {pid[5]}')
    print(f'last result     : {res[5]} ({"busy/failed" if res[5] == RESULT_BUSY else "ok/idle"})')


def decode(d):
    out = [f'header : {d[:6].hex(" ")}  (len 0x{d[0] << 8 | d[1]:03x}, profile {d[5]})']
    km = d[KEYMAP_OFF:KEYMAP_OFF + KEYMAP_LEN]
    changed = [(0x10 + i, v) for i, v in enumerate(km) if v != 0x10 + i]
    out.append('keymap : identity' if not changed else
               'keymap : ' + ', '.join(f'{keyname(c)}->{keyname(v)}' for c, v in changed))
    for s in range(MACRO_SLOTS):
        m = d[MACRO_OFF + s * MACRO_LEN:MACRO_OFF + (s + 1) * MACRO_LEN]
        if m[0] == 0xa5:
            desc = f'switch to profile {m[1]}'
        elif m[0] == 0xa6:
            desc = 'launch program (host-side)'
        else:
            ev = [(m[i], m[i + 1]) for i in range(0, MACRO_LEN, 2) if m[i]]
            desc = ' '.join(f'{keyname(c)}{"v" if f & 1 else "^"}{f" wait:{(f >> 1) * 50}" if f >> 1 else ""}' for c, f in ev)
        out.append(f'macro{s} ({keyname([0x80,0x81,0x82,0x84,0x85,0x89,0x8a,0x8b,0x8c,0x8d][s])}): {desc}')
    out.append(f'cksum  : {d[-2:].hex(" ")} ({"ok" if checksum_ok(d) else "BAD"})')
    return '\n'.join(out)


def cmd_dump(a):
    d = read_block(a.profile)
    if a.raw:
        for i in range(0, len(d), 32):
            print(f'{i:03x}  ' + d[i:i + 32].hex(' '))
    print(decode(d))
    print('(macro events: KEYv = down, KEY^ = up, wait:N = N ms pause after that event)')


def cmd_backup(a):
    d = read_block(a.profile)
    with open(a.file, 'wb') as f:
        f.write(d)
    print(f'saved profile {a.profile} ({len(d)} bytes) to {a.file}')


def keyname(c):
    return KEYS.get(c, f'code{c:02x}')


def keycode(s):
    s = s.lower()
    if s in NAME2CODE:
        return NAME2CODE[s]
    try:
        c = int(s, 16)
    except ValueError:
        c = -1
    if 0x10 <= c <= 0x9f:
        return c
    hint = f' - to type text, put it in quotes: "{s}"' if len(s) > 1 and s.isalnum() else ''
    sys.exit(f'unknown key {s!r}{hint}')


BACKUP_DIR = os.path.expanduser('~/tarantula-re/dumps')


def auto_backup(d):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    f = os.path.join(BACKUP_DIR, time.strftime(f'auto-p{d[5]}-%Y%m%d-%H%M%S.bin'))
    with open(f, 'wb') as fh:
        fh.write(d)
    if os.environ.get('SUDO_UID'):
        os.chown(f, int(os.environ['SUDO_UID']), int(os.environ['SUDO_GID']))
    print(f'backup  : {f}')


def cmd_write(a):
    data = open(a.file, 'rb').read()
    if len(data) != BLOCK or data[:5] != b'\x01\xd8\x00\x01\x00':
        sys.exit('file is not a 472-byte Tarantula profile block')
    write_block(a.profile, data, a.yes)


def cmd_keys(a):
    for c in sorted(KEYS):
        print(f'{c:02x}  {KEYS[c]}')


def edit_keymap(a, fn):
    """Apply fn to the whole profile block (used by macro)."""
    d = bytearray(read_block(a.profile))
    fn(d)
    write_block(a.profile, bytes(d), a.yes)


# ---- key map A/B (toggled by the profile key, code 0x87 -> 1-byte 0xB0 packet) ----
# The keyboard holds one key map per profile; maps A and B live in STATE_FILE and the
# active one is written into the profile on each toggle.
STATE_FILE = os.path.expanduser('~/.config/tarantula/maps.json')
IDENTITY = bytes(range(0x10, 0x10 + KEYMAP_LEN))


def load_state():
    import json
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(st):
    import json
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(st, f, indent=1)
    os.replace(tmp, STATE_FILE)


def sync_entry(st, profile, block, quiet=False):
    """Map state for a profile, created/updated so the active map matches the keyboard."""
    km = block[KEYMAP_OFF:KEYMAP_OFF + KEYMAP_LEN].hex()
    e = st.get(str(profile))
    if e is None:
        e = st[str(profile)] = {'active': 'A', 'A': km, 'B': km}
    elif e[e['active']] != km:
        if not quiet:
            print(f'note    : keyboard key map differs from stored map {e["active"]}; adopting the keyboard\'s')
        e[e['active']] = km
    return e


def map_summary(km, other=None):
    ch = [(0x10 + i, v) for i, v in enumerate(km) if v != 0x10 + i]
    return 'identity' if not ch else ', '.join(f'{keyname(c)}->{keyname(v)}' for c, v in ch)


def keymap_edit(a, fn):
    d = bytearray(read_block(a.profile))
    st = load_state()
    e = sync_entry(st, a.profile, d)
    target = (a.map or e['active']).upper()
    km = bytearray.fromhex(e[target])
    fn(km)
    if target == e['active']:
        print(f'map     : {target} (active, written to keyboard)')
        d[KEYMAP_OFF:KEYMAP_OFF + KEYMAP_LEN] = km
        write_block(a.profile, bytes(d), a.yes)
    else:
        print(f'map     : {target} (inactive, stored only; becomes live when toggled)')
        print(f'  - {map_summary(bytes.fromhex(e[target]))}\n  + {map_summary(km)}')
        if not a.yes:
            sys.exit('dry run: add --yes to save')
    e[target] = km.hex()
    save_state(st)


def cmd_remap(a):
    src, dst = keycode(a.src), keycode(a.dst)
    print(f'remap   : physical {keyname(src)} ({src:02x}) -> sends {keyname(dst)} ({dst:02x})')
    keymap_edit(a, lambda km: km.__setitem__(src - 0x10, dst))


def cmd_reset_keymap(a):
    keymap_edit(a, lambda km: km.__setitem__(slice(None), IDENTITY))


def toggle_map(profile, quiet=False):
    d = bytearray(read_block(profile))
    st = load_state()
    e = sync_entry(st, profile, d, quiet)
    new = 'B' if e['active'] == 'A' else 'A'
    d[KEYMAP_OFF:KEYMAP_OFF + KEYMAP_LEN] = bytes.fromhex(e[new])
    write_block(profile, bytes(d), True, quiet=quiet, backup=False)
    e['active'] = new
    save_state(st)
    return new


def cmd_maps(a):
    st = load_state()
    for p in range(1, max_profile() + 1):
        e = sync_entry(st, p, read_block(p), quiet=True)
        for m in 'AB':
            mark = '*' if e['active'] == m else ' '
            print(f'profile {p} map {m}{mark} {map_summary(bytes.fromhex(e[m]))}')
    save_state(st)
    print('(* = active map, written in the keyboard)')


def cmd_togglemap(a):
    p = a.profile or short(RID_PROFILEID)[5]
    print(f'profile {p}: key map {toggle_map(p)} active')


def notify(text):
    import shutil, subprocess
    if shutil.which('notify-send'):
        subprocess.run(['notify-send', '-a', 'Tarantula', '-e', '-t', '1500', '-i', 'input-keyboard',
                        'Razer Tarantula', text], check=False)


def cmd_daemon(a):
    """Listen on IF0 (/dev/hidraw3) for:
    - the profile key (1-byte 0xB0 packet): toggle key map A/B of the active profile
    - macro keys (HID usages 0xB1-0xBA in a key report): if one of them switched the
      profile on-board (no 0xCn packet is sent), notice it by re-reading the profile
    - 0xCn packets (firmware 'profile change'): notify"""
    import select
    log = lambda m: print(time.strftime('%H:%M:%S ') + m, flush=True)
    log('tarantula map daemon started')

    def announce(p, why):
        e = load_state().get(str(p), {})
        log(f'{why}: now profile {p}')
        if not a.no_notify:
            notify(f'Profile {p}' + (f' \u00b7 key map {e["active"]}' if e else ''))

    while True:
        path = find_hidraw(0)
        if path is None:
            time.sleep(2)
            continue
        try:
            fd = os.open(path, os.O_RDONLY)
        except OSError as e:
            log(f'cannot open {path}: {e}')
            time.sleep(5)
            continue
        log(f'listening on {path}')
        try:
            last = short(RID_PROFILEID)[5]
            checks = []                                  # monotonic times to re-read the profile
            while True:
                timeout = max(0.0, checks[0] - time.monotonic()) if checks else None
                ready, _, _ = select.select([fd], [], [], timeout)
                if ready:
                    data = os.read(fd, 64)
                    if len(data) == 1 and data[0] == 0xb0:
                        p = short(RID_PROFILEID)[5]
                        new = toggle_map(p, quiet=True)
                        last = p
                        log(f'profile key: profile {p} -> key map {new}')
                        if not a.no_notify:
                            notify(f'Profile {p} \u00b7 key map {new}')
                    elif len(data) == 1 and 0xc0 <= data[0] <= 0xcd:
                        last = short(RID_PROFILEID)[5]
                        announce(last, f'keyboard profile change packet 0x{data[0]:02x}')
                    elif len(data) == 8 and any(0xb1 <= b <= 0xba for b in data[2:]):
                        now = time.monotonic()           # a macro key: it may switch profile
                        checks = [now + 0.15, now + 0.5]
                if checks and time.monotonic() >= checks[0]:
                    checks.pop(0)
                    p = short(RID_PROFILEID)[5]
                    if p != last:
                        last = p
                        checks = []
                        announce(p, 'macro key switched profile')
        except (OSError, RuntimeError, SystemExit) as e:
            log(f'device error ({e}); reconnecting')
            time.sleep(2)
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
            global _kmod_fd
            if _kmod_fd is not None:
                try:
                    os.close(_kmod_fd)
                except OSError:
                    pass
                _kmod_fd = None

MACRO_KEYS = [0x80, 0x81, 0x82, 0x84, 0x85, 0x89, 0x8a, 0x8b, 0x8c, 0x8d]


# text -> key presses (assumes a US layout on the host)
_UNSHIFTED = {'`': '`', '-': '-', '=': '=', '[': '[', ']': ']', '\\': 'ISO#', ';': ';', "'": "'",
              ',': ',', '.': '.', '/': '/', ' ': 'Space'}
_SHIFTED = {'~': '`', '!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6', '&': '7', '*': '8',
            '(': '9', ')': '0', '_': '-', '+': '=', '{': '[', '}': ']', '|': 'ISO#', ':': ';', '"': "'",
            '<': ',', '>': '.', '?': '/'}
_LSHIFT = 0x83


def char_key(ch):
    """(code, needs_shift) for a printable character, or None."""
    if ch.isascii() and ch.isalpha():
        return NAME2CODE[ch.lower()], ch.isupper()
    if ch.isascii() and ch.isdigit():
        return NAME2CODE[ch], False
    if ch in _UNSHIFTED:
        return NAME2CODE[_UNSHIFTED[ch].lower()], False
    if ch in _SHIFTED:
        return NAME2CODE[_SHIFTED[ch].lower()], True
    return None


KEY2CHAR = {}
for _ch in [chr(i) for i in range(32, 127)]:
    _k = char_key(_ch)
    if _k:
        KEY2CHAR.setdefault(_k, _ch)


def text_events(text):
    ev = []
    for ch in text:
        k = char_key(ch)
        if k is None:
            sys.exit(f'cannot type {ch!r} (US layout ASCII only; use key names for others)')
        code, shift = k
        if shift:
            ev += [(_LSHIFT, 1), (code, 1), (code, 0), (_LSHIFT, 0)]
        else:
            ev += [(code, 1), (code, 0)]
    return ev


def quote_text(text):
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _tokens(spec):
    """Split a macro spec; quoted strings become ('text', str), everything else ('tok', str)."""
    i, n = 0, len(spec)
    while i < n:
        if spec[i].isspace():
            i += 1
        elif spec[i] == '"':
            j, buf = i + 1, []
            while j < n and spec[j] != '"':
                if spec[j] == '\\' and j + 1 < n:
                    j += 1
                buf.append(spec[j])
                j += 1
            if j >= n:
                sys.exit('unterminated "quoted text"')
            yield 'text', ''.join(buf)
            i = j + 1
        else:
            j = i
            while j < n and not spec[j].isspace() and spec[j] != '"':
                j += 1
            yield 'tok', spec[i:j]
            i = j


def parse_macro(spec):
    """Tokens: KEY (tap)  A+B+C (chord: press in order, release reversed)
    down:KEY  up:KEY  wait:MS (pause after previous event, 50 ms steps, max 6350)
    "text" (typed as key taps, Shift added for capitals/symbols; US layout)"""
    ev = []
    for kind, tok in _tokens(spec):
        if kind == 'text':
            ev += text_events(tok)
            continue
        t = tok.lower()
        if t.startswith('wait:'):
            if not ev:
                sys.exit('wait: needs a preceding event')
            try:
                ms = int(t[5:])
            except ValueError:
                sys.exit('wait: needs a number of milliseconds, e.g. wait:100')
            units = round(ms / 50)
            if not 0 <= units <= 127:
                sys.exit('wait must be 0..6350 ms')
            c, f = ev[-1]
            ev[-1] = (c, (f & 1) | (units << 1))
        elif t.startswith('down:'):
            ev.append((keycode(t[5:]), 1))
        elif t.startswith('up:'):
            ev.append((keycode(t[3:]), 0))
        else:
            keys = [keycode(k) for k in t.split('+')]
            ev += [(k, 1) for k in keys] + [(k, 0) for k in reversed(keys)]
    if not ev:
        sys.exit('empty macro')
    if len(ev) > 16:
        sys.exit(f'too long: {len(ev)} events, a macro key holds 16 '
                 f'(a key = 2, a capital/symbol = 4)')
    return ev


def cmd_macro(a):
    key = keycode(a.slot) if not a.slot.isdigit() else MACRO_KEYS[int(a.slot)]
    if key not in MACRO_KEYS:
        sys.exit('slot must be ML1..ML5, MR1..MR5 or 0..9')
    slot = MACRO_KEYS.index(key)
    if a.default or a.profile_switch:
        ev = [(key, 1), (key, 0)]          # unused for --profile-switch
    elif a.text is not None:
        ev = parse_macro(quote_text(a.text) + ' ' + ' '.join(a.spec))
    else:
        ev = parse_macro(' '.join(a.spec))
    body = bytearray(MACRO_LEN)
    if a.profile_switch:
        body[0], body[1] = 0xa5, a.profile_switch
    else:
        for i, (c, f) in enumerate(ev):
            body[2 * i], body[2 * i + 1] = c, f

    def put(d):
        o = MACRO_OFF + slot * MACRO_LEN
        d[o:o + MACRO_LEN] = body
    edit_keymap(a, put)


def write_block(profile, data, yes, quiet=False, backup=True):
    say = (lambda *x: None) if quiet else print
    if not 1 <= profile <= max_profile():
        sys.exit(f'profile must be 1..{max_profile()}' + ('' if max_profile() == 5 else ' (load tarantula_ctl for 2-5)'))
    data = bytearray(data)
    data[5] = profile
    data = fix_checksum(data)
    before = read_block(profile)
    if before == data:
        say('current : already identical, nothing to write')
        return
    say('change  :')
    for line_b, line_a in zip(decode(before).splitlines(), decode(data).splitlines()):
        if line_b != line_a:
            say(f'  - {line_b}\n  + {line_a}')
    if not yes:
        sys.exit('dry run: add --yes to write')
    if backup:
        auto_backup(before)
    for attempt in range(1, 11):
        set_report(RID_GROUP_SET, data, profile)
        time.sleep(0.05)
        res = short(RID_RESULT)
        say(f'attempt {attempt}: result {res.hex(" ")}')
        if res[5] != RESULT_BUSY:
            break
        time.sleep(0.2)
    after = read_block(profile)
    say('verify  :', 'OK, read-back matches' if after == data else 'MISMATCH')
    if after != data:
        raise RuntimeError(f'profile {profile}: read-back after write does not match')


def cmd_switch(a):
    if kmod() is None:
        sys.exit('switching profiles needs the tarantula_ctl kernel module (kmod/install.sh)')
    set_report(RID_SET_PROFILEID, cmd_packet(0x03, 0, a.n))
    time.sleep(0.05)
    print(f'result          : {short(RID_RESULT).hex(" ")}')
    print(f'active profile  : {short(RID_PROFILEID)[5]}')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('info').set_defaults(fn=cmd_info)
    s = sub.add_parser('dump'); s.add_argument('-p', '--profile', type=int, choices=range(0, 6), default=1)
    s.add_argument('--raw', action='store_true'); s.set_defaults(fn=cmd_dump)
    s = sub.add_parser('backup'); s.add_argument('-p', '--profile', type=int, choices=range(0, 6), default=1)
    s.add_argument('file'); s.set_defaults(fn=cmd_backup)
    s = sub.add_parser('write'); s.add_argument('-p', '--profile', type=int, choices=range(0, 6), default=1)
    s.add_argument('file'); s.add_argument('--yes', action='store_true'); s.set_defaults(fn=cmd_write)
    sub.add_parser('keys').set_defaults(fn=cmd_keys)
    s = sub.add_parser('switch', help='make profile N active (needs kernel module)')
    s.add_argument('n', type=int, choices=range(1, 6)); s.set_defaults(fn=cmd_switch)
    s = sub.add_parser('remap'); s.add_argument('src'); s.add_argument('dst')
    s.add_argument('-p', '--profile', type=int, choices=range(1, 6), default=1)
    s.add_argument('-m', '--map', choices=('A', 'B', 'a', 'b'), help='key map to edit (default: active one)')
    s.add_argument('--yes', action='store_true'); s.set_defaults(fn=cmd_remap)
    sub.add_parser('maps', help='show key maps A/B of every profile').set_defaults(fn=cmd_maps)
    s = sub.add_parser('togglemap', help='swap key map A/B (what the profile key does)')
    s.add_argument('-p', '--profile', type=int, choices=range(1, 6), help='default: active profile')
    s.set_defaults(fn=cmd_togglemap)
    s = sub.add_parser('daemon', help='toggle key map A/B when the profile key is pressed')
    s.add_argument('--no-notify', action='store_true'); s.set_defaults(fn=cmd_daemon)
    s = sub.add_parser('macro', help='program a macro key')
    s.add_argument('slot'); s.add_argument('spec', nargs='*')
    s.add_argument('--default', action='store_true', help='restore factory behaviour (key sends itself)')
    s.add_argument('--text', help='type this text (US layout), e.g. --text "gg wp"')
    s.add_argument('--profile-switch', type=int, choices=range(1, 6), metavar='N',
                   help='make the key switch the keyboard to profile N (on-board)')
    s.add_argument('-p', '--profile', type=int, choices=range(1, 6), default=1)
    s.add_argument('--yes', action='store_true'); s.set_defaults(fn=cmd_macro)
    s = sub.add_parser('reset-keymap'); s.add_argument('-p', '--profile', type=int, choices=range(1, 6), default=1)
    s.add_argument('-m', '--map', choices=('A', 'B', 'a', 'b'), help='key map to reset (default: active one)')
    s.add_argument('--yes', action='store_true'); s.set_defaults(fn=cmd_reset_keymap)
    a = p.parse_args()
    try:
        a.fn(a)
    except OSError as e:
        sys.exit(f'USB error: {errno.errorcode.get(e.errno, e.errno)}')


if __name__ == '__main__':
    main()
