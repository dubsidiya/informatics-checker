#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from checker.auth import hash_pin


def main() -> None:
    parser = argparse.ArgumentParser(description="Hash a teacher PIN with scrypt.")
    parser.add_argument("pin")
    args = parser.parse_args()
    print(hash_pin(args.pin))


if __name__ == "__main__":
    main()
