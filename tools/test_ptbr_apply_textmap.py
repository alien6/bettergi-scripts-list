import unittest

from ptbr_apply_textmap import apply_line


class ApplyTextMapTests(unittest.TestCase):
    def test_localizes_resolved_literals_inside_direct_helper_array(self):
        source = 'const result = await findText(["点击", "继续"], 610, 950, 700, 60);'
        resolved = {"点击", "继续"}

        migrated = apply_line(source, resolved)

        self.assertIn('genshin.getTextLiteral("点击")', migrated)
        self.assertIn('genshin.getTextLiteral("继续")', migrated)

    def test_direct_helper_array_migration_is_idempotent(self):
        source = 'const result = await findText(["点击", "继续"], 610, 950, 700, 60);'
        resolved = {"点击", "继续"}

        once = apply_line(source, resolved)
        twice = apply_line(once, resolved)

        self.assertEqual(once, twice)

    def test_localizes_known_literal_in_custom_tcg_ocr_helpers(self):
        resolved = {"出战角色"}

        wait_line = 'await waitForTextAppear("出战角色", [1766, 850, 118, 43]);'
        click_line = 'await recognizeTextAndClick("出战角色", [1766, 850, 118, 43]);'

        self.assertIn('genshin.getTextLiteral("出战角色")', apply_line(wait_line, resolved))
        self.assertIn('genshin.getTextLiteral("出战角色")', apply_line(click_line, resolved))


if __name__ == "__main__":
    unittest.main()
