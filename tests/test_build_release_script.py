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
            "docker-compose.multi.yml",
            "config\\config.py",
            "deploy_centos7.sh",
            "docker build -t wechat-ai-publisher:latest .",
            "docker save -o",
            "instances",
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
            "COMPOSE_FILE",
            "docker-compose.multi.yml",
            "instances",
        ]

        for token in required_tokens:
            self.assertIn(token, content)

    def test_deploy_centos7_script_auto_prefers_multi_instance_compose_when_available(self):
        script_path = Path("deploy_centos7.sh")
        content = script_path.read_text(encoding="utf-8")

        self.assertIn("default_compose_file()", content)
        self.assertIn('if [ -f "$MULTI_INSTANCE_COMPOSE_FILE" ] && [ -d "instances" ]; then', content)
        self.assertIn('echo "$MULTI_INSTANCE_COMPOSE_FILE"', content)

    def test_deploy_centos7_script_cleans_orphan_containers_on_down_and_up(self):
        script_path = Path("deploy_centos7.sh")
        content = script_path.read_text(encoding="utf-8")

        self.assertIn("down --remove-orphans", content)
        self.assertIn("up -d --remove-orphans", content)


if __name__ == "__main__":
    unittest.main()
