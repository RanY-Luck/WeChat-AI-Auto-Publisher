from pathlib import Path
import unittest


class BuildReleaseScriptTest(unittest.TestCase):
    def test_build_release_bat_exists_and_checks_required_inputs(self):
        script_path = Path("build_release.bat")
        self.assertTrue(script_path.exists(), "build_release.bat should exist")

        content = script_path.read_text(encoding="utf-8")
        required_tokens = [
            ".env",
            "docker-compose.yml",
            "config\\config.py",
            "deploy_centos7.sh",
            "docker build -t wechat-ai-publisher:latest .",
            "docker save -o",
            "release.zip",
        ]

        for token in required_tokens:
            self.assertIn(token, content)

    def test_deploy_centos7_script_exists_and_contains_release_flow(self):
        script_path = Path("deploy_centos7.sh")
        self.assertTrue(script_path.exists(), "deploy_centos7.sh should exist")

        content = script_path.read_text(encoding="utf-8")
        required_tokens = [
            "docker load -i wechat-ai-publisher.tar",
            "docker compose up -d",
            "docker-compose up -d",
            "docker compose down",
            "docker-compose down",
            "docker image rm",
        ]

        for token in required_tokens:
            self.assertIn(token, content)


if __name__ == "__main__":
    unittest.main()
