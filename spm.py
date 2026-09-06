#!/usr/bin/env python3
"""Convenience entrypoint so you can run `python spm.py ...` without -m."""
import sys

from spm.cli import main

if __name__ == "__main__":
    sys.exit(main())
