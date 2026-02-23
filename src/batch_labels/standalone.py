"""Entry point for running batch-labels as a standalone server."""
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

import uvicorn

# Keep in sync with pyproject.toml [project] version
APP_VERSION = "1.0.0"
GITHUB_REPO = "vitalseeds/batch_labels"


def _version_tuple(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except ValueError:
        return (0,)


def check_and_apply_update() -> None:
    """If a newer release exists on GitHub, download it and restart."""
    if not getattr(sys, "frozen", False):
        return

    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "sku-labels"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        latest = data["tag_name"].lstrip("v")
        if _version_tuple(latest) <= _version_tuple(APP_VERSION):
            return

        exe_url = next(
            (a["browser_download_url"] for a in data["assets"] if a["name"].endswith(".exe")),
            None,
        )
        if not exe_url:
            return

        print(f"Update available: v{latest}. Downloading...")
        current_exe = sys.executable
        exe_dir = os.path.dirname(current_exe)

        tmp_fd, tmp_path = tempfile.mkstemp(dir=exe_dir, suffix=".exe")
        os.close(tmp_fd)
        urllib.request.urlretrieve(exe_url, tmp_path)

        bat_fd, bat_path = tempfile.mkstemp(dir=exe_dir, suffix=".bat")
        os.close(bat_fd)
        with open(bat_path, "w") as f:
            f.write(
                "@echo off\n"
                "timeout /t 2 /nobreak >nul\n"
                f'move /y "{tmp_path}" "{current_exe}"\n'
                f'start "" "{current_exe}"\n'
                'del "%~f0"\n'
            )

        print("Restarting with new version...")
        subprocess.Popen(["cmd", "/c", bat_path])
        sys.exit(0)

    except Exception as e:
        print(f"Update check failed: {e}")


def main():
    check_and_apply_update()
    uvicorn.run("batch_labels.main:app", host="0.0.0.0", port=8765, reload=False)


if __name__ == "__main__":
    main()
