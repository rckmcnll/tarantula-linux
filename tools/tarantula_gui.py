#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""tarantula_gui.py - graphical configuration for the Razer Tarantula (GTK 4).

Click a key to remap it (per key map A/B), click a macro key (ML1-5 / MR1-5) to edit
its macro, then Apply. Uses tarantula.py for all keyboard access.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tarantula as t  # noqa: E402

import gi  # noqa: E402
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Gsk', '4.0')
gi.require_version('Graphene', '1.0')
from gi.repository import Gdk, GLib, Graphene, Gsk, Gtk, Pango  # noqa: E402

APP_ID = 'io.github.rckmcnll.TarantulaConfig'
MACRO_AREA = slice(t.MACRO_OFF, t.MACRO_OFF + t.MACRO_SLOTS * t.MACRO_LEN)
PROFILE_KEY = 0x87

SHORT = {'Backspace': 'Bksp', 'CapsLock': 'Caps', 'PrintScreen': 'PrtSc', 'ScrollLock': 'ScrLk',
         'NumLock': 'Num', 'KPEnter': 'Ent', 'PageUp': 'PgUp', 'PageDown': 'PgDn', 'Insert': 'Ins',
         'Delete': 'Del', 'Left': '←', 'Right': '→', 'Up': '↑', 'Down': '↓', 'LShift': 'Shift',
         'RShift': 'Shift', 'LCtrl': 'Ctrl', 'RCtrl': 'Ctrl', 'LAlt': 'Alt', 'RAlt': 'AltGr',
         'LWin?': 'Win?', 'MediaSelect': 'Media', 'PlayPause': '⏯', 'VolDown': 'Vol−', 'VolUp': 'Vol+',
         'WWWHome': 'Web', 'ZoomIn': 'Zoom+', 'ZoomOut': 'Zoom−', 'ISO#': '\\', 'Profile': 'Prof'}


def short(code):
    n = t.keyname(code)
    if n in SHORT:
        return SHORT[n]
    if n.startswith('KP') and len(n) > 2:
        return n[2:]
    return n


def build_layout():
    """(code, x, y, w, h) in key units. Codes without a place stay usable as targets."""
    K = {v: k for k, v in t.KEYS.items()}
    L = []

    def row(names, x, y, widths=None):
        for i, n in enumerate(names):
            w = widths[i] if widths else 1
            if n:
                L.append((K[n], x, y, w, 1))
            x += w
    # Geometry follows the real Tarantula: macro columns L1-5 / R1-5, compact 2-column
    # navigation block with a tall Delete, one key above it and four above the keypad.
    # Confirmed on the user's keyboard: Profile key above nav; Insert, ScrLk, PrtSc, Pause above the keypad.
    x0 = 1.5                     # main block
    xn = x0 + 15.75              # navigation block (2 columns)
    xp = xn + 2.5                # numeric keypad
    # media keys (side buttons on the frame) as a small row on top
    row(['Mute', 'VolDown', 'VolUp', 'PlayPause', 'MediaSelect', 'WWWHome', 'ZoomIn', 'ZoomOut'], xp - 4, 0)
    L[:] = [(c, x, y, w, 0.75) for c, x, y, w, h in L]
    # function row
    L.append((K['Esc'], x0, 1, 1, 1))
    row(['F1', 'F2', 'F3', 'F4'], x0 + 1.75, 1)
    row(['F5', 'F6', 'F7', 'F8'], x0 + 6.25, 1)
    row(['F9', 'F10', 'F11', 'F12'], x0 + 10.75, 1)
    L.append((K['Profile'], xn, 1, 2, 1))
    row(['Insert', 'ScrollLock', 'PrintScreen', 'Pause'], xp, 1)
    y = 2.3
    row(['`', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '=', 'Backspace'], x0, y, [1] * 13 + [2])
    row(['Home', 'End'], xn, y)
    row(['NumLock', 'KP/', 'KP*', 'KP-'], xp, y)
    y += 1
    row(['Tab', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '[', ']', 'ISO#'], x0, y, [1.5] + [1] * 12 + [1.5])
    L.append((K['Delete'], xn, y, 1, 2))
    row(['PageUp'], xn + 1, y)
    row(['KP7', 'KP8', 'KP9'], xp, y)
    L.append((K['KP+'], xp + 3, y, 1, 2))
    y += 1
    row(['CapsLock', 'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ';', "'", 'Enter'], x0, y, [1.75] + [1] * 11 + [2.25])
    row(['PageDown'], xn + 1, y)
    row(['KP4', 'KP5', 'KP6'], xp, y)
    y += 1
    row(['LShift', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', ',', '.', '/', 'RShift'], x0, y, [2.25] + [1] * 10 + [2.75])
    row(['Up'], xn, y)
    row(['KP1', 'KP2', 'KP3'], xp, y)
    L.append((K['KPEnter'], xp + 3, y, 1, 2))
    y += 1
    row(['LCtrl', 'LWin?', 'LAlt', 'Space', 'RAlt', 'Menu?', 'RCtrl'], x0, y,
        [1.5, 1.25, 1.25, 6.5, 1.25, 1.25, 1.5])
    row(['Left', 'Down', 'Right'], xn - 1, y)
    row(['KP0', 'KP.'], xp, y, [2, 1])
    for i in range(5):           # macro columns
        L.append((K[f'ML{i + 1}'], 0, 2.3 + i, 1, 1))
        L.append((K[f'MR{i + 1}'], xp + 4.5, 2.3 + i, 1, 1))
    return L


LAYOUT = build_layout()
LAYOUT_W = max(x + w for _, x, _, w, _ in LAYOUT)
LAYOUT_H = max(y + h for _, _, y, _, h in LAYOUT)
TARGETS = sorted(t.KEYS)                      # every code can be a remap target
TARGET_LABELS = [f'{t.keyname(c)}  ({c:02x})' for c in TARGETS]


def _event_tokens(slot):
    """Macro slot -> list of (token, wait_ms, char_or_None)."""
    ev = [(slot[i], slot[i + 1]) for i in range(0, t.MACRO_LEN, 2) if slot[i]]
    out, i = [], 0
    while i < len(ev):
        j, downs = i, []
        while j < len(ev) and ev[j][1] == 1:            # plain key-downs, no delay
            downs.append(ev[j][0])
            j += 1
        k = len(downs)
        ups = ev[j:j + k]
        if k and len(ups) == k and all(c == downs[k - 1 - n] and not f & 1 for n, (c, f) in enumerate(ups)) \
                and all(f == 0 for _, f in ups[:-1]):
            tok = '+'.join(t.keyname(c).lower() for c in downs)
            ch = None
            if k == 1:
                ch = t.KEY2CHAR.get((downs[0], False))
            elif k == 2 and downs[0] == 0x83:
                ch = t.KEY2CHAR.get((downs[1], True))
            out.append((tok, (ups[-1][1] >> 1) * 50, ch))
            i = j + k
        else:
            c, f = ev[i]
            out.append((('down:' if f & 1 else 'up:') + t.keyname(c).lower(), (f >> 1) * 50, None))
            i += 1
    return out


def events_to_spec(slot):
    """Macro slot -> text: "typed text", taps 'x', chords 'ctrl+c', waits 'wait:N', else down:/up:."""
    toks, run = [], ''
    for tok, wait, ch in _event_tokens(slot):
        if ch is not None:
            run += ch
            if not wait:
                continue
        if run:
            toks.append(t.quote_text(run))
            run = ''
        if ch is None:
            toks.append(tok)
        if wait:
            toks.append(f'wait:{wait}')
    if run:
        toks.append(t.quote_text(run))
    return ' '.join(toks)


def events_to_text(slot):
    """The literal text if the slot is nothing but typed characters (no waits), else None."""
    toks = _event_tokens(slot)
    if toks and all(ch is not None and not wait for _, wait, ch in toks):
        return ''.join(ch for _, _, ch in toks)
    return None


def encode(ev):
    body = bytearray(t.MACRO_LEN)
    for i, (c, f) in enumerate(ev):
        body[2 * i], body[2 * i + 1] = c, f
    return bytes(body)


def call(fn, *a):
    """Run a tarantula.py function, turning its sys.exit() into an exception."""
    try:
        return fn(*a)
    except SystemExit as e:
        raise RuntimeError(str(e.code)) from None


class Model:
    """Working copy of one profile: maps A/B and the macro area."""

    def load(self, profile):
        self.profile = profile
        self.block = call(t.read_block, profile)
        st = t.load_state()
        e = t.sync_entry(st, profile, self.block, quiet=True)
        t.save_state(st)
        self.live = e['active']
        self.maps = {m: bytearray.fromhex(e[m]) for m in 'AB'}
        self.macros = bytearray(self.block[MACRO_AREA])
        self.saved = (bytes(self.maps['A']), bytes(self.maps['B']), bytes(self.macros))
        self.state_mtime = self._mtime()

    @staticmethod
    def _mtime():
        try:
            return os.path.getmtime(t.STATE_FILE)
        except OSError:
            return 0

    def dirty(self):
        return (bytes(self.maps['A']), bytes(self.maps['B']), bytes(self.macros)) != self.saved

    def slot(self, code):
        i = t.MACRO_KEYS.index(code) * t.MACRO_LEN
        return self.macros[i:i + t.MACRO_LEN]

    def set_slot(self, code, body):
        i = t.MACRO_KEYS.index(code) * t.MACRO_LEN
        self.macros[i:i + t.MACRO_LEN] = body

    def apply(self):
        st = t.load_state()
        live = st.get(str(self.profile), {}).get('active', self.live)
        if live != self.live:
            raise RuntimeError('the live key map was toggled meanwhile; Revert and redo the change')
        d = bytearray(self.block)
        d[t.KEYMAP_OFF:t.KEYMAP_OFF + t.KEYMAP_LEN] = self.maps[self.live]
        d[MACRO_AREA] = self.macros
        call(t.write_block, self.profile, bytes(d), True, True, True)
        e = st.setdefault(str(self.profile), {'active': self.live})
        e['A'], e['B'] = self.maps['A'].hex(), self.maps['B'].hex()
        t.save_state(st)
        self.load(self.profile)


def rgba(rgb):
    c = Gdk.RGBA()
    c.red, c.green, c.blue, c.alpha = rgb[0], rgb[1], rgb[2], 1.0
    return c


class KeyboardView(Gtk.Widget):
    """Self-drawn keyboard (GTK 4 snapshot API, no cairo bridge needed)."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.selected = None
        self.set_size_request(900, int(900 / LAYOUT_W * LAYOUT_H) + 8)
        self.set_hexpand(True)
        self.set_vexpand(True)
        click = Gtk.GestureClick()
        click.connect('pressed', self.on_click)
        self.add_controller(click)
        self.set_has_tooltip(True)
        self.connect('query-tooltip', self.on_tooltip)

    def geometry(self):
        w, h = self.get_width(), self.get_height()
        u = min((w - 8) / LAYOUT_W, (h - 8) / LAYOUT_H)
        ox = (w - u * LAYOUT_W) / 2
        oy = (h - u * LAYOUT_H) / 2
        return u, ox, oy

    def key_at(self, px, py):
        u, ox, oy = self.geometry()
        for code, x, y, w, h in LAYOUT:
            if ox + x * u <= px <= ox + (x + w) * u and oy + y * u <= py <= oy + (y + h) * u:
                return code
        return None

    def on_click(self, gesture, n, px, py):
        code = self.key_at(px, py)
        if code is not None:
            self.selected = code
            self.win.select_key(code)
            self.queue_draw()

    def on_tooltip(self, widget, px, py, keyboard_mode, tooltip):
        code = self.key_at(px, py)
        m = self.win.model
        if code is None or m is None:
            return False
        if code in t.MACRO_KEYS:
            body = m.slot(code)
            if body[0] == 0xa5:
                text = f'switch to profile {body[1]}'
            elif body[:2] == bytes([code, 1]) and not any(body[4:]):
                text = 'default (sends itself)'
            else:
                text = events_to_spec(body)
            tooltip.set_text(f'{t.keyname(code)} macro: {text}')
            return True
        dst = m.maps[self.win.edit_map][code - 0x10]
        extra = '' if dst == code else f'  →  sends {t.keyname(dst)}'
        tooltip.set_text(f'{t.keyname(code)} (code {code:02x}){extra}')
        return True

    def palette(self):
        st = Gtk.Settings.get_default()
        dark = bool(st.props.gtk_application_prefer_dark_theme) or 'dark' in (st.props.gtk_theme_name or '').lower()
        if dark:
            return dict(key=(0.23, 0.23, 0.25), edge=(0.36, 0.36, 0.40), text=(0.93, 0.93, 0.95),
                        remap=(0.42, 0.29, 0.12), remap_edge=(0.90, 0.60, 0.24),
                        macro=(0.18, 0.25, 0.37), macro_set=(0.22, 0.34, 0.56), macro_edge=(0.44, 0.61, 0.91),
                        sel=(0.50, 0.69, 1.0), dim=(0.6, 0.6, 0.65))
        return dict(key=(0.95, 0.95, 0.96), edge=(0.60, 0.60, 0.64), text=(0.11, 0.11, 0.13),
                    remap=(1.0, 0.85, 0.66), remap_edge=(0.85, 0.51, 0.17),
                    macro=(0.86, 0.91, 1.0), macro_set=(0.72, 0.83, 1.0), macro_edge=(0.29, 0.47, 0.78),
                    sel=(0.16, 0.44, 0.86), dim=(0.40, 0.40, 0.45))

    def do_snapshot(self, snap):
        m = self.win.model
        if m is None:
            return
        p = self.palette()
        u, ox, oy = self.geometry()
        km = m.maps[self.win.edit_map]
        font = Pango.FontDescription.from_string(f'Sans {max(6, int(u * 0.19))}')
        small = Pango.FontDescription.from_string(f'Sans {max(5, int(u * 0.15))}')
        for code, x, y, w, h in LAYOUT:
            rx, ry, rw, rh = ox + x * u + 2, oy + y * u + 2, w * u - 4, h * u - 4
            sub = None
            if code in t.MACRO_KEYS:
                body = m.slot(code)
                default = body[:2] == bytes([code, 1]) and body[2] == code and not any(body[4:])
                fill, edge = (p['macro'] if default else p['macro_set']), p['macro_edge']
                if not default:
                    sub = f'P{body[1]}' if body[0] == 0xa5 else 'macro'
            elif km[code - 0x10] != code:
                fill, edge = p['remap'], p['remap_edge']
                sub = '→ ' + short(km[code - 0x10])
            else:
                fill, edge = p['key'], p['edge']
            rr = Gsk.RoundedRect()
            rr.init_from_rect(Graphene.Rect().init(rx, ry, rw, rh), min(6, u * 0.12))
            snap.push_rounded_clip(rr)
            snap.append_color(rgba(fill), rr.bounds)
            snap.pop()
            sel = code == self.selected
            bw = 2.5 if sel else 1.0
            bc = rgba(p['sel'] if sel else edge)
            snap.append_border(rr, [bw] * 4, [bc] * 4)
            self._text(snap, short(code), font, p['dim'] if code == PROFILE_KEY else p['text'],
                       rx, ry, rw, rh if not sub else rh * 0.62)
            if sub:
                self._text(snap, sub, small, p['text'], rx, ry + rh * 0.45, rw, rh * 0.55)

    def _text(self, snap, s, font, rgb, x, y, w, h):
        lay = self.create_pango_layout(s)
        lay.set_font_description(font)
        tw, th = lay.get_pixel_size()
        if tw > w - 2:
            lay.set_width(int((w - 2) * Pango.SCALE))
            lay.set_ellipsize(Pango.EllipsizeMode.END)
            tw = w - 2
        snap.save()
        snap.translate(Graphene.Point().init(x + (w - tw) / 2, y + (h - th) / 2))
        snap.append_layout(lay, rgba(rgb))
        snap.restore()


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Tarantula Configuration')
        self.set_default_size(1180, 600)
        self.model = None
        self.edit_map = 'A'
        self.key = None
        self._busy = False
        self.max_profile = 1

        hb = Gtk.HeaderBar()
        self.set_titlebar(hb)
        hb.pack_start(Gtk.Label(label='Profile'))
        self.profile_dd = Gtk.DropDown.new_from_strings(['1', '2', '3', '4', '5'])
        self.profile_dd.connect('notify::selected', self.on_profile_selected)
        hb.pack_start(self.profile_dd)
        self.activate_btn = Gtk.Button(label='Make active')
        self.activate_btn.set_tooltip_text('Switch the keyboard to this profile')
        self.activate_btn.connect('clicked', self.on_make_active)
        hb.pack_start(self.activate_btn)
        hb.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        hb.pack_start(Gtk.Label(label='Edit key map'))
        self.map_a = Gtk.ToggleButton(label='A', active=True)
        self.map_b = Gtk.ToggleButton(label='B', group=self.map_a)
        for b in (self.map_a, self.map_b):
            b.connect('toggled', self.on_map_toggled)
        box = Gtk.Box(css_classes=['linked'])
        box.append(self.map_a)
        box.append(self.map_b)
        hb.pack_start(box)
        self.live_btn = Gtk.Button()
        self.live_btn.set_tooltip_text('Swap the live key map now (same as pressing the profile key)')
        self.live_btn.connect('clicked', self.on_toggle_live)
        hb.pack_start(self.live_btn)

        self.apply_btn = Gtk.Button(label='Apply')
        self.apply_btn.connect('clicked', self.on_apply)
        self.revert_btn = Gtk.Button(label='Revert')
        self.revert_btn.connect('clicked', lambda *_: self.reload())
        hb.pack_end(self.apply_btn)
        hb.pack_end(self.revert_btn)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                        margin_top=8, margin_bottom=8, margin_start=10, margin_end=10)
        self.set_child(outer)
        self.kbd = KeyboardView(self)
        outer.append(self.kbd)

        self.editor = Gtk.Box(spacing=10)
        self.editor.set_size_request(-1, 44)
        outer.append(self.editor)
        legend = Gtk.Label(xalign=0, css_classes=['dim-label'], wrap=True,
                           label='Click a key to remap it in the key map being edited; click ML1-5 / MR1-5 to '
                                 'edit macros. Orange = remapped, blue = macro key (darker = programmed). '
                                 'The profile key (Prof) toggles the live key map A/B via tarantula-mapd.')
        outer.append(legend)
        self.status = Gtk.Label(xalign=0, css_classes=['dim-label'])
        outer.append(self.status)

        self.connect('close-request', self.on_close)
        GLib.idle_add(self.initial_load)
        GLib.timeout_add_seconds(2, self.poll)

    # ---------- loading / status ----------
    def say(self, text, error=False):
        self.status.set_markup(f'<span foreground="#d33">{GLib.markup_escape_text(text)}</span>' if error
                               else GLib.markup_escape_text(text))

    def guard(self, fn, *a):
        try:
            return fn(*a)
        except Exception as e:  # noqa: BLE001
            self.say(f'Error: {e}', error=True)
            return None

    def initial_load(self):
        def go():
            self.max_profile = t.max_profile()
            active = t.short(t.RID_PROFILEID)[5]
            fw = t.short(t.RID_FW)
            self.fw_text = f'firmware {fw[4]:02x} {fw[5]:02x}'
            self.active_profile = active
            start = active if active <= self.max_profile else 1
            self._busy = True
            self.profile_dd.set_selected(start - 1)
            self._busy = False
            self.reload(start)
        if self.guard(go) is None and self.model is None:
            self.say('Keyboard not available (plugged in? udev rule / tarantula_ctl installed?) – retrying…',
                     error=True)
        return False

    def reload(self, profile=None):
        profile = profile or self.profile_dd.get_selected() + 1
        m = Model()
        if self.guard(m.load, profile) is None and getattr(m, 'block', None) is None:
            return
        self.model = m
        self.refresh(rebuild=True)
        self.say(f'Profile {profile} loaded. {self.transport_text()}')

    def transport_text(self):
        via = '/dev/tarantula' if t.kmod() is not None else 'hidraw (profile 1 only)'
        return f'{getattr(self, "fw_text", "")} · via {via}'

    def refresh(self, rebuild=False):
        """Update header state and redraw. rebuild=True also recreates the key editor
        (only after the underlying data changed: reload, map switch, reset)."""
        m = self.model
        if m is None:
            return
        self.live_btn.set_label(f'Live: map {m.live}  ⇄')
        active = getattr(self, 'active_profile', None)
        self.activate_btn.set_sensitive(t.kmod() is not None and active != m.profile)
        self.activate_btn.set_label('Active' if active == m.profile else 'Make active')
        dirty = m.dirty()
        self.apply_btn.set_sensitive(dirty and not getattr(self, 'invalid', False))
        self.revert_btn.set_sensitive(dirty)
        self.live_btn.set_sensitive(not dirty)
        self.set_title('Tarantula Configuration' + (' •' if dirty else ''))
        self.kbd.queue_draw()
        if rebuild and self.key is not None:
            self.select_key(self.key)

    def poll(self):
        """Follow profile-key / profile changes made outside the GUI."""
        if self.model is None:
            self.initial_load()
            return True
        try:
            self.active_profile = t.short(t.RID_PROFILEID)[5]
            if not self.model.dirty() and self.model._mtime() != self.model.state_mtime:
                self.reload(self.model.profile)
            else:
                self.refresh()
        except Exception:  # noqa: BLE001
            self.say('Keyboard not responding (unplugged?)', error=True)
        except SystemExit:
            pass
        return True

    def confirm_discard(self, then):
        if self.model is None or not self.model.dirty():
            then()
            return True
        dlg = Gtk.AlertDialog(message='Discard unsaved changes?', buttons=['Cancel', 'Discard'],
                              cancel_button=0, default_button=0)

        def done(d, res):
            try:
                if d.choose_finish(res) == 1:
                    self.model.saved = (bytes(self.model.maps['A']), bytes(self.model.maps['B']),
                                        bytes(self.model.macros))
                    then()
            except GLib.Error:
                pass
        dlg.choose(self, None, done)
        return False

    # ---------- header actions ----------
    def on_profile_selected(self, dd, _):
        if self._busy or self.model is None:
            return
        p = dd.get_selected() + 1
        if p > self.max_profile:
            self._busy = True
            dd.set_selected(self.model.profile - 1)
            self._busy = False
            self.say('Profiles 2-5 need the tarantula_ctl kernel module (kmod/install.sh)', error=True)
            return

        def go():
            self.reload(p)

        if not self.confirm_discard(go):
            self._busy = True
            dd.set_selected(self.model.profile - 1)
            self._busy = False
            self._pending_profile = p

    def on_map_toggled(self, btn):
        if not btn.get_active():
            return
        self.edit_map = btn.get_label()
        self.refresh(rebuild=True)

    def on_make_active(self, _):
        def go():
            p = self.model.profile
            t.set_report(t.RID_SET_PROFILEID, t.cmd_packet(0x03, 0, p))
            self.active_profile = t.short(t.RID_PROFILEID)[5]
            self.say(f'Keyboard switched to profile {self.active_profile}')
            self.refresh()
        self.guard(go)

    def on_toggle_live(self, _):
        def go():
            new = t.toggle_map(self.model.profile, quiet=True)
            self.reload(self.model.profile)
            self.say(f'Profile {self.model.profile}: live key map is now {new}')
        self.guard(go)

    def on_apply(self, _):
        def go():
            m = self.model
            m.apply()
            self.refresh(rebuild=True)
            self.say(f'Saved: profile {m.profile} written to the keyboard (map {m.live} live), '
                     f'maps A/B stored. Backup in {t.BACKUP_DIR}')
        self.guard(go)

    def on_close(self, _):
        if self.model is not None and self.model.dirty():
            return not self.confirm_discard(self.close)
        return False

    # ---------- key editor ----------
    def clear_editor(self):
        while (c := self.editor.get_first_child()) is not None:
            self.editor.remove(c)

    def select_key(self, code):
        self.key = code
        self.clear_editor()
        m = self.model
        title = Gtk.Label(use_markup=True,
                          label=f'<b>{GLib.markup_escape_text(t.keyname(code))}</b>  <small>code {code:02x}</small>')
        self.editor.append(title)
        if code == PROFILE_KEY:
            self.editor.append(Gtk.Label(label='Profile key: toggles the live key map A/B (handled by '
                                               'tarantula-mapd). Remapping it is disabled here.', wrap=True))
        elif code in t.MACRO_KEYS:
            self.macro_editor(code)
        else:
            self.remap_editor(code)

    def remap_editor(self, code):
        m = self.model
        km = m.maps[self.edit_map]
        self.editor.append(Gtk.Label(label=f'in key map {self.edit_map} sends'))
        dd = Gtk.DropDown(model=Gtk.StringList.new(TARGET_LABELS), enable_search=True)
        dd.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, 'string'))
        dd.set_selected(TARGETS.index(km[code - 0x10]))
        dd.set_size_request(240, -1)

        def changed(d, _):
            km[code - 0x10] = TARGETS[d.get_selected()]
            self.refresh_soft()
        dd.connect('notify::selected', changed)
        self.editor.append(dd)
        reset = Gtk.Button(label='Default')
        reset.set_tooltip_text('This key sends itself again')
        reset.connect('clicked', lambda *_: dd.set_selected(TARGETS.index(code)))
        self.editor.append(reset)
        all_reset = Gtk.Button(label=f'Reset whole map {self.edit_map}')

        def reset_all(*_):
            km[:] = t.IDENTITY
            self.refresh(rebuild=True)
        all_reset.connect('clicked', reset_all)
        self.editor.append(all_reset)

    def macro_editor(self, code):
        m = self.model
        body = m.slot(code)
        default = body[:2] == bytes([code, 1]) and body[2] == code and not any(body[4:])
        DEFAULT, TEXT, KEYS, PROFILE = range(4)
        text = None if default or body[0] in (0xa5, 0xa6) else events_to_text(body)
        mode = DEFAULT if default else PROFILE if body[0] == 0xa5 else TEXT if text is not None else KEYS
        modes = Gtk.DropDown.new_from_strings(['Default (sends itself)', 'Type text', 'Keys & delays',
                                               'Switch to profile'])
        modes.set_selected(mode)
        text_entry = Gtk.Entry(hexpand=True, placeholder_text='text to type, e.g.  gg wp  (US layout)')
        text_entry.set_text(text or '')
        keys_entry = Gtk.Entry(hexpand=True,
                               placeholder_text='e.g.  ctrl+c   or   "hello" wait:200 enter   or   down:shift a up:shift')
        keys_entry.set_text(events_to_spec(body) if mode == KEYS else '')
        keys_entry.set_tooltip_text('Key names separated by spaces (see tarantula.py keys). '
                                    '"quoted text" is typed as-is; a+b = chord; wait:MS pauses (50 ms steps); '
                                    'down:KEY / up:KEY. A macro key holds 16 events: key = 2, capital/symbol = 4.')
        spin = Gtk.SpinButton.new_with_range(1, 5, 1)
        spin.set_value(body[1] if mode == PROFILE else 1)
        info = Gtk.Label(xalign=0, css_classes=['dim-label'], max_width_chars=34, wrap=True)
        for w in (modes, text_entry, keys_entry, spin, info):
            self.editor.append(w)
        if body[0] == 0xa6:
            info.set_text('was: launch program (Windows-only, replaced on edit)')
        state = {'mode': mode}

        def show_error(entry, msg):
            self.invalid = True
            info.set_markup(f'<span foreground="#d33">{GLib.markup_escape_text(msg)}</span>')
            entry.add_css_class('error')

        def update(*_):
            if state.get('busy'):                        # ignore 'changed' fired by our own set_text
                return
            sel = modes.get_selected()
            if sel != state['mode']:                     # carry content across mode switches
                prev, state['mode'], state['busy'] = state['mode'], sel, True
                try:
                    if prev == TEXT and sel == KEYS and text_entry.get_text():
                        keys_entry.set_text(t.quote_text(text_entry.get_text()))
                    elif prev == KEYS and sel == TEXT:
                        try:
                            txt = events_to_text(encode(call(t.parse_macro, keys_entry.get_text())))
                            if txt is not None:
                                text_entry.set_text(txt)
                        except RuntimeError:
                            pass
                finally:
                    state['busy'] = False
            text_entry.set_visible(sel == TEXT)
            keys_entry.set_visible(sel == KEYS)
            spin.set_visible(sel == PROFILE)
            self.invalid = False
            for e in (text_entry, keys_entry):
                e.remove_css_class('error')
            new = bytearray(t.MACRO_LEN)
            if sel == DEFAULT:
                new[0:4] = bytes([code, 1, code, 0])
                info.set_text('')
            elif sel == PROFILE:
                new[0], new[1] = 0xa5, int(spin.get_value())
                info.set_text('on-board profile switch (untested)')
            else:
                entry = text_entry if sel == TEXT else keys_entry
                spec = t.quote_text(entry.get_text()) if sel == TEXT else entry.get_text()
                try:
                    if not entry.get_text():
                        raise RuntimeError('empty macro')
                    ev = call(t.parse_macro, spec)
                except RuntimeError as e:
                    show_error(entry, str(e))
                    self.refresh_soft()
                    return
                new[:] = encode(ev)
                info.set_text(f'{len(ev)}/16 events')
            if bytes(new) != bytes(m.slot(code)):
                m.set_slot(code, new)
            self.refresh_soft()
        modes.connect('notify::selected', update)
        text_entry.connect('changed', update)
        keys_entry.connect('changed', update)
        spin.connect('value-changed', update)
        text_entry.set_visible(mode == TEXT)
        keys_entry.set_visible(mode == KEYS)
        spin.set_visible(mode == PROFILE)
        if mode in (TEXT, KEYS):
            info.set_text(f'{sum(1 for i in range(0, 32, 2) if body[i])}/16 events')

    def refresh_soft(self):
        """Refresh header state and drawing without rebuilding the editor."""
        self.refresh()


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        win = self.get_active_window() or Window(self)
        win.present()


if __name__ == '__main__':
    sys.exit(App().run(sys.argv[:1]))
