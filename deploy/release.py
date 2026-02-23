"""
Release script: bump version in pyproject.toml and standalone.py, commit, and tag.

Usage:
    uv run python deploy/release.py X.Y.Z
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def bump(version: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        print(f"Error: version must be X.Y.Z, got {version!r}")
        sys.exit(1)

    pyproject = ROOT / "pyproject.toml"
    text = pyproject.read_text()
    new_text = re.sub(r'^version = "[^"]+"', f'version = "{version}"', text, count=1, flags=re.MULTILINE)
    if new_text == text:
        print("Error: version not found in pyproject.toml")
        sys.exit(1)
    pyproject.write_text(new_text)

    standalone = ROOT / "src/batch_labels/standalone.py"
    text = standalone.read_text()
    new_text = re.sub(r'^APP_VERSION = "[^"]+"', f'APP_VERSION = "{version}"', text, count=1, flags=re.MULTILINE)
    if new_text == text:
        print("Error: APP_VERSION not found in standalone.py")
        sys.exit(1)
    standalone.write_text(new_text)

    subprocess.run(["git", "add", str(pyproject), str(standalone)], check=True, cwd=ROOT)
    subprocess.run(["git", "commit", "-m", f"Release v{version}"], check=True, cwd=ROOT)
    subprocess.run(["git", "tag", f"v{version}"], check=True, cwd=ROOT)

    print(f"v{version} tagged. Push with: git push && git push --tags")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: uv run python deploy/release.py X.Y.Z")
        sys.exit(1)
    bump(sys.argv[1])
