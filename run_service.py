import json
import sys

from src.edtech_image_service import CourseImageRequest, InfraiClient, store_course_image


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python run_service.py request.json", file=sys.stderr)
        return 2
    with open(sys.argv[1], encoding="utf-8") as handle:
        payload = json.load(handle)
    result = store_course_image(InfraiClient(), CourseImageRequest(**payload))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
