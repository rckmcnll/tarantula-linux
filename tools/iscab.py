#!/usr/bin/env python3
"""Minimal InstallShield (v6+) cabinet extractor. Usage: iscab.py <dir-with-data1.hdr> <outdir> [--list]"""
import hashlib, os, struct, sys, zlib

src, out = sys.argv[1], sys.argv[2]
listonly = '--list' in sys.argv
hdr = open(os.path.join(src, 'data1.hdr'), 'rb').read()
sig, ver, volinfo, cdo, cds = struct.unpack_from('<5I', hdr, 0)
assert sig == 0x28635349, hex(sig)
cd = cdo
ft_off, = struct.unpack_from('<I', hdr, cd + 0x0c)
dir_count, = struct.unpack_from('<I', hdr, cd + 0x1c)
file_count, = struct.unpack_from('<I', hdr, cd + 0x28)
ft_off2, = struct.unpack_from('<I', hdr, cd + 0x2c)
ft = cd + ft_off
print(f'version=0x{ver:08x} dirs={dir_count} files={file_count}', file=sys.stderr)

def cstr(off):
    end = hdr.index(b'\0', off)
    return hdr[off:end].decode('latin-1')

dirs = [cstr(ft + struct.unpack_from('<I', hdr, ft + 4 * i)[0]) for i in range(dir_count)]

vols = {}
def vol(n):
    if n not in vols:
        vols[n] = open(os.path.join(src, f'data{n}.cab'), 'rb').read()
    return vols[n]

def volhdr(n):
    d = vol(n)
    # v6+ volume header follows 20-byte common header
    f = struct.unpack_from('<IIIIIIIIIIIIIIIII', d, 0x14)
    return dict(data_offset=f[0], first_file_index=f[2], last_file_index=f[3],
                first_file_offset=f[4], first_file_size_expanded=f[6], first_file_size_compressed=f[8],
                last_file_offset=f[10], last_file_size_expanded=f[12], last_file_size_compressed=f[14])

def inflate_chunks(blob):
    outb, p = bytearray(), 0
    while p < len(blob):
        n, = struct.unpack_from('<H', blob, p); p += 2
        if n == 0:
            break
        outb += zlib.decompressobj(-15).decompress(blob[p:p + n]); p += n
    return bytes(outb)

def deobfuscate(b, seed=0):
    r = bytearray(len(b))
    for i, c in enumerate(b):
        x = ((c >> 2) | (c << 6)) & 0xff
        r[i] = x ^ 0xd5
        r[i] = (r[i] - (seed % 0x47)) & 0xff
        seed += 1
    return bytes(r)

bad = 0
for i in range(file_count):
    p = ft + ft_off2 + i * 0x57
    flags, = struct.unpack_from('<H', hdr, p)
    exp, comp, doff = struct.unpack_from('<QQQ', hdr, p + 2)
    md5 = hdr[p + 0x1a:p + 0x2a]
    name_off, = struct.unpack_from('<I', hdr, p + 0x3a)
    dir_idx, = struct.unpack_from('<H', hdr, p + 0x3e)
    volume, = struct.unpack_from('<H', hdr, p + 0x55)
    if flags & 8 or name_off == 0:
        continue
    name = cstr(ft + name_off)
    path = os.path.join(dirs[dir_idx].replace('\\', '/'), name) if dir_idx < len(dirs) else name
    if listonly:
        print(f'{flags:04x} vol{volume} {exp:9d} {comp:9d} {path}')
        continue
    # gather raw (possibly spanning) bytes
    raw, v, need, off = bytearray(), volume, comp if flags & 4 else exp, doff
    while need > 0:
        d, vh = vol(v), volhdr(v)
        take = need
        if vh['last_file_index'] == i and v != volume or (vh['first_file_index'] == i and v != volume):
            off = vh['first_file_offset']
        avail = len(d) - off
        take = min(need, avail)
        raw += d[off:off + take]
        need -= take
        v += 1
        off = None
    raw = bytes(raw)
    if flags & 2:
        raw = deobfuscate(raw)
    data = inflate_chunks(raw) if flags & 4 else raw
    ok = hashlib.md5(data).digest() == md5
    bad += not ok
    dest = os.path.join(out, path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    k = 1
    base = dest
    while os.path.exists(dest):
        dest = f'{base}.{k}'; k += 1
    open(dest, 'wb').write(data)
    print(f'{"OK " if ok else "BAD"} {len(data):9d} {path}')
print(f'md5 failures: {bad}', file=sys.stderr)
