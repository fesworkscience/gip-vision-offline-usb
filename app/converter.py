from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Iterable

from .glb_to_usdz_fast import glb_to_usdz_fast
from .job_manager import CancelCheck, ProgressCallback


def resolve_ifcconvert_path() -> str | None:
    explicit = os.getenv("IFC_CONVERT_PATH", "").strip()
    if explicit:
        if Path(explicit).exists():
            return explicit
        return None

    found = shutil.which("IfcConvert")
    if found:
        return found

    return None


def _supports_ifcopenshell_glb() -> tuple[bool, str | None]:
    try:
        import ifcopenshell.geom as geom

        _ = geom.settings
        _ = geom.serializer_settings
        _ = geom.serializers.gltf
        _ = geom.iterator
        return True, None
    except Exception as exc:
        return False, str(exc)


def get_diagnostics() -> dict:
    diagnostics = {
        "ifcconvert": {"ok": False, "path": None, "version": None, "error": None},
        "ifcopenshell_glb": {"ok": False, "error": None},
        "pxr": {"ok": False, "version": None, "error": None},
    }

    try:
        ifcconvert = resolve_ifcconvert_path()
        if ifcconvert:
            diagnostics["ifcconvert"]["path"] = ifcconvert
            result = subprocess.run([ifcconvert, "--version"], capture_output=True, text=True, timeout=8)
            output = (result.stdout or result.stderr or "").strip().splitlines()
            diagnostics["ifcconvert"]["version"] = output[0] if output else "unknown"
            diagnostics["ifcconvert"]["ok"] = result.returncode == 0
        else:
            diagnostics["ifcconvert"]["error"] = "IfcConvert not found in PATH"
    except Exception as exc:
        diagnostics["ifcconvert"]["error"] = str(exc)

    ok, err = _supports_ifcopenshell_glb()
    diagnostics["ifcopenshell_glb"]["ok"] = ok
    diagnostics["ifcopenshell_glb"]["error"] = err

    try:
        from pxr import Usd

        diagnostics["pxr"]["ok"] = True
        diagnostics["pxr"]["version"] = getattr(Usd, "GetVersion", lambda: "unknown")()
    except Exception as exc:
        diagnostics["pxr"]["error"] = str(exc)

    return diagnostics


def _check_cancel(cancel_check: CancelCheck | None) -> None:
    if cancel_check and cancel_check():
        raise RuntimeError("Cancelled by user")


def _convert_ifc_to_glb_with_ifcconvert(
    ifcconvert: str,
    input_ifc: Path,
    output_glb: Path,
    include_entities: Iterable[str] | None,
    exclude_entities: Iterable[str] | None,
    cancel_check: CancelCheck | None,
) -> None:
    output_glb.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ifcconvert,
        str(input_ifc),
        str(output_glb),
        "--use-element-guids",
        "--threads",
        str(os.cpu_count() or 4),
    ]

    include = list(include_entities or [])
    exclude = list(exclude_entities or [])
    if include:
        cmd.extend(["--include", "entities"] + include)
    elif exclude:
        cmd.extend(["--exclude", "entities"] + exclude)

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.time() + 1800

    while True:
        if cancel_check and cancel_check():
            process.terminate()
            try:
                process.wait(timeout=5)
            except Exception:
                process.kill()
            raise RuntimeError("Cancelled by user")
        if process.poll() is not None:
            break
        if time.time() > deadline:
            process.terminate()
            raise RuntimeError("IfcConvert timeout after 1800s")
        time.sleep(0.4)

    if cancel_check and cancel_check():
        process.terminate()
        raise RuntimeError("Cancelled by user")

    stdout, stderr = process.communicate(timeout=5)
    if process.returncode != 0:
        detail = (stderr or stdout or "Unknown IfcConvert error").strip()
        raise RuntimeError(f"IfcConvert failed: {detail[:1200]}")

    if not output_glb.exists() or output_glb.stat().st_size == 0:
        raise RuntimeError("IfcConvert completed but GLB output is missing/empty")


def _convert_ifc_to_glb_with_ifcopenshell(
    input_ifc: Path,
    output_glb: Path,
    include_entities: Iterable[str] | None,
    exclude_entities: Iterable[str] | None,
    cancel_check: CancelCheck | None,
) -> None:
    import ifcopenshell
    import ifcopenshell.geom as geom

    output_glb.parent.mkdir(parents=True, exist_ok=True)

    geometry_settings = geom.settings()
    geometry_settings.set("use-world-coords", True)
    geometry_settings.set("weld-vertices", True)
    geometry_settings.set("apply-default-materials", True)

    serializer_settings = geom.serializer_settings()
    serializer_settings.set("use-element-guids", True)
    serializer_settings.set("y-up", True)

    ifc_file = ifcopenshell.open(str(input_ifc))

    include = list(include_entities or [])
    exclude = list(exclude_entities or [])

    iterator = geom.iterator(
        geometry_settings,
        ifc_file,
        num_threads=max(1, os.cpu_count() or 1),
        include=include or None,
        exclude=exclude or None,
    )

    if not iterator.initialize():
        raise RuntimeError("IfcOpenShell iterator initialization failed")

    serializer = geom.serializers.gltf(str(output_glb), geometry_settings, serializer_settings)
    serializer.setFile(ifc_file)
    serializer.writeHeader()

    while True:
        _check_cancel(cancel_check)
        shape = iterator.get()
        serializer.write(shape)
        if not iterator.next():
            break

    serializer.finalize()

    if not output_glb.exists() or output_glb.stat().st_size == 0:
        raise RuntimeError("IfcOpenShell conversion completed but GLB output is missing/empty")


def convert_ifc_to_glb(
    input_ifc: Path,
    output_glb: Path,
    progress_cb: ProgressCallback | None = None,
    include_entities: Iterable[str] | None = None,
    exclude_entities: Iterable[str] | None = None,
    cancel_check: CancelCheck | None = None,
) -> None:
    _check_cancel(cancel_check)

    if progress_cb:
        progress_cb("ifc_to_glb", 15)

    ifcconvert = resolve_ifcconvert_path()
    if ifcconvert:
        _convert_ifc_to_glb_with_ifcconvert(
            ifcconvert=ifcconvert,
            input_ifc=input_ifc,
            output_glb=output_glb,
            include_entities=include_entities,
            exclude_entities=exclude_entities,
            cancel_check=cancel_check,
        )
    else:
        ok, err = _supports_ifcopenshell_glb()
        if not ok:
            raise RuntimeError(
                "IfcConvert not found and IfcOpenShell GLB serializer is unavailable: "
                f"{err or 'unknown error'}"
            )
        _convert_ifc_to_glb_with_ifcopenshell(
            input_ifc=input_ifc,
            output_glb=output_glb,
            include_entities=include_entities,
            exclude_entities=exclude_entities,
            cancel_check=cancel_check,
        )

    if progress_cb:
        progress_cb("ifc_to_glb", 55)


def convert_glb_to_usdz(
    input_glb: Path,
    output_usdz: Path,
    progress_cb: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict:
    _check_cancel(cancel_check)
    if progress_cb:
        progress_cb("glb_to_usdz", 70)

    result = glb_to_usdz_fast(str(input_glb), str(output_usdz))
    if not result.get("success"):
        raise RuntimeError(f"GLB->USDZ failed: {result.get('error', 'Unknown error')}")

    _check_cancel(cancel_check)

    if not output_usdz.exists() or output_usdz.stat().st_size == 0:
        raise RuntimeError("GLB->USDZ completed but USDZ output is missing/empty")

    if progress_cb:
        progress_cb("glb_to_usdz", 95)

    return result.get("stats", {})


def run_fast_pipeline(
    input_ifc: Path,
    output_glb: Path,
    output_usdz: Path,
    progress_cb: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> dict:
    convert_ifc_to_glb(input_ifc, output_glb, progress_cb=progress_cb, cancel_check=cancel_check)
    stats = convert_glb_to_usdz(input_glb=output_glb, output_usdz=output_usdz, progress_cb=progress_cb, cancel_check=cancel_check)
    if progress_cb:
        progress_cb("completed", 100)
    return stats
