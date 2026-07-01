"""Run Vision — CLI or Gateway."""

import sys
import asyncio
import uvicorn


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "gateway":
        from vision.gateway.server import create_app
        app = create_app()
        uvicorn.run(app, host="0.0.0.0", port=8080)
    else:
        from vision.cli import main as cli_main
        cli_main()


if __name__ == "__main__":
    main()
