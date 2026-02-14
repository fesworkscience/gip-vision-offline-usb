from __future__ import annotations

import argparse
import os

import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run FastAPI server.")
    parser.add_argument(
        "--host",
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host to bind (default: %(default)s or env HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="Port to bind (default: %(default)s or env PORT)",
    )
    parser.add_argument(
        "--app",
        default="app.main:app",
        help="ASGI app target (default: %(default)s)",
    )
    parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable auto-reload (default: True). Use --no-reload to disable",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=("critical", "error", "warning", "info", "debug", "trace"),
        help="Uvicorn log level (default: info)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    uvicorn.run(
        app=args.app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
