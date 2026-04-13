from pathlib import Path
import unittest


class RequirementsLockfileTest(unittest.TestCase):
    def test_requirements_are_fully_pinned_and_include_playwright(self):
        requirements_path = Path("requirements.txt")
        self.assertTrue(requirements_path.exists(), "requirements.txt should exist")

        lines = [
            line.strip()
            for line in requirements_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        self.assertTrue(lines, "requirements.txt should not be empty")
        self.assertTrue(
            any(line.startswith("playwright==") for line in lines),
            "requirements.txt should include a pinned playwright dependency",
        )

        for line in lines:
            self.assertIn("==", line, f"dependency should be pinned with ==: {line}")


if __name__ == "__main__":
    unittest.main()
