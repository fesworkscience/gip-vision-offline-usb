from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = ROOT_DIR / "config"
PY_MINOR = "3.11"


def _env_path() -> Path:
    default = CONFIG_DIR / ".offline_env"
    return Path(os.getenv("APP_ENV_DIR", str(default)))


def _portable_python_dir() -> Path:
    default = CONFIG_DIR / ".offline_python"
    return Path(os.getenv("APP_OFFLINE_PYTHON_DIR", str(default)))


def _site_packages_path() -> Path:
    return _env_path() / "lib" / f"python{PY_MINOR}" / "site-packages"


def _portable_python_path() -> Path | None:
    root = _portable_python_dir()
    candidates = [
        root / "bin" / f"python{PY_MINOR}",
        root / "bin" / "python3",
        root / "python" / "bin" / f"python{PY_MINOR}",
        root / "python" / "bin" / "python3",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _resolve_python() -> Path:
    if sys.platform == "darwin":
        portable = _portable_python_path()
        if portable is not None:
            return portable

    env_dir = _env_path()
    if os.name == "nt":
        candidate = env_dir / "Scripts" / "python.exe"
    else:
        candidate = env_dir / "bin" / "python"

    if candidate.exists():
        return candidate

    raise FileNotFoundError(
        f"[offline] Embedded Python not found: {candidate}\n"
        "[offline] Rebuild/repackage the release bundle."
    )


def _runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    env["OFFLINE_BLOCK_NET"] = "1"
    env["PIP_NO_INDEX"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["HTTP_PROXY"] = "http://127.0.0.1:9"
    env["HTTPS_PROXY"] = "http://127.0.0.1:9"
    env["ALL_PROXY"] = "socks5://127.0.0.1:9"
    env["NO_PROXY"] = "localhost,127.0.0.1,::1"
    env["http_proxy"] = env["HTTP_PROXY"]
    env["https_proxy"] = env["HTTPS_PROXY"]
    env["all_proxy"] = env["ALL_PROXY"]
    env["no_proxy"] = env["NO_PROXY"]

    site_packages = _site_packages_path()
    if site_packages.is_dir():
        cur_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{site_packages}{os.pathsep}{cur_pythonpath}" if cur_pythonpath else str(site_packages)
        )

    if sys.platform == "darwin":
        portable_root = _portable_python_dir()
        if portable_root.is_dir():
            env["PYTHONHOME"] = str(portable_root)
    return env


def _run_quiet(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
    except Exception:
        pass


def _prepare_macos_runtime() -> None:
    if sys.platform != "darwin":
        return

    marker = CONFIG_DIR / ".macos_runtime_prepared"
    if marker.exists():
        return

    if shutil.which("xattr"):
        _run_quiet(["xattr", "-dr", "com.apple.quarantine", str(ROOT_DIR)])

    try:
        marker.write_text("ok\n", encoding="utf-8")
    except Exception:
        pass


def _normalize_url_host(host: str) -> str:
    value = (host or "").strip()
    if value in {"", "0.0.0.0", "::", "::0"}:
        return "127.0.0.1"
    if ":" in value and not value.startswith("["):
        return f"[{value}]"
    return value


def _probe_host(host: str) -> str:
    value = (host or "").strip()
    if value in {"", "0.0.0.0", "::", "::0"}:
        return "127.0.0.1"
    return value.strip("[]")


def _wait_for_tcp(host: str, port: int, timeout_sec: float = 20.0) -> bool:
    target_host = _probe_host(host)
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with socket.create_connection((target_host, int(port)), timeout=0.6):
                return True
        except Exception:
            time.sleep(0.2)
    return False


def _open_browser(url: str) -> None:
    if os.getenv("OFFLINE_OPEN_BROWSER", "1").strip().lower() in {"0", "false", "no", "off"}:
        return

    if sys.platform == "darwin" and shutil.which("open"):
        _run_quiet(["open", url])
        return

    if sys.platform.startswith("win"):
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return
        except Exception:
            pass

    try:
        import webbrowser

        webbrowser.open_new_tab(url)
    except Exception:
        pass


def main() -> int:
    _prepare_macos_runtime()

    host = os.getenv("OFFLINE_HOST", "127.0.0.1")
    port = os.getenv("OFFLINE_PORT", "8765")
    extra = sys.argv[1:] if len(sys.argv) > 1 else []

    python_bin = _resolve_python()
    cmd = [
        str(python_bin),
        "-m",
        "app.offline_runner",
        "--host",
        host,
        "--port",
        port,
        *extra,
    ]
    server_url = f"http://{_normalize_url_host(host)}:{port}"
    print(f"[offline] Open in browser: {server_url}", flush=True)
    print(server_url, flush=True)

    threading.Thread(
        target=lambda: _open_browser(server_url) if _wait_for_tcp(host, int(port)) else None,
        daemon=True,
    ).start()

    return subprocess.call(cmd, cwd=str(ROOT_DIR), env=_runtime_env())


if __name__ == "__main__":
    raise SystemExit(main())
