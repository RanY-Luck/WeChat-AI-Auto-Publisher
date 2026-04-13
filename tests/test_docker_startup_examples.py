import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parent.parent
START_SH_PATH = ROOT / "docker" / "start.sh"
COMPOSE_EXAMPLE_PATH = ROOT / "docker-compose.yml.example"
ENV_EXAMPLE_PATH = ROOT / ".env.example"
DOCKERIGNORE_PATH = ROOT / ".dockerignore"
DOCKERFILE_PATH = ROOT / "Dockerfile"


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

    def test_env_example_documents_auto_open_browser_default(self):
        env_example = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")

        self.assertIn("AUTO_OPEN_BROWSER=true", env_example)


if __name__ == "__main__":
    unittest.main()
