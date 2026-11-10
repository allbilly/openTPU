#!/usr/bin/env python3
"""Original strict Project X-Ray assembler, with immutable grid metadata cached.

No feature lookup, required feature, or frame-generation behavior is changed.
The cache avoids re-parsing the full Kintex-7 grid for every unused I/O bank.
Run using the X-Ray environment with its source root on PYTHONPATH.
"""
from functools import lru_cache

from utils import fasm2frames


class CachedGridDatabase(fasm2frames.Database):
    @lru_cache(maxsize=1)
    def grid(self):
        return super().grid()


if __name__ == '__main__':
    fasm2frames.Database = CachedGridDatabase
    fasm2frames.main()
