from __future__ import annotations

import asyncio
import socket
from uuid import uuid4

from knora.main import app

_WORKER_COUNT = 2


async def main() -> None:
    async with app.router.lifespan_context(app):
        runner = app.state.conversation_runner
        async with asyncio.TaskGroup() as group:
            for worker_number in range(_WORKER_COUNT):
                worker_id = f"{socket.gethostname()}:{uuid4().hex[:8]}:{worker_number}"
                group.create_task(runner.run_forever(worker_id=worker_id))


if __name__ == "__main__":
    asyncio.run(main())
