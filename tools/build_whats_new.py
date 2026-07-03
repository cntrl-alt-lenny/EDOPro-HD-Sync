#!/usr/bin/env python3
"""Regenerate assets/whats-new.svg — the "What's New" panel shown in the README.

Reads the two most recent version tags from git and turns the commit subjects
between them into a styled SVG card. A GitHub Actions workflow
(.github/workflows/whats-new.yml) runs this on every release tag and commits
the result, so the README panel updates itself. It can also be run by hand:

    python3 tools/build_whats_new.py
"""

import os
import subprocess
import sys
from datetime import date
from xml.sax.saxutils import escape

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(REPO_ROOT, "assets", "whats-new.svg")

# Commit subjects that are release plumbing, not user-visible changes.
SKIP_PREFIXES = (
    "bump version",
    "merge ",
    "update what's new",
)

MAX_BULLETS = 6
MAX_BULLET_CHARS = 72


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    return result.stdout.strip()


def collect_release_info() -> tuple[str, str, list[str]]:
    """Return (latest_tag, release_date, bullets) from the git history."""
    tags = [t for t in git("tag", "-l", "v*", "--sort=-v:refname").splitlines() if t]
    if not tags:
        sys.exit("No version tags found — cannot build the What's New panel.")
    latest = tags[0]
    previous = tags[1] if len(tags) > 1 else None

    commit_range = f"{previous}..{latest}" if previous else latest
    subjects = git("log", "--format=%s", commit_range).splitlines()

    bullets: list[str] = []
    for subject in subjects:
        cleaned = subject.strip()
        if not cleaned or cleaned.lower().startswith(SKIP_PREFIXES):
            continue
        if cleaned not in bullets:
            bullets.append(cleaned)
    bullets = bullets[:MAX_BULLETS] or ["General maintenance and fixes"]
    bullets = [
        b if len(b) <= MAX_BULLET_CHARS else b[: MAX_BULLET_CHARS - 1] + "…" for b in bullets
    ]

    released = date.fromisoformat(git("log", "-1", "--format=%as", latest))
    release_date = f"{released.strftime('%B')} {released.day}, {released.year}"
    return latest, release_date, bullets


def render_svg(version: str, release_date: str, bullets: list[str]) -> str:
    width = 760
    bullets_top = 116
    line_height = 33
    footer_height = 64
    height = bullets_top + len(bullets) * line_height + footer_height

    bullet_rows = []
    for i, text in enumerate(bullets):
        y = bullets_top + i * line_height
        delay = 150 + i * 120
        bullet_rows.append(
            f'  <g class="item" style="animation-delay:{delay}ms">\n'
            f'    <rect x="30" y="{y - 5}" width="9" height="9" rx="2" '
            f'transform="rotate(45 34.5 {y - 0.5})" fill="url(#gold)"/>\n'
            f'    <text x="52" y="{y + 5}" class="bullet">{escape(text)}</text>\n'
            f"  </g>"
        )
    bullets_svg = "\n".join(bullet_rows)

    version_label = escape(version)
    pill_width = 24 + 9 * len(version_label)
    pill_x = width - 28 - pill_width
    footer_y = height - 26

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="What's new in EDOPro HD Sync {version_label}">
  <style>
    text {{ font-family: -apple-system, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; }}
    .eyebrow {{ font-size: 11px; font-weight: 600; letter-spacing: 2.5px; fill: #7f89a6; }}
    .title {{ font-size: 26px; font-weight: 700; fill: #f3f6ff; }}
    .title-version {{ fill: #ffd76a; }}
    .pill-text {{ font-size: 14px; font-weight: 700; fill: #ffd76a; }}
    .date {{ font-size: 12.5px; fill: #7f89a6; }}
    .bullet {{ font-size: 15.5px; fill: #d7deee; }}
    .foot {{ font-size: 12px; fill: #6d7690; }}
    /* Slide-in only — never animate opacity here. A static renderer (README
       thumbnailers, some mobile apps) shows frame zero, so bullets must be
       fully visible in that frame. */
    .item {{ animation: rise 0.5s ease-out backwards; }}
    .spark {{ animation: pulse 2.6s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }}
    .spark2 {{ animation-delay: 1.3s; }}
    @keyframes rise {{
      from {{ transform: translateY(9px); }}
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 0.25; transform: scale(0.8); }}
      50%      {{ opacity: 1; transform: scale(1.1); }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      .item {{ animation: none; }}
      .spark {{ animation: none; }}
    }}
  </style>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#101830"/>
      <stop offset="1" stop-color="#0b1122"/>
    </linearGradient>
    <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#ffd76a"/>
      <stop offset="1" stop-color="#f0a832"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.15" cy="0" r="1">
      <stop offset="0" stop-color="#ffd76a" stop-opacity="0.14"/>
      <stop offset="0.55" stop-color="#ffd76a" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="16" fill="url(#bg)" stroke="#2a3554"/>
  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="16" fill="url(#glow)"/>

  <text x="30" y="36" class="eyebrow">EDOPRO HD SYNC · LATEST RELEASE</text>
  <text x="30" y="68" class="title">What’s New in <tspan class="title-version">{version_label}</tspan></text>
  <rect x="30" y="82" width="122" height="3" rx="1.5" fill="url(#gold)"/>

  <path class="spark" d="M {pill_x - 34} {34 - 11} l 3.2 7.8 7.8 3.2 -7.8 3.2 -3.2 7.8 -3.2 -7.8 -7.8 -3.2 7.8 -3.2 Z" fill="url(#gold)"/>
  <path class="spark spark2" d="M {pill_x - 62} {44 - 7} l 2.1 5 5 2 -5 2 -2.1 5 -2.1 -5 -5 -2 5 -2 Z" fill="url(#gold)"/>

  <rect x="{pill_x}" y="24" width="{pill_width}" height="27" rx="13.5" fill="none" stroke="url(#gold)"/>
  <text x="{pill_x + pill_width / 2}" y="42.5" class="pill-text" text-anchor="middle">{version_label}</text>
  <text x="{width - 28}" y="68" class="date" text-anchor="end">Released {escape(release_date)}</text>

{bullets_svg}

  <line x1="30" y1="{footer_y - 16}" x2="{width - 30}" y2="{footer_y - 16}" stroke="#232d4a"/>
  <text x="30" y="{footer_y}" class="foot">This panel updates automatically with every release</text>
  <text x="{width - 28}" y="{footer_y}" class="foot" text-anchor="end">See all releases →</text>
</svg>
"""


def main() -> None:
    version, release_date, bullets = collect_release_info()
    svg = render_svg(version, release_date, bullets)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    print(f"Wrote {os.path.relpath(OUTPUT_PATH, REPO_ROOT)} for {version} ({len(bullets)} items)")


if __name__ == "__main__":
    main()
