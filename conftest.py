"""Pytest configuration ensuring pythonpath includes root directory."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
