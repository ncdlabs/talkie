#!/usr/bin/env python3
"""
CLI launcher for module servers.
Usage:
    python run_module_server.py speech --port 8001
    python run_module_server.py rag --port 8002
    python run_module_server.py browser --port 8003
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on path
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Launch a Talkie module server")
    parser.add_argument(
        "module",
        choices=["speech", "rag", "browser"],
        help="Module to launch",
    )
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument(
        "--port", type=int, help="Port to bind to (default: module default)"
    )
    parser.add_argument("--api-key", help="Optional API key for authentication")
    args = parser.parse_args()

    # Default ports
    default_ports = {
        "speech": 8001,
        "rag": 8002,
        "browser": 8003,
    }

    port = args.port if args.port is not None else default_ports[args.module]

    # Import and run the appropriate server
    if args.module == "speech":
        from modules.speech.server import main as speech_main

        sys.argv = [
            "modules.speech.server",
            "--host",
            args.host,
            "--port",
            str(port),
        ]
        if args.api_key:
            sys.argv.extend(["--api-key", args.api_key])
        speech_main()
    elif args.module == "rag":
        from modules.rag.server import main as rag_main

        sys.argv = [
            "modules.rag.server",
            "--host",
            args.host,
            "--port",
            str(port),
        ]
        if args.api_key:
            sys.argv.extend(["--api-key", args.api_key])
        rag_main()
    elif args.module == "browser":
        from modules.browser.server import main as browser_main

        sys.argv = [
            "modules.browser.server",
            "--host",
            args.host,
            "--port",
            str(port),
        ]
        if args.api_key:
            sys.argv.extend(["--api-key", args.api_key])
        browser_main()


if __name__ == "__main__":
    main()
