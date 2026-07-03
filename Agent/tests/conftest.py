"""Pytest configuration and shared fixtures."""

import sys
import os

# Ensure the Agent root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
