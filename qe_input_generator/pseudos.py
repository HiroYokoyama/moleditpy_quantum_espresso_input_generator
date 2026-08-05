"""Locate UPF pseudopotential files on disk instead of guessing their names."""

from __future__ import annotations

import os
import re
import shutil
from typing import Dict, List, Optional, Sequence, Tuple

_ELEMENT_TOKEN = re.compile(r"^([A-Za-z]{1,2})(?=[._\-]|$)")


def element_of(filename: str) -> Optional[str]:
    """Element a UPF filename belongs to, e.g. ``Si.pbe-n-kjpaw_psl.1.0.0.UPF`` -> Si.

    The leading token is delimited by ``.``, ``_`` or ``-``, so ``C.pbe...`` and
    ``Ca.pbe...`` do not collide.
    """
    match = _ELEMENT_TOKEN.match(os.path.basename(str(filename)))
    if not match:
        return None
    token = match.group(1)
    return token[0].upper() + token[1:].lower()


def scan_folder(folder: str) -> Dict[str, List[str]]:
    """Map element -> UPF filenames found in ``folder`` (case-insensitive suffix)."""
    found: Dict[str, List[str]] = {}
    if not folder or not os.path.isdir(folder):
        return found
    for entry in sorted(os.listdir(folder)):
        if not entry.lower().endswith(".upf"):
            continue
        if not os.path.isfile(os.path.join(folder, entry)):
            continue
        element = element_of(entry)
        if element:
            found.setdefault(element, []).append(entry)
    return found


def match_elements(
    elements: Sequence[str], folder: str
) -> Tuple[Dict[str, str], List[str]]:
    """Pick one UPF per element; returns (chosen, elements with nothing found)."""
    available = scan_folder(folder)
    chosen: Dict[str, str] = {}
    missing: List[str] = []
    for element in elements:
        element = str(element).strip().capitalize()
        candidates = available.get(element)
        if candidates:
            # Shortest name first: plain "Si.UPF" beats a long variant spelling.
            chosen[element] = sorted(candidates, key=lambda name: (len(name), name))[0]
        elif element not in missing:
            missing.append(element)
    return chosen, missing


def copy_into(
    chosen: Dict[str, str], source_folder: str, destination_folder: str
) -> List[str]:
    """Copy the selected UPFs into ``pseudo_dir``; returns the copied filenames."""
    if not chosen:
        return []
    if not os.path.isdir(source_folder):
        raise ValueError(f"Pseudopotential folder not found:\n{source_folder}")
    os.makedirs(destination_folder, exist_ok=True)

    copied: List[str] = []
    for filename in chosen.values():
        source = os.path.join(source_folder, filename)
        target = os.path.join(destination_folder, filename)
        if os.path.abspath(source) == os.path.abspath(target):
            continue
        shutil.copyfile(source, target)
        copied.append(filename)
    return copied
