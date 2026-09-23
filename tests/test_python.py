import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/python"))
from processing import process_emails

PAYLOADS = json.loads(Path(__file__).with_name("payloads.json").read_text())
PREFIX = "[connector-pivots]"


class ProcessingTests(unittest.IsolatedAsyncioTestCase):
    async def test_prefix_filter(self):
        ids = []
        async def flag(message_id):
            ids.append(message_id)
        result = await process_emails(PAYLOADS["mixed"], flag, PREFIX)
        self.assertEqual(ids, ["test-1", "test-2"])
        self.assertEqual(result, {"received": 3, "flagged": 2})

    async def test_empty(self):
        async def fail(_):
            self.fail("Unexpected action")
        self.assertEqual(await process_emails(PAYLOADS["empty"], fail, PREFIX),
                         {"received": 0, "flagged": 0})

    async def test_invalid(self):
        async def fail(_):
            self.fail("Unexpected action")
        for payload in PAYLOADS["invalid"]:
            with self.assertRaises(ValueError):
                await process_emails(payload, fail, PREFIX)
        with self.assertRaises(ValueError):
            await process_emails(PAYLOADS["mixed"], fail, "")

    async def test_action_failure(self):
        async def fail(_):
            raise RuntimeError("Action failed")
        with self.assertRaises(RuntimeError):
            await process_emails(PAYLOADS["mixed"], fail, PREFIX)


if __name__ == "__main__":
    unittest.main()
