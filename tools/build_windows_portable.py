"""Build a portable Windows zip bundle using Python's signed embeddable runtime."""

from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build" / "windows-portable"
BUNDLE_NAME = "EDOPro-HD-Sync-Windows"
BUNDLE_DIR = BUILD_DIR / BUNDLE_NAME
APP_DIR = BUNDLE_DIR / "app"
SITE_PACKAGES_DIR = BUNDLE_DIR / "Lib" / "site-packages"
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
EMBED_ZIP_NAME = f"python-{PYTHON_VERSION}-embed-amd64.zip"
EMBED_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{EMBED_ZIP_NAME}"
START_FILE = BUNDLE_DIR / "START-HERE.txt"
LAUNCHER_FILE = BUNDLE_DIR / "EDOPro-HD-Sync.cmd"


def clean_dirs() -> None:
    shutil.rmtree(BUNDLE_DIR, ignore_errors=True)
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    SITE_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)


def download_embed_runtime() -> Path:
    download_path = BUILD_DIR / EMBED_ZIP_NAME
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(EMBED_URL) as response, open(download_path, "wb") as file_obj:
        shutil.copyfileobj(response, file_obj)
    return download_path


def extract_embed_runtime(embed_zip: Path) -> None:
    with zipfile.ZipFile(embed_zip) as archive:
        archive.extractall(BUNDLE_DIR)


def patch_python_path_file() -> None:
    pth_files = sorted(BUNDLE_DIR.glob("python*._pth"))
    if not pth_files:
        raise FileNotFoundError("Could not find python*._pth in the embeddable runtime.")

    pth_path = pth_files[0]
    lines = [line.strip() for line in pth_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    normalized_lines: list[str] = []
    for line in lines:
        if line == "#import site":
            normalized_lines.append("import site")
        else:
            normalized_lines.append(line)

    if "Lib\\site-packages" not in normalized_lines:
        if "import site" in normalized_lines:
            insert_at = normalized_lines.index("import site")
            normalized_lines.insert(insert_at, "Lib\\site-packages")
        else:
            normalized_lines.append("Lib\\site-packages")
            normalized_lines.append("import site")

    if "import site" not in normalized_lines:
        normalized_lines.append("import site")

    pth_path.write_text("\n".join(normalized_lines) + "\n", encoding="utf-8")


def install_runtime_dependencies() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--no-compile",
            "--target",
            str(SITE_PACKAGES_DIR),
            "-r",
            str(ROOT / "requirements.txt"),
        ],
        check=True,
    )


def copy_app_files() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    for filename in ("main.py", "config.py", "LICENSE"):
        shutil.copy2(ROOT / filename, APP_DIR / filename)


def write_windows_launcher() -> None:
    LAUNCHER_FILE.write_text(
        "@echo off\n"
        "setlocal\n"
        "cd /d \"%~dp0\"\n"
        ".\\python.exe app\\main.py %*\n"
        "set EXIT_CODE=%ERRORLEVEL%\n"
        "echo.\n"
        "pause\n"
        "exit /b %EXIT_CODE%\n",
        encoding="utf-8",
    )


def write_start_file() -> None:
    START_FILE.write_text(
        "EDOPro HD Sync for Windows\n"
        "==========================\n\n"
        "1. Double-click EDOPro-HD-Sync.cmd\n"
        "2. Pick your EDOPro folder when the folder browser opens\n"
        "3. Wait for the sync summary\n"
        "4. Press any key to close the window\n",
        encoding="utf-8",
    )


def create_release_zip() -> Path:
    archive_base = DIST_DIR / BUNDLE_NAME
    archive_path = archive_base.with_suffix(".zip")
    if archive_path.exists():
        archive_path.unlink()
    shutil.make_archive(str(archive_base), "zip", BUILD_DIR, BUNDLE_NAME)
    return archive_path


def main() -> None:
    clean_dirs()
    embed_zip = download_embed_runtime()
    extract_embed_runtime(embed_zip)
    patch_python_path_file()
    install_runtime_dependencies()
    copy_app_files()
    write_windows_launcher()
    write_start_file()
    archive_path = create_release_zip()

    print(f"Downloaded runtime: {EMBED_URL}")
    print(f"Created bundle: {BUNDLE_DIR}")
    print(f"Created release zip: {archive_path}")


if __name__ == "__main__":
    main()
