"""Pytest configuration: put the repo root (app modules) on sys.path."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test env — set before any app module import
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-only")
os.environ.pop("EMAIL_SIGNATURE", None)  # deterministic: no env signature fallback
