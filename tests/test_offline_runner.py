from __future__ import annotations

import unittest

from app import offline_runner


class OfflineRunnerTest(unittest.TestCase):
    def test_loopback_target_detection(self) -> None:
        self.assertTrue(offline_runner._is_loopback_target(("127.0.0.1", 8765)))
        self.assertTrue(offline_runner._is_loopback_target(("::1", 8765)))
        self.assertTrue(offline_runner._is_loopback_target("localhost"))

    def test_non_loopback_target_detection(self) -> None:
        self.assertFalse(offline_runner._is_loopback_target(("8.8.8.8", 53)))
        self.assertFalse(offline_runner._is_loopback_target(("example.com", 443)))


if __name__ == "__main__":
    unittest.main()
