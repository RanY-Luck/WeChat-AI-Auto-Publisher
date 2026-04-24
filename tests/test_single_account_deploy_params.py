from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SingleAccountDeployParamsTests(unittest.TestCase):
    def test_compose_uses_env_driven_deployment_identifiers(self):
        compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn('container_name: ${CONTAINER_NAME:-wechat-publisher}', compose_text)
        self.assertIn('image: ${IMAGE_NAME:-wechat-ai-publisher:latest}', compose_text)
        self.assertIn('- "${HOST_NOVNC_PORT:-6080}:6080"', compose_text)
        self.assertIn('- "${HOST_VNC_PORT:-5900}:5900"', compose_text)
        self.assertIn('- wechat-profile-data:/data/wechat-profile', compose_text)
        self.assertIn('name: ${WECHAT_PROFILE_VOLUME:-wechat-profile-data}', compose_text)

    def test_env_example_documents_multi_deploy_variables(self):
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

        for expected in (
            "COMPOSE_PROJECT_NAME=",
            "CONTAINER_NAME=",
            "IMAGE_NAME=",
            "HOST_NOVNC_PORT=",
            "HOST_VNC_PORT=",
            "WECHAT_PROFILE_VOLUME=",
        ):
            self.assertIn(expected, env_example)

    def test_build_release_script_reads_image_name_from_env(self):
        script_text = (ROOT / "build_release.bat").read_text(encoding="utf-8")

        self.assertIn('for /f "usebackq tokens=1,* delims==" %%A in (".env") do (', script_text)
        self.assertIn('if /I "%%~A"=="IMAGE_NAME" set "IMAGE_NAME=%%~B"', script_text)
        self.assertIn('if not defined IMAGE_NAME set "IMAGE_NAME=wechat-ai-publisher:latest"', script_text)
        self.assertIn('docker build -t "%IMAGE_NAME%" .', script_text)
        self.assertIn('docker save -o "%TAR_PATH%" "%IMAGE_NAME%"', script_text)

    def test_build_release_script_includes_cover_pool_assets(self):
        script_text = (ROOT / "build_release.bat").read_text(encoding="utf-8")

        self.assertIn('mkdir "%RELEASE_DIR%\\cover_pool"', script_text)
        self.assertIn('if exist "cover_pool" xcopy /e /i /y "cover_pool" "%RELEASE_DIR%\\cover_pool" >nul', script_text)
        self.assertIn('echo   - cover_pool\\*', script_text)

    def test_deploy_script_loads_env_and_uses_resolved_names(self):
        script_text = (ROOT / "deploy_centos7.sh").read_text(encoding="utf-8")

        self.assertIn('load_env_file() {', script_text)
        self.assertIn("line=\"${line%$'\\r'}\"", script_text)
        self.assertIn('export "$line"', script_text)
        self.assertIn('load_env_file ".env"', script_text)
        self.assertIn('IMAGE_NAME="${IMAGE_NAME:-wechat-ai-publisher:latest}"', script_text)
        self.assertIn('CONTAINER_NAME="${CONTAINER_NAME:-wechat-publisher}"', script_text)
        self.assertIn('docker load -i "$TAR_PATH"', script_text)


if __name__ == "__main__":
    unittest.main()
