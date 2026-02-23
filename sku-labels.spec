# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for sku-labels standalone server.

Build commands:
  Windows: uv run python deploy/build.py --clean
  macOS:   uv run python deploy/build.py --clean
"""
import sys
from pathlib import Path

block_cipher = None

is_windows = sys.platform == "win32"

src_path = Path("src")

a = Analysis(
    ["src/batch_labels/standalone.py"],
    pathex=[str(src_path)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # FastAPI and Starlette
        "fastapi",
        "fastapi.responses",
        "fastapi.routing",
        "fastapi.middleware",
        "starlette",
        "starlette.responses",
        "starlette.routing",
        "starlette.middleware",

        # Uvicorn and ASGI
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",

        # HTTP/Networking
        "httptools",
        "h11",
        "anyio",
        "anyio._backends",
        "anyio._backends._asyncio",
        "sniffio",
        "httpx",

        # Form parsing
        "multipart",

        # .env loading
        "dotenv",

        # ZPL label generation (uses PIL for preview)
        "zpl",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",

        # Standard library modules that may be missed
        "email.mime.text",
        "email.mime.multipart",
        "json",
        "ssl",
        "multiprocessing",
        "logging.config",

        # Application modules
        "batch_labels",
        "batch_labels.main",
        "batch_labels.standalone",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "ruff",
        "ipython",
        "tkinter",
        "matplotlib",
        "scipy",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# uvloop is not available on Windows
if not is_windows:
    a.hiddenimports.append("uvloop")

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="sku-labels",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
