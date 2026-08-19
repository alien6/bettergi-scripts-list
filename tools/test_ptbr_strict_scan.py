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

    def test_cjk_regex_used_to_parse_ocr_text_is_reported(self):
        old_root = ptbr_strict_scan.ROOT
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / "repo" / "js" / "fixture.js"
                path.parent.mkdir(parents=True)
                path.write_text(
                    'const levelText = result.text;\n'
                    'const levelMatch = levelText.match(/冒险等阶\\s*(\\d+)/);\n',
                    encoding="utf-8",
                )
                ptbr_strict_scan.ROOT = root

                blockers, covered = ptbr_strict_scan.scan(path, set())

                self.assertEqual(["冒险等阶"], [item["literal"] for item in blockers])
                self.assertEqual([], covered)
        finally:
            ptbr_strict_scan.ROOT = old_root

    def test_local_ocr_text_variable_string_methods_are_reported(self):
        old_root = ptbr_strict_scan.ROOT
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / "repo" / "js" / "fixture.js"
                path.parent.mkdir(parents=True)
                path.write_text(
                    'const requestText = requestRegion.text.trim();\n'
                    "if (requestText.endsWith('拒绝了多人游戏申请')) fail();\n"
                    "if (requestText.startsWith('无法进入')) fail();\n",
                    encoding="utf-8",
                )
                ptbr_strict_scan.ROOT = root

                blockers, covered = ptbr_strict_scan.scan(path, set())

                self.assertEqual(
                    ["拒绝了多人游戏申请", "无法进入"],
                    [item["literal"] for item in blockers],
                )
                self.assertEqual([], covered)
        finally:
            ptbr_strict_scan.ROOT = old_root


if __name__ == "__main__":
    unittest.main()
