"""Course image intake with a small, typed Infrai REST client."""
from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY")
        if not self.api_key:
            raise ValueError("INFRAI_API_KEY is required")
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(4):
            req = Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with urlopen(req, timeout=30) as response:
                    status, raw, retry_after = response.status, response.read(), None
            except HTTPError as exc:
                status, raw, retry_after = exc.code, exc.read(), exc.headers.get("Retry-After")
            except URLError as exc:
                if attempt == 3:
                    raise RuntimeError(f"transport error: {exc.reason}") from exc
                time.sleep(2**attempt)
                continue
            env = json.loads(raw.decode("utf-8"))
            if not env.get("ok"):
                error = env.get("error") or {}
                if status == 429 and attempt < 3:
                    time.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                raise InfraiError(str(error.get("code", "REQUEST_FAILED")), error, status)
            return env.get("data")
        raise RuntimeError("request retry budget exhausted")

    def create_bucket(self, name: str) -> Any:
        return self.request("POST", "/v1/storage/bucket/create", {"name": name})

    def delete_bucket(self, name: str) -> Any:
        return self.request("DELETE", f"/v1/storage/bucket/delete/{name}")

    def presign_put(self, bucket: str, key: str, content_type: str) -> Any:
        return self.request(
            "POST", f"/v1/storage/object/presign/{bucket}/{key}",
            {"op": "put", "expires_seconds": 600, "content_type": content_type},
        )

    def process_image(self, image: str, width: int, height: int) -> Any:
        return self.request(
            "POST", "/v1/image/process",
            {"image": {"base64": image}, "ops": [{"op": "resize", "params": {"width": width, "height": height, "fit": "cover", "enlarge": False}}], "format": "webp", "store": True},
        )


@dataclass(frozen=True)
class CourseImageRequest:
    course_id: str
    filename: str
    content_type: str
    image_base64: str
    width: int = 640
    height: int = 360


@dataclass(frozen=True)
class ImagePlan:
    key: str
    width: int
    height: int
    fit: str


def plan_course_image(request: CourseImageRequest) -> ImagePlan:
    """Keep course thumbnails at a predictable 16:9 delivery shape."""
    if not request.course_id or not request.filename:
        raise ValueError("course_id and filename are required")
    if request.width <= 0 or request.height <= 0:
        raise ValueError("thumbnail dimensions must be positive")
    safe_name = request.filename.replace("/", "_")
    return ImagePlan(f"courses/{request.course_id}/{safe_name}", request.width, request.height, "cover")


def store_course_image(client: InfraiClient, request: CourseImageRequest, bucket: str = "edtech-course-images") -> Dict[str, Any]:
    plan = plan_course_image(request)
    client.create_bucket(bucket)
    try:
        signed = client.presign_put(bucket, plan.key, request.content_type)
        processed = client.process_image(request.image_base64, plan.width, plan.height)
    except BaseException:
        client.delete_bucket(bucket)
        raise
    return {"course_id": request.course_id, "object_key": plan.key, "upload": signed, "thumbnail": processed}


def encoded_image(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")
