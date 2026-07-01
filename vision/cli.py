"""Vision CLI — interactive terminal interface."""

import asyncio
import sys
from rich.console import Console
from rich.panel import Panel

from vision.core.config import Config
from vision.core.database import Database
from vision.agent.agent import Agent


console = Console()


async def main_async():
    console.print(Panel.fit(
        "[bold cyan]Vision[/] — Self-improving AI Agent\n"
        "[dim]Type /help for commands, Ctrl+C to exit[/]",
        border_style="cyan",
    ))

    config = Config.load()
    db = Database(config.db_path)
    await db.connect()
    agent = Agent(config, db)

    session_id = await agent.start_session()
    console.print(f"[dim]Session: {session_id}[/]\n")

    loop = asyncio.get_event_loop()

    try:
        while True:
            try:
                # Use loop.run_in_executor for non-blocking input
                user_input = await loop.run_in_executor(None, lambda: input("\033[1;32mYou\033[0m: "))
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input.strip():
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                break

            # Process through agent
            console.print("[bold cyan]Vision[/] ", end="")
            async for chunk in agent.process_message(user_input):
                console.print(chunk, end="", highlight=False)
            console.print()

    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted[/]")
    finally:
        await db.close()
        console.print("[dim]Goodbye![/]")


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
