import pytest

from unittest.mock import Mock

from src.edtech_image_service import CourseImageRequest, plan_course_image, store_course_image


def test_course_thumbnail_plan_is_stable_and_scoped():
    request = CourseImageRequest("course-42", "cover.png", "image/png", "aGVsbG8=")
    plan = plan_course_image(request)
    assert plan.key == "courses/course-42/cover.png"
    assert (plan.width, plan.height, plan.fit) == (640, 360, "cover")


def test_invalid_dimensions_are_rejected_before_upload():
    request = CourseImageRequest("course-42", "cover.png", "image/png", "aGVsbG8=", width=0)
    with pytest.raises(ValueError, match="positive"):
        plan_course_image(request)


@pytest.mark.parametrize("stage", ["presign_put", "process_image"])
def test_failed_intake_deletes_created_bucket(stage):
    client = Mock()
    getattr(client, stage).side_effect = RuntimeError("intake failed")
    request = CourseImageRequest("course-42", "cover.png", "image/png", "aGVsbG8=")
    with pytest.raises(RuntimeError, match="intake failed"):
        store_course_image(client, request)
    client.delete_bucket.assert_called_once_with("edtech-course-images")


def test_failed_bucket_creation_does_not_delete_existing_bucket():
    client = Mock()
    client.create_bucket.side_effect = RuntimeError("already exists")
    with pytest.raises(RuntimeError, match="already exists"):
        store_course_image(client, CourseImageRequest("course-42", "cover.png", "image/png", "aGVsbG8="))
    client.delete_bucket.assert_not_called()


def test_image_process_uses_pipeline_contract():
    from src.edtech_image_service import InfraiClient

    client = InfraiClient(api_key="test")
    client.request = Mock(return_value={})
    client.process_image("encoded-image", 640, 360)
    client.request.assert_called_once_with(
        "POST", "/v1/image/process",
        {"image": {"base64": "encoded-image"},
         "ops": [{"op": "resize", "params": {
             "width": 640, "height": 360, "fit": "cover", "enlarge": False}}],
         "format": "webp", "store": True},
    )
