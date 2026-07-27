#!/usr/bin/env python3
"""Validate the account-free ECHS Mathematics Open navigation and release shell."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []


def fail(message: str) -> None:
    ERRORS.append(message)


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        fail(f"Missing required file: {relative}")
        return ""
    return path.read_text(encoding="utf-8")


PUBLIC_PAGES = [
    "index.html",
    "question-bank/index.html",
    "question-bank/practice.html",
    "question-bank/exam.html",
    "question-bank/mistakes.html",
    "question-bank/dashboard.html",
    "question-bank/official/index.html",
    "question-bank/official/archive.html",
    "question-bank/official/practice.html",
    "question-bank/official/exam.html",
    "question-bank/official/dashboard.html",
    "privacy.html",
    "accessibility.html",
    "sources-and-rights.html",
    "404.html",
    "offline.html",
]

for page in PUBLIC_PAGES:
    read(page)

index = read("index.html")
for marker in [
    "https://2ed944-cloud.github.io/ECHS-Math-Open/",
    "ECHS Mathematics Open",
    "No account required",
    'href="question-bank/index.html"',
    'href="question-bank/practice.html"',
    'href="question-bank/exam.html"',
    'href="question-bank/mistakes.html"',
    'href="question-bank/dashboard.html"',
    'href="question-bank/official/index.html"',
    'id="courses"',
]:
    if marker not in index:
        fail(f"Open landing page missing marker: {marker}")

ROLE_LINK_PATTERNS = [
    r'href=["\'][^"\']*login\.html',
    r'href=["\'][^"\']*teacher\.html',
    r'href=["\'][^"\']*parent\.html',
    r'href=["\'][^"\']*admin\.html',
    r'href=["\'][^"\']*school-control\.html',
    r'href=["\'][^"\']*student\.html',
]
for page in PUBLIC_PAGES:
    body = read(page)
    for pattern in ROLE_LINK_PATTERNS:
        if re.search(pattern, body, re.IGNORECASE):
            fail(f"Account or role link exposed in {page}: {pattern}")
    if "https://2ed944-cloud.github.io/ECHS-Math/" in body:
        fail(f"Institutional site URL remains in open page: {page}")

foundation = read("js/platform-foundation.js")
for marker in ["Practice Hub", "Tests", "Progress", "AP Banks", "ECHS Mathematics Open"]:
    if marker not in foundation:
        fail(f"Open navigation foundation missing: {marker}")
for forbidden in ["teacher.html", "parent.html", "login.html", "school-control.html", ">Student<", "publisher questions"]:
    if forbidden.lower() in foundation.lower():
        fail(f"Open navigation foundation contains forbidden marker: {forbidden}")

manifest_text = read("manifest.json")
try:
    manifest = json.loads(manifest_text)
except json.JSONDecodeError as exc:
    fail(f"Invalid manifest.json: {exc}")
    manifest = {}
if manifest.get("name") != "ECHS Mathematics Open":
    fail("manifest.json must identify ECHS Mathematics Open")
shortcuts = manifest.get("shortcuts", [])
shortcut_urls = {str(row.get("url", "")) for row in shortcuts}
for required in [
    "./index.html#courses",
    "./question-bank/index.html",
    "./question-bank/practice.html?mode=adaptive",
    "./question-bank/mistakes.html",
    "./question-bank/exam.html",
    "./question-bank/dashboard.html",
    "./question-bank/official/index.html",
]:
    if required not in shortcut_urls:
        fail(f"PWA manifest missing open shortcut: {required}")
for forbidden in ["teacher.html", "parent.html", "login.html", "admin.html", "student.html"]:
    if forbidden in manifest_text:
        fail(f"PWA manifest contains role/account shortcut: {forbidden}")

worker = read("sw.js")
for required in [
    '"./index.html"',
    '"./question-bank/index.html"',
    '"./question-bank/practice.html"',
    '"./question-bank/exam.html"',
    '"./question-bank/dashboard.html"',
    '"./question-bank/mistakes.html"',
    '"./question-bank/official/index.html"',
]:
    if required not in worker:
        fail(f"Service worker missing open shell asset: {required}")
for forbidden in ["teacher.html", "parent.html", "teacher.js", "parent.js", "login.html"]:
    if forbidden in worker:
        fail(f"Service worker still caches role/account asset: {forbidden}")

for role_page in ["question-bank/teacher.html", "question-bank/parent.html"]:
    body = read(role_page)
    for marker in ['content="0;url=dashboard.html"', 'location.replace("dashboard.html")', "noindex,nofollow"]:
        if marker not in body:
            fail(f"Retired role route {role_page} is not a safe redirect: {marker}")
    if len(body) > 1800:
        fail(f"Retired role route still appears to contain a full workspace: {role_page}")

robots = read("robots.txt")
if "Sitemap: https://2ed944-cloud.github.io/ECHS-Math-Open/sitemap.xml" not in robots:
    fail("robots.txt points to the wrong sitemap")
sitemap = read("sitemap.xml")
if "https://2ed944-cloud.github.io/ECHS-Math/" in sitemap:
    fail("sitemap.xml still contains the institutional site root")
if "https://2ed944-cloud.github.io/ECHS-Math-Open/" not in sitemap:
    fail("sitemap.xml does not contain the open site root")

ATTRIBUTE = re.compile(r"(?:href|src)=[\"']([^\"']+)[\"']", re.IGNORECASE)
for relative in PUBLIC_PAGES:
    page = ROOT / relative
    body = read(relative)
    for value in ATTRIBUTE.findall(body):
        parsed = urlparse(value)
        if parsed.scheme or value.startswith(("#", "//", "data:", "mailto:", "javascript:")):
            continue
        clean = value.split("?", 1)[0].split("#", 1)[0]
        if not clean or "${" in clean or "{" in clean:
            continue
        if clean.startswith("/ECHS-Math-Open/"):
            target = ROOT / clean.removeprefix("/ECHS-Math-Open/")
        elif clean == "/ECHS-Math-Open/":
            target = ROOT / "index.html"
        elif clean.startswith("/"):
            continue
        else:
            target = (page.parent / clean).resolve()
        if target.is_dir():
            target = target / "index.html"
        try:
            target.relative_to(ROOT.resolve())
        except ValueError:
            fail(f"Reference leaves repository root in {relative}: {value}")
            continue
        if not target.exists():
            fail(f"Broken local reference in {relative}: {value}")

print("ECHS Mathematics Open validation")
print(f"Errors: {len(ERRORS)}")
for item in ERRORS:
    print(f"  ERROR: {item}")
if ERRORS:
    sys.exit(1)
print("Status: PASS")
