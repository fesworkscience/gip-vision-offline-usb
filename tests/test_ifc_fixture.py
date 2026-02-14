from __future__ import annotations

import unittest
from pathlib import Path

import ifcopenshell

ROOT_DIR = Path(__file__).resolve().parents[1]
FIXTURE_IFC = ROOT_DIR / "tests" / "fixtures" / "sample.ifc"


class IfcFixtureTest(unittest.TestCase):
    def test_fixture_exists(self) -> None:
        self.assertTrue(FIXTURE_IFC.exists(), f"Missing fixture: {FIXTURE_IFC}")

    def test_fixture_has_ifc_header(self) -> None:
        header = FIXTURE_IFC.read_text(encoding="utf-8", errors="ignore")[:256].upper()
        self.assertIn("ISO-10303-21", header)

    def test_fixture_can_be_opened_by_ifcopenshell(self) -> None:
        model = ifcopenshell.open(str(FIXTURE_IFC))
        self.assertIsNotNone(model)
        self.assertGreater(len(model.by_type("IfcProject")), 0)


if __name__ == "__main__":
    unittest.main()
