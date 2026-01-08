from app.media import parse_ffprobe_json


def test_parse_ffprobe_json() -> None:
    payload = {
        "streams": [
            {"codec_type": "video", "width": 1920, "height": 1080},
            {"codec_type": "audio"},
        ],
        "format": {"duration": "12.34"},
    }
    parsed = parse_ffprobe_json(payload)
    assert parsed["has_video"] is True
    assert parsed["duration"] == 12.34
    assert parsed["width"] == 1920
    assert parsed["height"] == 1080