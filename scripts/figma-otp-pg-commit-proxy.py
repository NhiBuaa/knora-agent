"""Bounded test-only lost PostgreSQL COMMIT reply fault; never a production dependency."""

import asyncio
import hmac
import json
import os
import re
import struct
import sys
import time
import unittest
import uuid
from contextlib import suppress

MAX_PACKET = 1_048_576


def bind_parameters(payload):
    """Decode only parameter boundaries; never decode/store SQL or authentication frames."""
    try:
        offset = payload.index(b"\0") + 1
        offset = payload.index(b"\0", offset) + 1
        formats = struct.unpack_from("!H", payload, offset)[0]
        offset += 2 + formats * 2
        count = struct.unpack_from("!H", payload, offset)[0]
        offset += 2
        values = []
        for _ in range(count):
            length = struct.unpack_from("!i", payload, offset)[0]
            offset += 4
            if length == -1:
                continue
            if length < 0 or offset + length > len(payload):
                return []
            values.append(payload[offset : offset + length])
            offset += length
        return values
    except (ValueError, struct.error):
        return []


class Fault:
    def __init__(self):
        self.disarm()
        self.confirmed = 0

    def disarm(self):
        self.target = None
        self.deadline = 0
        self.connection = None

    def arm(self, target):
        if not isinstance(target, str) or not re.fullmatch(
            r"knora-otp-proof:[a-zA-Z0-9:-]{1,100}", target
        ):
            raise ValueError("Exact synthetic namespace required")
        if self.target is not None and time.monotonic() < self.deadline:
            raise ValueError("One outstanding arm only")
        self.target = target.encode("ascii")
        self.deadline = time.monotonic() + 30
        self.connection = None
        self.confirmed = 0

    def claim(self, connection, message_type, payload):
        if message_type != b"B" or self.target is None or self.connection is not None:
            return False
        if time.monotonic() >= self.deadline or self.target not in bind_parameters(payload):
            return False
        self.connection = connection
        return True

    def suppress(self, connection, message_type, payload):
        if self.connection != connection or time.monotonic() >= self.deadline:
            return False
        if message_type != b"C" or payload != b"COMMIT\0":
            return False
        self.confirmed += 1
        self.disarm()
        return True


async def read_packet(reader):
    message_type = await reader.readexactly(1)
    length_bytes = await reader.readexactly(4)
    length = struct.unpack("!I", length_bytes)[0]
    if not 4 <= length <= MAX_PACKET:
        raise ValueError("Frame size rejected")
    payload = await reader.readexactly(length - 4)
    return message_type, payload, message_type + length_bytes + payload


class Proxy:
    def __init__(self, secret):
        self.secret = secret
        self.fault = Fault()
        self.connections = 0

    async def postgres(self, client_reader, client_writer):
        if self.connections >= 32:
            client_writer.close()
            return
        self.connections += 1
        backend_writer = None
        tasks = []
        connection = uuid.uuid4().hex
        try:
            async with asyncio.timeout(60):
                # SSL/GSS negotiation is explicitly rejected for this isolated test route.
                while True:
                    length_bytes = await client_reader.readexactly(4)
                    length = struct.unpack("!I", length_bytes)[0]
                    if not 8 <= length <= MAX_PACKET:
                        raise ValueError("Startup size rejected")
                    startup = await client_reader.readexactly(length - 4)
                    code = struct.unpack_from("!I", startup)[0]
                    if code in (80877103, 80877104):
                        client_writer.write(b"N")
                        await client_writer.drain()
                        continue
                    if code != 196608:
                        raise ValueError("Only PostgreSQL protocol3 startup supported")
                    break
                backend_reader, backend_writer = await asyncio.open_connection("keycloak-db", 5432)
                backend_writer.write(length_bytes + startup)
                await backend_writer.drain()

                async def frontend():
                    while True:
                        kind, payload, frame = await read_packet(client_reader)
                        self.fault.claim(connection, kind, payload)
                        backend_writer.write(frame)
                        await backend_writer.drain()

                async def backend():
                    while True:
                        kind, payload, frame = await read_packet(backend_reader)
                        # Reading the real backend completion precedes dropping its reply.
                        if self.fault.suppress(connection, kind, payload):
                            return
                        client_writer.write(frame)
                        await client_writer.drain()

                tasks = [asyncio.create_task(frontend()), asyncio.create_task(backend())]
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except (OSError, EOFError, ValueError, TimeoutError, asyncio.IncompleteReadError):
            pass
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            client_writer.close()
            if backend_writer is not None:
                backend_writer.close()
            self.connections -= 1

    async def control(self, reader, writer):
        status = 404
        response = {}
        try:
            async with asyncio.timeout(3):
                headers = await reader.readuntil(b"\r\n\r\n")
                if len(headers) > 8192:
                    raise ValueError("Control headers too large")
                lines = headers.decode("ascii").split("\r\n")
                method, path, _ = lines[0].split(" ")
                fields = dict(line.split(":", 1) for line in lines[1:] if ":" in line)
                fields = {key.lower(): value.strip() for key, value in fields.items()}
                if not hmac.compare_digest(fields.get("x-knora-storage-proof", ""), self.secret):
                    raise ValueError("Control authentication failed")
                size = int(fields.get("content-length", "0"))
                if not 0 <= size <= 256:
                    raise ValueError("Control body too large")
                payload = await reader.readexactly(size)
                if method == "POST" and path == "/arm":
                    self.fault.arm(json.loads(payload)["challenge"])
                    status, response = 200, {"armed": True}
                elif method == "DELETE" and path == "/arm":
                    self.fault.disarm()
                    status, response = 200, {"disarmed": True}
                elif method == "GET" and path == "/state":
                    status, response = (
                        200,
                        {
                            "confirmedCommitRepliesDropped": self.fault.confirmed,
                            "armed": self.fault.target is not None,
                        },
                    )
        except (
            ValueError,
            KeyError,
            OSError,
            TimeoutError,
            asyncio.IncompleteReadError,
            asyncio.LimitOverrunError,
        ):
            pass
        body = json.dumps(response).encode("ascii")
        response_headers = (
            f"HTTP/1.1 {status} Result\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
        )
        with suppress(OSError):
            writer.write(response_headers.encode("ascii") + body)
            await writer.drain()
        writer.close()


async def serve():
    secret = os.environ.get("KNORA_STORAGE_PROOF_SECRET", "")
    if os.environ.get("KNORA_STORAGE_PROOF") != "enabled" or len(secret) < 32:
        raise SystemExit("Explicit isolated storage proof enablement required")
    proxy = Proxy(secret)
    postgres = await asyncio.start_server(proxy.postgres, "0.0.0.0", 5432)
    control = await asyncio.start_server(proxy.control, "0.0.0.0", 8765, limit=8192)
    async with postgres, control:
        await asyncio.gather(postgres.serve_forever(), control.serve_forever())


class ProtocolTests(unittest.TestCase):
    def test_only_exact_bind_parameter_claims_one_connection(self):
        import struct

        target = b"knora-otp-proof:synthetic-challenge"

        def bind(value):
            return b"\0\0" + struct.pack("!HHI", 0, 1, len(value)) + value + b"\0\0"

        fault = Fault()
        fault.arm(target.decode())
        self.assertFalse(fault.claim("other", b"B", bind(target + b"-suffix")))
        self.assertTrue(fault.claim("chosen", b"B", bind(target)))
        self.assertFalse(fault.claim("second", b"B", bind(target)))
        self.assertFalse(fault.suppress("chosen", b"C", b"INSERT 0 1\0"))
        self.assertFalse(fault.suppress("other", b"C", b"COMMIT\0"))
        self.assertTrue(fault.suppress("chosen", b"C", b"COMMIT\0"))
        self.assertEqual(1, fault.confirmed)
        self.assertFalse(fault.suppress("chosen", b"C", b"COMMIT\0"))

    def test_expired_arm_and_malformed_bind_do_not_fault(self):
        fault = Fault()
        with self.assertRaises(ValueError):
            fault.arm("outside-proof")
        fault.arm("knora-otp-proof:synthetic")
        fault.deadline = 0
        self.assertFalse(fault.claim("chosen", b"B", b"\0\0"))
        self.assertFalse(fault.suppress("chosen", b"C", b"COMMIT\0"))
        self.assertEqual([], bind_parameters(b"\0\0"))


class FramingTests(unittest.IsolatedAsyncioTestCase):
    async def test_fragmented_real_commit_completion_frame_is_reassembled(self):
        reader = asyncio.StreamReader()
        frame = b"C" + struct.pack("!I", 11) + b"COMMIT\0"
        reader.feed_data(frame[:3])
        pending = asyncio.create_task(read_packet(reader))
        await asyncio.sleep(0)
        self.assertFalse(pending.done())
        reader.feed_data(frame[3:])
        kind, payload, observed = await pending
        self.assertEqual((b"C", b"COMMIT\0", frame), (kind, payload, observed))

    async def test_oversized_and_truncated_frames_fail_closed(self):
        for frame, error in (
            (b"B" + struct.pack("!I", MAX_PACKET + 1), ValueError),
            (b"C" + struct.pack("!I", 11) + b"COM", asyncio.IncompleteReadError),
        ):
            reader = asyncio.StreamReader()
            reader.feed_data(frame)
            reader.feed_eof()
            with self.assertRaises(error):
                await read_packet(reader)


if __name__ == "__main__":
    if "--serve" in sys.argv:
        asyncio.run(serve())
    else:
        unittest.main()
