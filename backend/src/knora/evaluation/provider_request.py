"""One killable HTTP attempt. Authority and accounting belong to the parent host."""

import base64
import json
import os
import sys
import time
from threading import Event, Thread

import httpx


def _arm_deadline(deadline):
    remaining = deadline - time.time()
    if remaining <= 0:
        os._exit(2)

    def expire():
        Event().wait(remaining)
        # Parent death must not leave a provider socket alive past its original deadline.
        os._exit(2)

    Thread(target=expire, daemon=True).start()


def main():
    try:
        value = json.loads(sys.stdin.buffer.read(8_388_608))
        _arm_deadline(value["deadline"])
        with (
            httpx.Client(
                transport=httpx.HTTPTransport(retries=0, trust_env=False),
                follow_redirects=False,
                trust_env=False,
            ) as client,
            client.stream(
                "POST",
                value["url"],
                headers=value["headers"],
                content=base64.b64decode(value["content"]),
                timeout=value["timeout"],
            ) as response,
        ):
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > 1_048_576:
                    raise ValueError("Response limit")
            result = {
                "status": response.status_code,
                "content": base64.b64encode(content).decode(),
            }
        sys.stdout.write(json.dumps(result))
    except Exception:
        # Neither prompts nor credentials belong in process diagnostics.
        sys.exit(1)


if __name__ == "__main__":
    main()
