#!/usr/bin/env python3
"""Extracteur minimal d'images de disque Xbox / Xbox 360 (XDVDFS).

Usage : xiso_extract.py <image.iso> <dossier_sortie> [chemin ...]
Sans chemin, liste la racine. Avec des chemins (ex. default.xex data), extrait
ces fichiers / dossiers (récursivement) dans le dossier de sortie.
"""
import os
import struct
import sys

SECTOR = 2048
MAGIC = b"MICROSOFT*XBOX*MEDIA"
# Décalages possibles de la partition de jeu : ISO « rebuild » (0), XGD1,
# XGD2 (la plupart des jeux 360), XGD3.
PARTITIONS = (0, 0x18300000, 0xFD90000, 0x2080000)


def find_partition(f):
    for off in PARTITIONS:
        f.seek(off + 32 * SECTOR)
        if f.read(len(MAGIC)) == MAGIC:
            hdr = f.read(8)
            root_sector, root_size = struct.unpack("<II", hdr)
            return off, root_sector, root_size
    raise SystemExit("pas une image XDVDFS reconnue")


def read_dir(f, base, sector, size):
    """Renvoie {nom: (secteur, taille, est_dossier)} d'un répertoire (arbre binaire)."""
    if size == 0:
        return {}
    f.seek(base + sector * SECTOR)
    buf = f.read(size)
    out = {}
    stack = [0]
    seen = set()
    while stack:
        off = stack.pop()
        if off in seen or off + 14 > len(buf):
            continue
        seen.add(off)
        left, right, s, sz, attr, nlen = struct.unpack_from("<HHIIBB", buf, off)
        if left == 0xFFFF and right == 0xFFFF:      # remplissage
            continue
        name = buf[off + 14: off + 14 + nlen].decode("latin-1")
        out[name] = (s, sz, bool(attr & 0x10))
        if left:
            stack.append(left * 4)
        if right:
            stack.append(right * 4)
    return out


def extract(f, base, entry, name, dest):
    s, sz, is_dir = entry
    path = os.path.join(dest, name)
    if is_dir:
        os.makedirs(path, exist_ok=True)
        for n, e in read_dir(f, base, s, sz).items():
            extract(f, base, e, n, path)
        return
    f.seek(base + s * SECTOR)
    left = sz
    with open(path, "wb") as o:
        while left:
            chunk = f.read(min(left, 8 << 20))
            if not chunk:
                raise SystemExit(f"image tronquée sur {name}")
            o.write(chunk)
            left -= len(chunk)


def main():
    iso, dest, wanted = sys.argv[1], sys.argv[2], sys.argv[3:]
    with open(iso, "rb") as f:
        base, rs, rz = find_partition(f)
        root = read_dir(f, base, rs, rz)
        print(f"partition à 0x{base:X}, racine : {len(root)} entrées")
        if not wanted:
            for n, (s, sz, d) in sorted(root.items()):
                print(("  [dir] " if d else "        ") + n, sz)
            return
        os.makedirs(dest, exist_ok=True)
        for w in wanted:
            if w not in root:
                raise SystemExit(f"{w} absent de la racine")
            print("extraction :", w)
            extract(f, base, root[w], w, dest)


if __name__ == "__main__":
    main()
