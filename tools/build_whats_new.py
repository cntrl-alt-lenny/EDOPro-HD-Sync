#!/usr/bin/env python3
"""Regenerate the README's release visuals from git history.

Produces two SVGs in assets/:

  whats-new.svg        - "What's New" card: the changes in the latest release,
                         each tagged NEW/FIX/MISC, plus a commits/files/lines
                         stats row.
  release-history.svg  - feature timeline of recent releases: each release with
                         the user-visible changes it shipped.

A GitHub Actions workflow (.github/workflows/whats-new.yml) runs this on every
release tag and commits the results, so the README updates itself. Preview by
hand with:

    python3 tools/build_whats_new.py
"""

import os
import re
import subprocess
import sys
from datetime import date
from xml.sax.saxutils import escape

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(REPO_ROOT, "assets")

# Commit subjects that are release plumbing, not user-visible changes.
SKIP_PREFIXES = (
    "bump version",
    "merge ",
    "update what's new",
)

MAX_BULLETS = 8
MAX_BULLET_CHARS = 72
HISTORY_WINDOW = 8

# git's well-known empty tree: lets us diff the very first release against nothing.
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

NEW_PREFIXES = ("add", "support", "new", "introduce", "create", "enable", "launchers")
FIX_PREFIXES = ("fix", "stop", "never", "repair", "correct", "prevent", "validate", "honor")


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    return result.stdout.strip()


def classify(subject: str) -> tuple[str, str]:
    """Map a commit subject to a (chip label, chip color) pair."""
    lowered = subject.lower()
    if lowered.startswith(FIX_PREFIXES):
        return ("FIX", "#7ee2a8")
    if lowered.startswith(NEW_PREFIXES):
        return ("NEW", "#ffd76a")
    return ("MISC", "#8b94ad")


def version_tags_newest_first() -> list[str]:
    return [t for t in git("tag", "-l", "v*", "--sort=-v:refname").splitlines() if t]


def diff_stats(base: str, tag: str) -> tuple[int, int, int]:
    """Return (files_changed, insertions, deletions) between two revisions."""
    stat = git("diff", "--shortstat", base, tag)
    files = insertions = deletions = 0
    if m := re.search(r"(\d+) files? changed", stat):
        files = int(m.group(1))
    if m := re.search(r"(\d+) insertions?\(\+\)", stat):
        insertions = int(m.group(1))
    if m := re.search(r"(\d+) deletions?\(-\)", stat):
        deletions = int(m.group(1))
    return files, insertions, deletions


def tag_date(tag: str) -> str:
    released = date.fromisoformat(git("log", "-1", "--format=%as", tag))
    return f"{released.strftime('%B')} {released.day}, {released.year}"


def collect_release_info() -> dict:
    """Everything render_whats_new needs, pulled from the two newest tags."""
    tags = version_tags_newest_first()
    if not tags:
        sys.exit("No version tags found — cannot build the What's New panel.")
    latest = tags[0]
    previous = tags[1] if len(tags) > 1 else None
    base = previous if previous else EMPTY_TREE

    commit_range = f"{previous}..{latest}" if previous else latest
    subjects = git("log", "--format=%s", commit_range).splitlines()

    bullets: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for subject in subjects:
        cleaned = subject.strip()
        if not cleaned or cleaned.lower().startswith(SKIP_PREFIXES) or cleaned in seen:
            continue
        seen.add(cleaned)
        label, color = classify(cleaned)
        if len(cleaned) > MAX_BULLET_CHARS:
            cleaned = cleaned[: MAX_BULLET_CHARS - 1] + "…"
        bullets.append((label, color, cleaned))
    bullets = bullets[:MAX_BULLETS] or [("MISC", "#8b94ad", "General maintenance and fixes")]

    files, insertions, deletions = diff_stats(base, latest)
    return {
        "version": latest,
        "date": tag_date(latest),
        "bullets": bullets,
        "commits": int(git("rev-list", "--count", commit_range)),
        "files": files,
        "insertions": insertions,
        "deletions": deletions,
    }


def collect_release_timeline() -> list[dict]:
    """The last HISTORY_WINDOW releases with their user-visible changes, newest first."""
    tags = version_tags_newest_first()
    timeline = []
    for i, tag in enumerate(tags[:HISTORY_WINDOW]):
        previous = tags[i + 1] if i + 1 < len(tags) else None
        commit_range = f"{previous}..{tag}" if previous else tag
        subjects = []
        for subject in git("log", "--format=%s", commit_range).splitlines():
            cleaned = subject.strip()
            if not cleaned or cleaned.lower().startswith(SKIP_PREFIXES):
                continue
            if cleaned not in subjects:
                subjects.append(cleaned)
        released = date.fromisoformat(git("log", "-1", "--format=%as", tag))
        timeline.append(
            {
                "tag": tag,
                "date": f"{released.strftime('%b')} {released.day}, {released.year}",
                "subjects": subjects,
            }
        )
    return timeline


COMMON_STYLE = """    text { font-family: -apple-system, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; }
    .eyebrow { font-size: 11px; font-weight: 600; letter-spacing: 2.5px; fill: #7f89a6; }
    .title { font-size: 26px; font-weight: 700; fill: #f3f6ff; }
    .title-version { fill: #ffd76a; }
    .date { font-size: 12.5px; fill: #7f89a6; }
    .foot { font-size: 12px; fill: #6d7690; }
    /* Slide-in only — never animate opacity here. A static renderer (README
       thumbnailers, some mobile apps) shows frame zero, so content must be
       fully visible in that frame. */
    .item { animation: rise 0.5s ease-out backwards; }
    @keyframes rise {
      from { transform: translateY(9px); }
    }
    @media (prefers-reduced-motion: reduce) {
      .item { animation: none; }
    }
"""

DEFS = """  <defs>
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
"""


def card_frame(width: int, height: int) -> str:
    return (
        f'  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="16" '
        'fill="url(#bg)" stroke="#2a3554"/>\n'
        f'  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="16" '
        'fill="url(#glow)"/>'
    )


def render_whats_new(info: dict) -> str:
    width = 760
    bullets = info["bullets"]
    bullets_top = 132
    line_height = 33
    footer_height = 64
    height = bullets_top + len(bullets) * line_height + footer_height

    rows = []
    for i, (label, color, text) in enumerate(bullets):
        y = bullets_top + i * line_height
        delay = 150 + i * 110
        rows.append(
            f'  <g class="item" style="animation-delay:{delay}ms">\n'
            f'    <rect x="30" y="{y - 12}" width="42" height="17" rx="8.5" '
            f'fill="none" stroke="{color}"/>\n'
            f'    <text x="51" y="{y}" text-anchor="middle" '
            f'style="font-size:9px;font-weight:700;letter-spacing:0.8px" '
            f'fill="{color}">{label}</text>\n'
            f'    <text x="86" y="{y + 1}" class="bullet">{escape(text)}</text>\n'
            f"  </g>"
        )
    bullets_svg = "\n".join(rows)

    version_label = escape(info["version"])
    pill_width = 24 + 9 * len(version_label)
    pill_x = width - 28 - pill_width
    footer_y = height - 26
    stats_line = (
        f"{info['commits']} commits · {info['files']} files changed · "
        f"+{info['insertions']:,} / −{info['deletions']:,} lines"
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="What's new in EDOPro HD Sync {version_label}">
  <style>
{COMMON_STYLE}    .bullet {{ font-size: 15px; fill: #d7deee; }}
    .stats {{ font-size: 12.5px; fill: #8b94ad; }}
    .spark {{ animation: pulse 2.6s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }}
    .spark2 {{ animation-delay: 1.3s; }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 0.25; transform: scale(0.8); }}
      50%      {{ opacity: 1; transform: scale(1.1); }}
    }}
  </style>
{DEFS}
{card_frame(width, height)}

  <text x="30" y="36" class="eyebrow">EDOPRO HD SYNC · LATEST RELEASE</text>
  <text x="30" y="68" class="title">What’s New in <tspan class="title-version">{version_label}</tspan></text>
  <rect x="30" y="82" width="122" height="3" rx="1.5" fill="url(#gold)"/>
  <text x="30" y="105" class="stats">{escape(stats_line)}</text>

  <path class="spark" d="M {pill_x - 34} 23 l 3.2 7.8 7.8 3.2 -7.8 3.2 -3.2 7.8 -3.2 -7.8 -7.8 -3.2 7.8 -3.2 Z" fill="url(#gold)"/>
  <path class="spark spark2" d="M {pill_x - 62} 37 l 2.1 5 5 2 -5 2 -2.1 5 -2.1 -5 -5 -2 5 -2 Z" fill="url(#gold)"/>

  <rect x="{pill_x}" y="24" width="{pill_width}" height="27" rx="13.5" fill="none" stroke="url(#gold)"/>
  <text x="{pill_x + pill_width / 2}" y="42.5" text-anchor="middle" style="font-size:14px;font-weight:700" fill="#ffd76a">{version_label}</text>
  <text x="{width - 28}" y="68" class="date" text-anchor="end">Released {escape(info["date"])}</text>

{bullets_svg}

  <line x1="30" y1="{footer_y - 16}" x2="{width - 30}" y2="{footer_y - 16}" stroke="#232d4a"/>
  <text x="30" y="{footer_y}" class="foot">This panel updates automatically with every release</text>
  <text x="{width - 28}" y="{footer_y}" class="foot" text-anchor="end">See all releases →</text>
</svg>
"""


MAX_TIMELINE_LINES = 2
MAX_TIMELINE_CHARS = 78
CHIP_ORDER = {"NEW": 0, "FIX": 1, "MISC": 2}


def render_release_timeline(timeline: list[dict]) -> str:
    """A vertical feature timeline: each release with the changes it shipped."""
    width = 760
    top = 76
    header_h = 24
    line_h = 21
    row_gap = 15
    dot_x = 40
    text_x = 58

    rows = []
    y = top
    dot_ys = []
    for i, rel in enumerate(timeline):
        shown = sorted(
            rel["subjects"],
            key=lambda s: (CHIP_ORDER[classify(s)[0]], rel["subjects"].index(s)),
        )[:MAX_TIMELINE_LINES]
        shown = [
            s if len(s) <= MAX_TIMELINE_CHARS else s[: MAX_TIMELINE_CHARS - 1] + "…" for s in shown
        ] or ["General maintenance and fixes"]
        extra = len(rel["subjects"]) - len(shown)

        dot_ys.append(y + 8)
        is_latest = i == 0
        version_fill = "#ffd76a" if is_latest else "#aeb7cf"
        changes = len(rel["subjects"])
        changes_label = f"{changes} change{'s' if changes != 1 else ''}" if changes else "release"
        delay = 100 + i * 90

        parts = [
            f'  <g class="item" style="animation-delay:{delay}ms">',
            (
                f'    <circle cx="{dot_x}" cy="{y + 8}" r="5" '
                + (
                    'fill="url(#gold)"/>'
                    if is_latest
                    else 'fill="#101830" stroke="#3a4666" stroke-width="2"/>'
                )
            ),
            (
                f'    <text x="{text_x}" y="{y + 13}"><tspan style="font-size:14.5px;'
                f'font-weight:700" fill="{version_fill}">{escape(rel["tag"])}</tspan>'
                f'<tspan dx="10" class="date">{escape(rel["date"])}</tspan></text>'
            ),
            (
                f'    <text x="{width - 28}" y="{y + 13}" class="date" '
                f'text-anchor="end">{changes_label}</text>'
            ),
        ]
        for j, subject in enumerate(shown):
            ly = y + header_h + j * line_h
            parts.append(
                f'    <rect x="{text_x}" y="{ly - 4}" width="7" height="7" rx="1.5" '
                f'transform="rotate(45 {text_x + 3.5} {ly - 0.5})" fill="url(#gold)"/>'
            )
            parts.append(
                f'    <text x="{text_x + 18}" y="{ly + 4}" class="entry">{escape(subject)}</text>'
            )
        if extra > 0:
            ly = y + header_h + len(shown) * line_h
            parts.append(
                f'    <text x="{text_x + 18}" y="{ly + 2}" class="more">'
                f"+ {extra} more change{'s' if extra != 1 else ''}</text>"
            )
            y += line_h - 4
        parts.append("  </g>")
        rows.append("\n".join(parts))
        y += header_h + len(shown) * line_h + row_gap

    height = y + 44
    spine = (
        f'  <line x1="{dot_x}" y1="{dot_ys[0]}" x2="{dot_x}" y2="{dot_ys[-1]}" '
        'stroke="#2a3554" stroke-width="2"/>'
        if len(dot_ys) > 1
        else ""
    )
    rows_svg = "\n".join(rows)
    footer_y = height - 24

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="EDOPro HD Sync release history: what each release added">
  <style>
{COMMON_STYLE}    .entry {{ font-size: 13.5px; fill: #d7deee; }}
    .more {{ font-size: 12px; fill: #6d7690; font-style: italic; }}
  </style>
{DEFS}
{card_frame(width, height)}

  <text x="30" y="34" class="eyebrow">RELEASE HISTORY</text>
  <text x="30" y="56" style="font-size:17px;font-weight:700" fill="#f3f6ff">What each release added</text>
  <text x="{width - 28}" y="56" class="date" text-anchor="end">last {len(timeline)} releases</text>

{spine}
{rows_svg}

  <line x1="30" y1="{footer_y - 15}" x2="{width - 30}" y2="{footer_y - 15}" stroke="#232d4a"/>
  <text x="30" y="{footer_y}" class="foot">This timeline updates automatically with every release</text>
  <text x="{width - 28}" y="{footer_y}" class="foot" text-anchor="end">See all releases →</text>
</svg>
"""


def main() -> None:
    os.makedirs(ASSETS_DIR, exist_ok=True)

    info = collect_release_info()
    with open(os.path.join(ASSETS_DIR, "whats-new.svg"), "w", encoding="utf-8", newline="\n") as f:
        f.write(render_whats_new(info))
    print(f"Wrote assets/whats-new.svg for {info['version']} ({len(info['bullets'])} items)")

    timeline = collect_release_timeline()
    path = os.path.join(ASSETS_DIR, "release-history.svg")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_release_timeline(timeline))
    print(f"Wrote assets/release-history.svg ({len(timeline)} releases)")


if __name__ == "__main__":
    main()
