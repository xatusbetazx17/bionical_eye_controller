#!/usr/bin/env python3
"""Compatibility launcher; install the package in a virtual environment first."""
import sys

from bionic_eye.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["gui"]))
