# Razer Tarantula (USB 1532:0102) on Linux

Reverse-engineered from the official Windows driver package `Tarantula_v2.10_070509.zip`
(UsbFltr.sys filter driver + razerhid.exe + razercfg.exe). Verified on real hardware 2026-11-01.

## Usage

```
tools/tarantula.py info                         # firmware, active profile, last result
tools/tarantula.py dump [-p 0-5] [--raw]        # decode key map + macros (0 = factory)
tools/tarantula.py keys                         # list key names / internal codes
tools/tarantula.py remap capslock lctrl --yes   # physical key -> other key
tools/tarantula.py reset-keymap --yes
tools/tarantula.py macro ML3 lctrl+c --yes      # tap, chord, down:K, up:K, wait:MS
tools/tarantula.py macro ML3 --default --yes    # factory behaviour
tools/tarantula.py backup -p 1 FILE / write -p 1 FILE --yes
tools/tarantula.py switch 3                     # make profile 3 active (kernel module)
```

`-p N` selects the profile (default 1). Profiles 2-5 and `switch` need the kernel module;
without it the tool falls back to hidraw (profile 1 only).

Without `--yes` every write is a dry run showing the diff. Each write first saves the
current profile to `dumps/auto-p1-*.bin` and verifies by reading back.
Non-root access: `install-udev.sh` (udev `uaccess` rule, already installed).

### Graphical tool

`tools/tarantula_gui.py` (GTK 4, no extra packages beyond `python3-gi`): a drawn
Tarantula layout with the macro columns; click a key to remap it in key map A or B, click
ML1-5 / MR1-5 to edit a macro (same text syntax as the CLI, validated live), pick the
profile, make it active, swap the live map, then Apply (auto-backup + read-back verify as
in the CLI). It follows profile-key presses handled by `tarantula-mapd` live.
Launcher: `desktop/tarantula-config.desktop` (copy to `~/.local/share/applications/`).

### Profile key = key map A/B toggle

The profile key (internal code 0x87) makes the keyboard send a 1-byte `b0` packet on IF0
(`/dev/hidraw3`), one per press; the firmware itself changes nothing. The Windows app
used it to toggle the current profile between key map A and B. Here:

```
tools/tarantula.py remap -m B capslock lctrl --yes   # edit map B (stored until toggled)
tools/tarantula.py maps                              # A/B of every profile, * = active
tools/tarantula.py togglemap                         # swap now
tools/tarantula.py daemon                            # listen for the key (+ notification)
```

Maps live in `~/.config/tarantula/maps.json`; the active map is the one written in the
keyboard, so each toggle rewrites the profile block in flash (fine for normal use, not for
thousands of toggles a day). Service: `systemd/tarantula-mapd.service` (user unit).
`0xCn` packets are the firmware's own "profile changed" notification (e.g. from a macro
key set to switch profile); the daemon logs them and shows the new profile.

### Kernel module (`kmod/`)

`tarantula_ctl` creates `/dev/tarantula` and issues the HID report requests from the kernel
with `usb_control_msg`, so wIndex can carry the profile number (1-5) and the report type
can be 0 exactly like the Windows driver. It does not bind to the device (usbhid keeps the
keyboard) and only accepts this protocol: report IDs 1-8, wIndex 0-5, length 1-472, device
1532:0102. ioctl `_IOWR('T', 1, struct tarantula_xfer)`, see `kmod/tarantula_ctl.h`.

Installed with `kmod/install.sh` via DKMS (Secure Boot: signed with the enrolled DKMS MOK,
rebuilt on kernel updates), autoloaded via `/etc/modules-load.d/tarantula_ctl.conf`, udev
rule `/etc/udev/rules.d/71-tarantula-ctl.rules` grants the desktop user access.
Remove: `sudo dkms remove tarantula-ctl/1.0 --all` and delete those two files.

Changes are stored in the keyboard's flash and take effect immediately; macros are
played by the keyboard firmware, so no daemon is needed.

## Protocol

All commands are HID class requests on EP0, using report IDs **not** declared in the
HID descriptor. Linux: hidraw `HIDIOCGFEATURE`/`HIDIOCSFEATURE` with the **exact** length
(wLength must match; one extra byte = STALL). The Windows driver uses report type 0
(wValue 0x00NN); feature type (0x03NN) is accepted too.

| ID | Dir | Len | Name (razerhid debug strings) | wIndex |
|----|-----|-----|-------------------------------|--------|
| 6 | GET | 8 | GET_FWVERSION | 0 |
| 5 | GET | 8 | GET_PROFILEID | 0 |
| 2 | GET | 8 | GET_RESULT (byte5: 1 = busy/retry, 2 = ok) | 0 |
| 4 | SET | 8 | SET_PROFILEID `00 08 00 03 00 <n> cs cs` | 0 |
| 3 | GET | 472 | GET_GROUP_SETTING | profile |
| 1 | SET | 472 | SEND_SETTING | profile |
| 7/8 | SET/GET | 1/8 | unknown (driver IOCTLs 0x22244c/0x222454) | 0 |

8-byte packets: `[00 08 dir cmd a b X(b0,b2,b4) X(b1,b3,b5)]` (dir 00 host→kbd, 01 kbd→host).

472-byte profile block:

| Offset | Size | Content |
|--------|------|---------|
| 0x000 | 6 | `01 d8 00 01 00 <profile>` |
| 0x006 | 144 | key map: entry *i* = code sent by physical code 0x10+*i* |
| 0x096 | 10×32 | macro slots for codes 80 81 82 84 85 89 8a 8b 8c 8d (ML1-5, MR1-5) |
| 0x1d6 | 2 | XOR of even bytes, XOR of odd bytes |

Macro slot: up to 16 × `[code, flag]`, terminated by code 0. Flag bit0 = down,
bits 1-7 = pause after the event in 50 ms units. Special slots: `a5 <n>` = switch to
profile n, `a6` = launch program (host side, Windows only).

Internal codes are matrix-ordered, not HID usages. Code → HID usage table extracted
from razercfg.exe file offset 0x3c9f8 → `dumps/codetable.txt` (embedded in the tool).

## Limitations

- Without the kernel module: wIndex carries the profile number, but hidraw sends
  wIndex = interface number, so only profile 0 (IF0, factory defaults) and profile 1
  (IF1) are reachable, and SET_PROFILEID (first byte 0x00 = "no report ID" to hidraw)
  can't be sent. With the module all of it works (verified 2026-11-01).
- usbfs with the kernel driver detached worked once, then returned zeros/STALLs;
  avoid it.
- Unconfirmed labels: `Fn?` (0x87), `LWin?` (0x9c), several media codes;
  MR1-5 positions not yet pressed. Firmware version reads `64 00`.
- 8-byte commands 7/8 not investigated; firmware updater (Freescale JW32 bootloader,
  USB 0425:ff07, Usbicp.sys) not investigated, no firmware image in the package.

## Layout

- `tools/tarantula.py` – the tool; `tools/watch_profile.py` – raw input/profile monitor
- `tools/iscab.py` – InstallShield 12 cab extractor (used to unpack the driver package)
- `tools/probe*.py` – read-only probes used during reverse engineering
- `kmod/` – `tarantula_ctl` kernel module (DKMS) + `install.sh`
- `systemd/` – user unit for the profile-key daemon; `install-udev.sh` – hidraw access
- `dumps/codetable.txt` – internal code → HID usage table

Not in the repo (kept local, regenerate yourself): the Razer driver package and its
unpacked files (`extracted/`, via `tools/iscab.py "<pkg>/Program Files" extracted`), the
disassembly (`disasm/`, `objdump -d -M intel`), and profile backups (`dumps/*.bin`).
The tool expects the checkout at `~/tarantula-re` (auto-backups and the systemd unit
use that path).

## Setup

```
git clone https://github.com/rckmcnll/tarantula-linux ~/tarantula-re
~/tarantula-re/install-udev.sh            # hidraw access without sudo
~/tarantula-re/kmod/install.sh            # optional: profiles 2-5 + switch (DKMS)
cp ~/tarantula-re/systemd/tarantula-mapd.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now tarantula-mapd
```

## License

GPL-2.0-only, see `LICENSE`. The kernel module must be GPL-compatible because it uses
GPL-only kernel symbols (`usb_control_msg`, `usb_for_each_dev`). This project contains no
Razer code or binaries; the protocol was documented from the official driver package.
