import tempfile
import unittest
from pathlib import Path

import ptbr_strict_scan


class StrictScanTests(unittest.TestCase):
    def test_commented_functional_call_is_not_reported(self):
        old_root = ptbr_strict_scan.ROOT
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / "repo" / "js" / "fixture.js"
                path.parent.mkdir(parents=True)
                path.write_text(
                    '// await genshin.chooseTalkOption("给我一份福利餐");\n'
                    'await genshin.chooseTalkOption("能给我几支香吗");\n',
                    encoding="utf-8",
                )
                ptbr_strict_scan.ROOT = root

                blockers, covered = ptbr_strict_scan.scan(path, set())

                self.assertEqual(["能给我几支香吗"], [item["literal"] for item in blockers])
                self.assertEqual([], covered)
        finally:
            ptbr_strict_scan.ROOT = old_root


if __name__ == "__main__":
    unittest.main()
