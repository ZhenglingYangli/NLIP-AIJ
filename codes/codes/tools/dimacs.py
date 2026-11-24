"""Shared DIMACS token reading for CNF-based input formats."""
from __future__ import annotations

from typing import Iterator


def iter_dimacs_ints(lines: Iterator[str]) -> Iterator[int]:
    for line in lines:
        line = line.strip()
        if not line or line.startswith('c'):
            continue
        if line.startswith('p'):
            # The caller handles the header separately.
            continue
        for tok in line.split():
            try:
                yield int(tok)
            except Exception:
                continue
