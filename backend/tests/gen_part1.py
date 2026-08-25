import json, os

def L(lines, s):
    lines.append(s)

def W(lines):
    lines.append('')

lines = []

L(lines, '"""')
L(lines, 'test_all_endpoints.py -- Comprehensive integration tests')
L(lines, 'for all API endpoint groups.')
L(lines, '"""')
W(lines)
L(lines, 'from __future__ import annotations')
L(lines, 'import json, sys, urllib.request, urllib.error, threading')
W(lines)
L(lines, 'BASE = "http://127.0.0.1:8150"')
L(lines, 'passed = failed = total_tests = 0')
W(lines)

print("Part 1 done: %d lines" % len(lines))
with open('test_all_endpoints.py', 'w') as f:
    f.write('\n'.join(lines))
    f.write('\n')
