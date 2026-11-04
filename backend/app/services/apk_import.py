"""Bounded APK ingestion through the JADX command line."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from app.paths import validate_app_id


MAX_APK_BYTES = 100 * 1024 * 1024
MAX_UNPACKED_BYTES = 1024 * 1024 * 1024


def import_apk_file(app_id: str, apk_path: Path, repos_root: Path, jadx_command: str = "jadx") -> Path:
    """Import a validated APK into an isolated project directory.

    `apk_path` is a temporary upload file. The original name is never used as a
    filesystem path. An existing project is never overwritten.
    """
    validate_app_id(app_id)
    repos_root = repos_root.resolve()
    repos_root.mkdir(parents=True, exist_ok=True)
    target = repos_root / app_id
    if target.exists():
        raise FileExistsError(f"Project {app_id} already exists")
    if apk_path.stat().st_size > MAX_APK_BYTES:
        raise ValueError("APK exceeds the 100 MiB upload limit")
    if not zipfile.is_zipfile(apk_path):
        raise ValueError("Uploaded file is not an APK/ZIP archive")
    with zipfile.ZipFile(apk_path) as archive:
        entries = archive.infolist()
        names = {entry.filename for entry in entries}
        if "AndroidManifest.xml" not in names or not any(name.startswith("classes") and name.endswith(".dex") for name in names):
            raise ValueError("APK is missing AndroidManifest.xml or classes.dex")
        if len(entries) > 100_000 or sum(entry.file_size for entry in entries) > MAX_UNPACKED_BYTES:
            raise ValueError("APK has too many entries or expands beyond 1 GiB")

    staging = Path(tempfile.mkdtemp(prefix="apk-import-", dir=repos_root))
    try:
        source_apk = staging / "source.apk"
        shutil.copyfile(apk_path, source_apk)
        output = staging / "decompiled"
        try:
            result = subprocess.run(
                [jadx_command, "--output-dir", str(output), str(source_apk)],
                capture_output=True, text=True, timeout=600, check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("JADX is not installed on the backend") from exc
        if result.returncode != 0:
            raise RuntimeError(f"JADX failed: {(result.stderr or result.stdout)[-1200:]}")
        if not (output / "resources" / "AndroidManifest.xml").is_file():
            raise RuntimeError("JADX did not produce a decoded AndroidManifest.xml")
        os.rename(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return target
