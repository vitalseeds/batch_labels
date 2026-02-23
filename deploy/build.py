"""
Build script for sku-labels standalone executable.

Usage:
    python deploy/build.py          # Build executable
    python deploy/build.py --clean  # Clean build artifacts first
    python deploy/build.py --test   # Run executable after build to test

Requirements (in dev dependency group):
    pyinstaller>=6.0
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent


def clean_build():
    """Remove previous build artifacts."""
    for path_name in ["build", "dist"]:
        path = PROJECT_ROOT / path_name
        if path.exists():
            shutil.rmtree(path)
            print(f"Cleaned: {path}")

    for pycache in PROJECT_ROOT.rglob("__pycache__"):
        if ".venv" not in str(pycache):
            shutil.rmtree(pycache)
            print(f"Cleaned: {pycache}")


def build():
    """Run PyInstaller build."""
    spec_file = PROJECT_ROOT / "sku-labels.spec"

    if not spec_file.exists():
        print(f"Error: Spec file not found at {spec_file}")
        sys.exit(1)

    uv_path = shutil.which("uv")
    if uv_path:
        cmd = ["uv", "run", "pyinstaller", str(spec_file)]
    else:
        cmd = [sys.executable, "-m", "PyInstaller", str(spec_file)]

    print(f"Building with: {' '.join(cmd)}")
    print(f"Working directory: {PROJECT_ROOT}")
    print()

    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    if result.returncode == 0:
        exe_name = "sku-labels.exe" if sys.platform == "win32" else "sku-labels"
        exe_path = PROJECT_ROOT / "dist" / exe_name
        print()
        print("=" * 60)
        print("Build successful!")
        print("=" * 60)
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"Executable: {exe_path} ({size_mb:.1f} MB)")
        print()
        if sys.platform == "win32":
            print(r"To run:  dist\sku-labels.exe")
        else:
            print("To run:  ./dist/sku-labels")
    else:
        print()
        print("Build failed!")
        sys.exit(1)


def test_executable():
    """Run the built executable to test it."""
    exe_name = "sku-labels.exe" if sys.platform == "win32" else "sku-labels"
    exe_path = PROJECT_ROOT / "dist" / exe_name

    if not exe_path.exists():
        print(f"Error: Executable not found at {exe_path}")
        print("Run build first: python deploy/build.py")
        sys.exit(1)

    print(f"Running: {exe_path}")
    print("Press Ctrl+C to stop")
    print()

    try:
        subprocess.run([str(exe_path)])
    except KeyboardInterrupt:
        print("\nStopped")


def main():
    parser = argparse.ArgumentParser(
        description="Build sku-labels standalone executable",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deploy/build.py          # Build executable
  python deploy/build.py --clean  # Clean and build
  python deploy/build.py --test   # Run built executable
        """,
    )
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts before building")
    parser.add_argument("--test", action="store_true", help="Run the built executable after building")
    args = parser.parse_args()

    if args.clean:
        clean_build()

    if args.test and not args.clean:
        test_executable()
    else:
        build()
        if args.test:
            print()
            test_executable()


if __name__ == "__main__":
    main()
