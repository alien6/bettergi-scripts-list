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


if __name__ == "__main__":
    unittest.main()
