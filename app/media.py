from __future__ import annotations

from typing import Any


def parse_ffprobe_json(payload: dict[str, Any]) -> dict[str, int | float | bool]:
    streams = payload.get("streams", [])
    format_info = payload.get("format", {})
    duration_raw = format_info.get("duration")
    duration = float(duration_raw) if duration_raw else 0.0

    video_stream = None
    for stream in streams:
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if not video_stream:
        return {"has_video": False, "duration": duration, "width": 0, "height": 0}

    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    return {
        "has_video": True,
        "duration": duration,
        "width": width,
        "height": height,
    }


def parse_timecode(value: str) -> float:
    parts = value.split(":")
    if len(parts) != 3:
        return 0.0
    hours = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds