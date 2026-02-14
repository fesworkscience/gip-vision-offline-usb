from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = ROOT_DIR / "config"


def _env_path() -> Path:
    default = CONFIG_DIR / ".offline_env"
    return Path(os.getenv("APP_ENV_DIR", str(default)))


def _frameworks_path() -> Path:
    default = CONFIG_DIR / ".offline_frameworks"
    return Path(os.getenv("APP_OFFLINE_FRAMEWORKS_DIR", str(default)))


def _resolve_python() -> Path:
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

    if sys.platform == "darwin":
        frameworks_dir = _frameworks_path()
        python_framework = frameworks_dir / "Python.framework"
        if python_framework.is_dir():
            current = env.get("DYLD_FRAMEWORK_PATH", "")
            env["DYLD_FRAMEWORK_PATH"] = (
                f"{frameworks_dir}:{current}" if current else str(frameworks_dir)
            )
    return env


def main() -> int:
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
    return subprocess.call(cmd, cwd=str(ROOT_DIR), env=_runtime_env())


if __name__ == "__main__":
    raise SystemExit(main())
