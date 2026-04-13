import base64
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import requests

from utils.imgbb_uploader import ImgbbUploader


def _write_temp_file(data: bytes) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False)
    try:
        tmp.write(data)
        tmp.flush()
    finally:
        tmp.close()
    return tmp.name


class ImgbbUploaderTest(unittest.TestCase):
    @patch("utils.imgbb_uploader.requests.post")
    def test_upload_posts_encoded_image_and_returns_display_url(self, mock_post):
        mock_post.return_value = SimpleNamespace(
            status_code=200,
            text="ok",
            json=lambda: {
                "success": True,
                "data": {"display_url": "https://imgbb.com/example"},
            },
        )
        uploader = ImgbbUploader(api_key="test-key", expiration=600)
        temp_path = _write_temp_file(b"abc")
        try:
            result = uploader.upload(temp_path)
        finally:
            os.remove(temp_path)

        self.assertEqual(result, "https://imgbb.com/example")
        mock_post.assert_called_once()
        called_url = mock_post.call_args[0][0]
        called_data = mock_post.call_args.kwargs["data"]
        self.assertEqual(called_url, ImgbbUploader.API_ENDPOINT)
        self.assertEqual(called_data["key"], "test-key")
        self.assertEqual(
            called_data["image"],
            base64.b64encode(b"abc").decode("ascii"),
        )
        self.assertEqual(called_data["expiration"], 600)

    @patch("utils.imgbb_uploader.requests.post")
    def test_upload_respects_overridden_expiration(self, mock_post):
        mock_post.return_value = SimpleNamespace(
            status_code=200,
            text="ok",
            json=lambda: {
                "success": True,
                "data": {"display_url": "https://imgbb.com/custom-expiration"},
            },
        )
        uploader = ImgbbUploader(api_key="another-key", expiration=600)
        temp_path = _write_temp_file(b"xyz")
        try:
            uploader.upload(temp_path, expiration=120)
        finally:
            os.remove(temp_path)

        called_data = mock_post.call_args.kwargs["data"]
        self.assertEqual(called_data["expiration"], 120)

    @patch("utils.imgbb_uploader.requests.post")
    def test_upload_raises_on_http_error(self, mock_post):
        mock_post.return_value = SimpleNamespace(status_code=500, text="server error")
        uploader = ImgbbUploader(api_key="test-key", expiration=600)
        temp_path = _write_temp_file(b"abc")
        try:
            with self.assertRaises(RuntimeError) as ctx:
                uploader.upload(temp_path)
        finally:
            os.remove(temp_path)

        self.assertIn("500", str(ctx.exception))

    @patch("utils.imgbb_uploader.requests.post")
    def test_upload_converts_request_exceptions(self, mock_post):
        mock_post.side_effect = requests.RequestException("timeout")
        uploader = ImgbbUploader(api_key="test-key", expiration=600)
        temp_path = _write_temp_file(b"abc")
        try:
            with self.assertRaises(RuntimeError) as ctx:
                uploader.upload(temp_path)
        finally:
            os.remove(temp_path)

        self.assertIn("request failed", str(ctx.exception))

    @patch("utils.imgbb_uploader.requests.post")
    def test_upload_reports_file_read_failure(self, mock_post):
        mock_post.return_value = SimpleNamespace(status_code=200, text="ok", json=lambda: {})
        uploader = ImgbbUploader(api_key="test-key", expiration=600)
        with patch("builtins.open", side_effect=OSError("boom")):
            with self.assertRaises(RuntimeError) as ctx:
                uploader.upload("missing.png")

        self.assertIn("read image file", str(ctx.exception))
        mock_post.assert_not_called()

    @patch("utils.imgbb_uploader.requests.post")
    def test_upload_raises_when_api_reports_failure(self, mock_post):
        mock_post.return_value = SimpleNamespace(
            status_code=200,
            text="ok",
            json=lambda: {"success": False, "error": {"message": "bad"}},
        )
        uploader = ImgbbUploader(api_key="test-key", expiration=600)
        temp_path = _write_temp_file(b"abc")
        try:
            with self.assertRaises(RuntimeError) as ctx:
                uploader.upload(temp_path)
        finally:
            os.remove(temp_path)

        self.assertIn("bad", str(ctx.exception))

    @patch("utils.imgbb_uploader.requests.post")
    def test_upload_requires_display_url(self, mock_post):
        mock_post.return_value = SimpleNamespace(
            status_code=200,
            text="ok",
            json=lambda: {"success": True, "data": {}},
        )
        uploader = ImgbbUploader(api_key="test-key", expiration=600)
        temp_path = _write_temp_file(b"abc")
        try:
            with self.assertRaises(RuntimeError) as ctx:
                uploader.upload(temp_path)
        finally:
            os.remove(temp_path)

        self.assertIn("display_url", str(ctx.exception))

    @patch("utils.imgbb_uploader.requests.post")
    def test_upload_handles_invalid_json(self, mock_post):
        def _bad_json():
            raise ValueError("boom")

        mock_post.return_value = SimpleNamespace(
            status_code=200,
            text="ok",
            json=_bad_json,
        )
        uploader = ImgbbUploader(api_key="test-key", expiration=600)
        temp_path = _write_temp_file(b"abc")
        try:
            with self.assertRaises(RuntimeError) as ctx:
                uploader.upload(temp_path)
        finally:
            os.remove(temp_path)

        self.assertIn("invalid JSON", str(ctx.exception))

    @patch("utils.imgbb_uploader.requests.post")
    def test_upload_handles_non_dict_payload(self, mock_post):
        mock_post.return_value = SimpleNamespace(
            status_code=200,
            text="ok",
            json=lambda: ["not", "dict"],
        )
        uploader = ImgbbUploader(api_key="test-key", expiration=600)
        temp_path = _write_temp_file(b"abc")
        try:
            with self.assertRaises(RuntimeError) as ctx:
                uploader.upload(temp_path)
        finally:
            os.remove(temp_path)

        self.assertIn("unexpected payload", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
