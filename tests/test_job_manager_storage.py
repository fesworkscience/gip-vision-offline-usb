from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.job_manager import JobManager


class JobManagerStorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.workspace = root / "workspace"
        self.ifc_dir = root / "ifc"
        self.usdz_dir = root / "usdz"
        self.manager = JobManager(base_dir=self.workspace, input_dir=self.ifc_dir, output_dir=self.usdz_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_external_input_output_paths(self) -> None:
        record = self.manager.create_job()
        record = self.manager.update(record.id, input_name="demo.ifc")

        input_path = self.manager.input_path(record)
        output_name = self.manager.output_file_name(record)
        final_output_path = self.manager.final_output_path(record, output_name)

        self.assertEqual(input_path.parent, self.ifc_dir.resolve())
        self.assertEqual(final_output_path.parent, self.usdz_dir.resolve())
        self.assertTrue(input_path.name.startswith(f"{record.id}_"))
        self.assertTrue(final_output_path.name.startswith(f"{record.id}_"))

    def test_cleanup_does_not_delete_ifc_or_usdz_content(self) -> None:
        record = self.manager.create_job()
        record = self.manager.update(record.id, input_name="demo.ifc")

        input_path = self.manager.input_path(record)
        output_name = self.manager.output_file_name(record)
        output_path = self.manager.final_output_path(record, output_name)

        input_path.write_text("ifc-bytes")
        output_path.write_text("usdz-bytes")

        self.manager.set_done(record.id, output_name=output_name, metadata={})

        stale_record = self.manager.get(record.id)
        assert stale_record is not None
        stale_record.updated_at = datetime.now(timezone.utc) - timedelta(days=30)
        self.manager._write_meta(stale_record)

        removed = self.manager.cleanup_expired()
        self.assertEqual(removed, 1)
        self.assertTrue(input_path.exists())
        self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()
