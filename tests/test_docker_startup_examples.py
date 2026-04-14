import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parent.parent
START_SH_PATH = ROOT / "docker" / "start.sh"
COMPOSE_PATH = ROOT / "docker-compose.yml"
COMPOSE_EXAMPLE_PATH = ROOT / "docker-compose.yml.example"
MULTI_COMPOSE_PATH = ROOT / "docker-compose.multi.yml"
ENV_EXAMPLE_PATH = ROOT / ".env.example"
INSTANCE_TEMPLATE_ENV_PATH = ROOT / "instances" / "_template" / ".env.example"
INSTANCE_TEMPLATE_CONFIG_PATH = ROOT / "instances" / "_template" / "config.py.example"
DOCKERIGNORE_PATH = ROOT / ".dockerignore"
DOCKERFILE_PATH = ROOT / "Dockerfile"
README_PATH = ROOT / "README.md"


class DockerStartupExamplesTest(unittest.TestCase):
    def test_dockerfile_does_not_install_playwright_browser_binaries(self):
        dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")

        self.assertNotIn("python -m playwright install chromium", dockerfile)

    def test_dockerfile_does_not_include_runtime_dev_packages(self):
        dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")

        self.assertNotIn("libjpeg-dev", dockerfile)
        self.assertNotIn("libpng-dev", dockerfile)
        self.assertNotIn("zlib1g-dev", dockerfile)

    def test_dockerignore_excludes_runtime_browser_profile(self):
        dockerignore = DOCKERIGNORE_PATH.read_text(encoding="utf-8")

        self.assertIn("wechat-profile/", dockerignore)

    def test_dockerignore_excludes_real_instance_configs_but_keeps_templates_in_repo(self):
        dockerignore = DOCKERIGNORE_PATH.read_text(encoding="utf-8")

        self.assertIn("instances/*", dockerignore)
        self.assertIn("!instances/_template/", dockerignore)

    def test_dockerignore_excludes_release_artifacts_from_build_context(self):
        dockerignore = DOCKERIGNORE_PATH.read_text(encoding="utf-8")

        self.assertIn("release/", dockerignore)
        self.assertIn("release.zip", dockerignore)

    def test_start_script_validates_mounted_config_file(self):
        start_script = START_SH_PATH.read_text(encoding="utf-8")

        self.assertIn('if [ -d "/app/config/config.py" ]; then', start_script)
        self.assertIn('if [ ! -f "/app/config/config.py" ]; then', start_script)
        self.assertIn("Mounted config path is a directory", start_script)
        self.assertIn("Expected a file at /app/config/config.py", start_script)

    def test_start_script_waits_for_xvfb_socket_before_x11vnc(self):
        start_script = START_SH_PATH.read_text(encoding="utf-8")

        self.assertIn('DISPLAY_NUMBER="${DISPLAY#:}"', start_script)
        self.assertIn('DISPLAY_SOCKET="/tmp/.X11-unix/X${DISPLAY_NUMBER}"', start_script)
        self.assertIn('[ -S "${DISPLAY_SOCKET}" ]', start_script)

    def test_start_script_cleans_stale_profile_locks_before_auto_open(self):
        start_script = START_SH_PATH.read_text(encoding="utf-8")

        self.assertIn('cleanup_stale_profile_lock()', start_script)
        self.assertIn('SingletonCookie', start_script)
        self.assertIn('SingletonLock', start_script)
        self.assertIn('SingletonSocket', start_script)
        self.assertIn('cleanup_stale_profile_lock', start_script)

    def test_start_script_supports_auto_open_browser(self):
        start_script = START_SH_PATH.read_text(encoding="utf-8")

        self.assertIn('AUTO_OPEN_BROWSER="${AUTO_OPEN_BROWSER:-false}"', start_script)
        self.assertIn("https://mp.weixin.qq.com", start_script)
        self.assertIn("--user-data-dir=", start_script)
        self.assertIn("chromium", start_script)

    def test_compose_example_exposes_auto_open_browser_env(self):
        compose_example = COMPOSE_EXAMPLE_PATH.read_text(encoding="utf-8")

        self.assertIn("AUTO_OPEN_BROWSER: ${AUTO_OPEN_BROWSER:-true}", compose_example)
        self.assertIn("./config/config.py:/app/config/config.py:ro", compose_example)

    def test_compose_files_allow_overriding_host_ports_from_env(self):
        expected_port_lines = [
            '- "${NOVNC_HOST_PORT:-6080}:6080"',
            '- "${VNC_HOST_PORT:-5900}:5900"',
        ]

        for compose_path in (COMPOSE_PATH, COMPOSE_EXAMPLE_PATH):
            compose_text = compose_path.read_text(encoding="utf-8")
            for expected_line in expected_port_lines:
                self.assertIn(expected_line, compose_text)

    def test_env_example_documents_auto_open_browser_default(self):
        env_example = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")

        self.assertIn("AUTO_OPEN_BROWSER=true", env_example)

    def test_env_example_documents_overridable_host_ports(self):
        env_example = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")

        self.assertIn("# NOVNC_HOST_PORT=6080", env_example)
        self.assertIn("# VNC_HOST_PORT=5900", env_example)

    def test_multi_compose_exists_with_isolated_instance_examples(self):
        self.assertTrue(MULTI_COMPOSE_PATH.exists())
        multi_compose = MULTI_COMPOSE_PATH.read_text(encoding="utf-8")

        self.assertIn("wechat-foo:", multi_compose)
        self.assertIn("wechat-bar:", multi_compose)
        self.assertIn("./instances/foo/.env", multi_compose)
        self.assertIn("./instances/bar/.env", multi_compose)
        self.assertIn("./instances/foo/config.py:/app/config/config.py:ro", multi_compose)
        self.assertIn("./instances/bar/config.py:/app/config/config.py:ro", multi_compose)
        self.assertIn("wechat-profile-foo:/data/wechat-profile", multi_compose)
        self.assertIn("wechat-profile-bar:/data/wechat-profile", multi_compose)

    def test_instance_template_files_exist_and_document_required_fields(self):
        self.assertTrue(INSTANCE_TEMPLATE_ENV_PATH.exists())
        self.assertTrue(INSTANCE_TEMPLATE_CONFIG_PATH.exists())

        env_example = INSTANCE_TEMPLATE_ENV_PATH.read_text(encoding="utf-8")
        self.assertIn("INSTANCE_SLUG=", env_example)
        self.assertIn("INSTANCE_NAME=", env_example)
        self.assertIn("BARK_TITLE_PREFIX=", env_example)
        self.assertIn("VNC_PASSWORD=", env_example)
        self.assertIn("AUTO_OPEN_BROWSER=", env_example)
        self.assertNotIn("NOVNC_HOST_PORT=", env_example)
        self.assertNotIn("VNC_HOST_PORT=", env_example)

        config_example = INSTANCE_TEMPLATE_CONFIG_PATH.read_text(encoding="utf-8")
        self.assertIn("WECHAT_CONFIG", config_example)
        self.assertIn("browser_profile_dir", config_example)

    def test_readme_documents_multi_instance_deploy_and_scan_mapping(self):
        readme = README_PATH.read_text(encoding="utf-8")

        self.assertIn("docker-compose.multi.yml", readme)
        self.assertIn("instances/_template/", readme)
        self.assertIn("INSTANCE_SLUG", readme)
        self.assertIn("INSTANCE_NAME", readme)
        self.assertIn("BARK_TITLE_PREFIX", readme)
        self.assertIn("宿主机端口直接写在 `docker-compose.multi.yml`", readme)
        self.assertIn("简称", readme)
        self.assertIn("noVNC", readme)
        self.assertIn("二维码", readme)


if __name__ == "__main__":
    unittest.main()
