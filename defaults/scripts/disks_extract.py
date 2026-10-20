#!/usr/bin/env python3
"""Discs & Installers: extract disc images with the system 7z (no mount, no
root). Checks free space before writing anything."""

import os
import re
import shutil
import subprocess
from pathlib import Path

DATA_EXTS = {".iso", ".bin", ".mdf", ".img", ".nrg"}


class ExtractError(Exception):
    pass


class NotEnoughSpace(ExtractError):
    def __init__(self, needed, free):
        super().__init__(f"needs {needed} bytes, {free} free")
        self.needed, self.free = needed, free


def _seven_zip():
    for name in ("7z", "7za", "7zz"):
        path = shutil.which(name)
        if path:
            return path
    raise ExtractError("7z is not installed")


def _data_files(parts):
    """Descriptor files (.cue/.mds) only point at data: extract the data."""
    data = [p for p in parts if Path(p).suffix.lower() in DATA_EXTS]
    return data or list(parts)


def listed_size(image):
    out = subprocess.run([_seven_zip(), "l", "-slt", image], capture_output=True, text=True,
                         errors="replace", timeout=300)
    if out.returncode != 0:
        raise ExtractError("cannot read this disc image")
    return sum(int(m) for m in re.findall(r"^Size = (\d+)", out.stdout, re.M))


def free_space(path):
    fake = os.environ.get("SK_DISKS_FAKE_FREE")
    if fake:
        return int(fake)
    probe = Path(path)
    while not probe.exists():
        probe = probe.parent
    return shutil.disk_usage(probe).free


def extract_images(parts, dest, progress=None):
    images = _data_files(parts)
    seven = _seven_zip()
    needed = sum(listed_size(p) for p in images)
    free = free_space(dest)
    if needed > free:
        raise NotEnoughSpace(needed, free)
    dest = Path(dest)
    created = not dest.exists()
    dirs = []
    try:
        for i, image in enumerate(images, start=1):
            out = dest / f"disc{i}"
            out.mkdir(parents=True, exist_ok=True)
            proc = subprocess.Popen([seven, "x", "-y", "-bsp1", f"-o{out}", image],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, errors="replace")
            for line in proc.stdout:
                m = re.search(r"(\d{1,3})%", line)
                if m and progress:
                    done = (i - 1 + int(m.group(1)) / 100) / len(images)
                    progress(round(done * 100))
            if proc.wait() != 0:
                raise ExtractError("7z could not extract this disc image")
            dirs.append(str(out))
    except Exception:
        if created:
            shutil.rmtree(dest, ignore_errors=True)
        raise
    return dirs
