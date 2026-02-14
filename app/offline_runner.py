from __future__ import annotations

import argparse
import ipaddress
import os
import socket


def _is_loopback_target(address: object) -> bool:
    host: str | None = None

    if isinstance(address, tuple) and address:
        host = str(address[0])
    elif isinstance(address, str):
        host = address
        if host.startswith("[") and "]" in host:
            host = host[1 : host.index("]")]
        elif host.count(":") == 1 and "." in host.split(":")[0]:
            host = host.rsplit(":", 1)[0]

    if not host:
        return False

    if host in {"localhost", "127.0.0.1", "::1"}:
        return True

    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _install_network_guard() -> None:
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection

    def guarded_connect(self: socket.socket, address: object):
        if not _is_loopback_target(address):
            raise OSError("Outbound network is blocked by offline bundle policy")
        return original_connect(self, address)

    def guarded_connect_ex(self: socket.socket, address: object) -> int:
        if not _is_loopback_target(address):
            return 111
        return original_connect_ex(self, address)

    def guarded_create_connection(address, *args, **kwargs):
        if not _is_loopback_target(address):
            raise OSError("Outbound network is blocked by offline bundle policy")
        return original_create_connection(address, *args, **kwargs)

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.create_connection = guarded_create_connection


def _enforce_offline_env() -> None:
    os.environ["OFFLINE_BLOCK_NET"] = "1"
    os.environ["PIP_NO_INDEX"] = "1"
    os.environ["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    os.environ["HTTP_PROXY"] = "http://127.0.0.1:9"
    os.environ["HTTPS_PROXY"] = "http://127.0.0.1:9"
    os.environ["ALL_PROXY"] = "socks5://127.0.0.1:9"
    os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
    os.environ["http_proxy"] = os.environ["HTTP_PROXY"]
    os.environ["https_proxy"] = os.environ["HTTPS_PROXY"]
    os.environ["all_proxy"] = os.environ["ALL_PROXY"]
    os.environ["no_proxy"] = os.environ["NO_PROXY"]
    _install_network_guard()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline FastAPI server")
    parser.add_argument("--host", default=os.getenv("OFFLINE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("OFFLINE_PORT", "8765")))
    parser.add_argument("--log-level", default="info")
    return parser.parse_args()


def main() -> int:
    _enforce_offline_env()
    args = _parse_args()

    import uvicorn

    uvicorn.run(
        app="app.main:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level=args.log_level,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
