#!/usr/bin/env python3
"""Watch for profile-key presses on the Razer Tarantula.

Prints every raw input report from both hidraw interfaces (the profile key is expected
to send a 1-byte 0xCn packet, per razerhid.exe "Profile change 0xCX") and polls the
active profile via /dev/tarantula (or hidraw) every 250 ms. Read-only. Ctrl+C to stop.
Usage: watch_profile.py [seconds]   (default 60)
"""
import os, select, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tarantula as t  # noqa

dur = float(sys.argv[1]) if len(sys.argv) > 1 else 60
fds = {}
for intf in (0, 1):
    p = t.hidraw(intf)
    fds[os.open(p, os.O_RDONLY | os.O_NONBLOCK)] = f'IF{intf} {p}'

t0 = time.monotonic()
last_prof, next_poll = None, 0
print(f'watching for {dur:.0f}s - press the profile key a few times (normal typing is shown too)')
try:
    while time.monotonic() - t0 < dur:
        now = time.monotonic()
        if now >= next_poll:
            prof = t.short(t.RID_PROFILEID)[5]
            if prof != last_prof:
                print(f'{now - t0:7.2f}s  active profile = {prof}')
                last_prof = prof
            next_poll = now + 0.25
        r, _, _ = select.select(list(fds), [], [], 0.05)
        for fd in r:
            data = os.read(fd, 64)
            tag = '  <-- profile event?' if len(data) == 1 or (data and 0xc0 <= data[0] <= 0xcd and not any(data[1:])) else ''
            print(f'{time.monotonic() - t0:7.2f}s  {fds[fd]}: {data.hex(" ")}{tag}')
except KeyboardInterrupt:
    pass
