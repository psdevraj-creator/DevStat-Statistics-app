"""
test_all_endpoints.py - Comprehensive integration tests
for all API endpoint groups.
"""

from __future__ import annotations
import json, sys, urllib.request, urllib.error, threading

BASE = "http://127.0.0.1:8150"
passed = failed = total_tests = 0
