import os
import tempfile
import unittest
from pathlib import Path

from scripts.build import process_markdown_file


class TestDiskDirective(unittest.TestCase):
    def test_standalone_disk_offline_injects_note(self):
        with tempfile.TemporaryDirectory() as td:
            md = Path(td) / "page.md"
            md.write_text("# Page\n\nSome text.\n\n<!-- disk -->\n\nMore text.\n", encoding="utf-8")
            out = process_markdown_file(md, dbname="demo_db", offline=True)
            self.assertIn("(Offline build: disk usage not generated)", out)
            # Should not create a details block in offline mode for standalone
            self.assertNotIn("<summary>Output</summary>", out)

    def test_no_double_render_when_preceding_code_fence(self):
        with tempfile.TemporaryDirectory() as td:
            md = Path(td) / "page.md"
            md.write_text("# Page\n\n<!-- disk -->\n```sql\nSELECT 1;\n```\n", encoding="utf-8")
            out = process_markdown_file(md, dbname="demo_db", offline=True)
            # Expect exactly one disk offline message
            self.assertEqual(out.count("disk usage not generated"), 1)
            # And expect a details block exists (injected for the SQL block output)
            self.assertIn("<summary>Output</summary>", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)

