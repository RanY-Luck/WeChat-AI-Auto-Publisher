import base64
from typing import Any

import requests
from requests.exceptions import RequestException


class ImgbbUploader:
    API_ENDPOINT = "https://api.imgbb.com/1/upload"

    def __init__(self, api_key: str, expiration: int = 600):
        self.api_key = api_key
        self.expiration = expiration

    def upload(self, path: str, expiration: int | None = None) -> str:
        try:
            with open(path, "rb") as handle:
                image_bytes = handle.read()
        except OSError as exc:
            raise RuntimeError("imgbb upload failed to read image file") from exc

        payload: dict[str, Any] = {
            "key": self.api_key,
            "image": base64.b64encode(image_bytes).decode("ascii"),
            "expiration": expiration if expiration is not None else self.expiration,
        }

        try:
            response = requests.post(self.API_ENDPOINT, data=payload, timeout=10)
        except RequestException as exc:
            raise RuntimeError("imgbb upload request failed") from exc
        if response.status_code != 200:
            raise RuntimeError(
                f"imgbb upload failed ({response.status_code}): {response.text}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("imgbb returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("imgbb returned unexpected payload")

        if not payload.get("success"):
            message = payload.get("error", {}).get("message", "unknown")
            raise RuntimeError(f"imgbb responded with failure: {message}")

        data = payload.get("data")
        if not data or "display_url" not in data:
            raise RuntimeError("imgbb response missing display_url")

        return data["display_url"]
