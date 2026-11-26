#!/usr/bin/env python3
"""Assemble PNG frames, an animated GIF or a video with timed sound and subtitles."""
import argparse
from contextlib import ExitStack
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile


def run(*args, cwd=None):
    return subprocess.run([str(arg) for arg in args], cwd=cwd, check=True)


def probe(path, frames=False):
    options = ["-count_frames"] if frames else []
    return json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", *options, "-show_streams", "-show_format", "-of", "json", str(path)
    ]))


def number(value, label, minimum=0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ValueError(f"{label} must be a finite number >= {minimum}")
    return value


def positive_int(value, label):
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def stamp(seconds):
    minutes, centiseconds = divmod(round(seconds * 100), 6000)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02}:{centiseconds // 100:02}.{centiseconds % 100:02}"


def subtitles(path, captions, width, height, font):
    if any(ch in font for ch in ",\r\n"):
        raise ValueError("Invalid subtitle font name")
    margin = round(width * .07)
    fontsize = round(height * .045)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{fontsize},&H00FFFFFF,&H000000FF,&H350B1E18,&H350B1E18,-1,0,0,0,100,100,0,0,3,5,0,2,{margin},{margin},{round(height*.065)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for cue in captions:
        text = (cue["text"].replace("\\", "＼").replace("{", "｛").replace("}", "｝")
                .replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\N"))
        events.append(f"Dialogue: 0,{stamp(cue['start'])},{stamp(cue['end'])},Caption,,0,0,0,,{text}")
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def read_captions(plan, duration):
    captions = sorted(plan.get("captions", []), key=lambda cue: cue["start"])
    previous_end = 0
    ids = {}
    for cue in captions:
        a = number(cue["start"], "caption.start")
        b = number(cue["end"], "caption.end")
        if a < previous_end or b > duration or stamp(a) == stamp(b) or b <= a or not cue["text"].strip():
            raise ValueError("Captions must be non-overlapping, nonempty and within the video")
        if "id" in cue:
            if cue["id"] in ids:
                raise ValueError(f"Duplicate caption ID: {cue['id']}")
            ids[cue["id"]] = cue
        previous_end = b
    return captions, ids


def visual_input(visual, base, fps, frame_count):
    path = (base / visual["path"]).resolve()
    kind = visual["type"]
    if kind == "frames":
        names = sorted(frame.name for frame in path.glob("*.png"))
        if names != [f"{i:06d}.png" for i in range(frame_count)]:
            raise ValueError(f"Expected {frame_count} PNG frames named 000000.png through {frame_count-1:06}.png")
        return ["-framerate", str(fps), "-start_number", "0", "-i", str(path / "%06d.png")]
    if kind == "gif":
        if path.suffix.lower() != ".gif" or not path.is_file():
            raise ValueError(f"GIF input is missing: {path}")
        mode = visual.get("mode", "hold")
        if mode not in ("hold", "loop"):
            raise ValueError("GIF mode must be hold or loop")
        loop = ["-stream_loop", "-1"] if mode == "loop" else []
        return [*loop, "-ignore_loop", "1", "-i", str(path)]
    if kind == "video":
        if path.suffix.lower() != ".mp4" or not path.is_file():
            raise ValueError(f"MP4 input is missing: {path}")
        return ["-i", str(path)]
    raise ValueError("visual.type must be frames, gif or video")


def audio_filters(cues, base, duration, caption_ids):
    inputs, filters = [], []
    voices, effects, narration_ranges = [], [], []
    for i, cue in enumerate(cues, 1):
        path = (base / cue["file"]).resolve()
        info = probe(path)
        stream = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
        if stream is None:
            raise ValueError(f"No audio stream: {path}")
        start = number(cue["start"], "audio.start")
        length = float(stream.get("duration", info["format"].get("duration", 0)))
        if not math.isfinite(length) or length <= 0 or start + length > duration + .002:
            raise ValueError(f"Audio is outside the video timeline: {path}")
        gain_db = number(cue.get("gain_db", 0), "audio.gain_db", minimum=-60)
        role = cue["role"]
        if role == "voice":
            caption_id = cue.get("caption_id")
            if caption_id is not None:
                caption = caption_ids.get(caption_id)
                if caption is None or start < caption["start"] or start + length > caption["end"] + .002:
                    raise ValueError(f"Narration falls outside its subtitle: {path}")
            narration_ranges.append((start, start + length))
            voices.append(f"[a{i}]")
        elif role == "effect":
            effects.append(f"[a{i}]")
        else:
            raise ValueError(f"Unsupported audio role: {role}")
        inputs += ["-i", str(path)]
        filters.append(
            f"[{i}:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"volume={gain_db}dB,adelay={round(start * 48000)}S:all=1,apad,atrim=duration={duration}[a{i}]"
        )
    ranges = sorted(narration_ranges)
    if any(previous[1] > current[0] + .002 for previous, current in zip(ranges, ranges[1:])):
        raise ValueError("Narration clips overlap")
    groups = []
    for tracks, label in ((voices, "vbus"), (effects, "ebus")):
        if tracks:
            mix = f"amix=inputs={len(tracks)}:normalize=0" if len(tracks) > 1 else "anull"
            filters.append(f"{''.join(tracks)}{mix}[{label}]")
            groups.append(f"[{label}]")
    if len(groups) == 2:
        filters.extend([
            "[vbus]asplit=2[voiceout][duckkey]",
            "[ebus][duckkey]sidechaincompress=threshold=0.025:ratio=6:attack=12:release=170[effectsout]",
            "[voiceout][effectsout]amix=inputs=2:normalize=0[bus]",
        ])
        groups = ["[bus]"]
    if groups:
        filters.append(f"{groups[0]}alimiter=limit=0.88:level=false:latency=true[audio]")
    return inputs, filters


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gif-preview", type=Path)
    parser.add_argument("--preview-seconds", type=float, default=3.6)
    args = parser.parse_args()
    plan_file = args.plan.resolve()
    plan = json.loads(plan_file.read_text(encoding="utf-8-sig"))
    duration = number(plan["duration"], "duration", minimum=.01)
    fps = positive_int(plan.get("fps", 30), "fps")
    frame_count = round(duration * fps)
    if frame_count < 1 or abs(frame_count - duration * fps) > .00001:
        raise ValueError("duration × fps must be an integral number of frames")
    width, height = (positive_int(v, "size") for v in plan.get("size", [1080, 1080]))
    if width % 2 or height % 2:
        raise ValueError("Output width and height must be even")
    output = args.output.resolve()
    preview = args.gif_preview.resolve() if args.gif_preview else None
    if output.suffix.lower() != ".mp4" or (preview and preview.suffix.lower() != ".gif"):
        raise ValueError("Output must be .mp4 and preview must be .gif")
    for target in (output, preview):
        if target:
            if target.exists():
                raise FileExistsError(f"Choose a new output name: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
    caption_cues, caption_ids = read_captions(plan, duration)
    visual_args = visual_input(plan["visual"], plan_file.parent, fps, frame_count)
    sound_args, sound_filters = audio_filters(plan.get("audio", []), plan_file.parent, duration, caption_ids)
    visual = (f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2:"
              f"out_color_matrix=bt709:out_range=limited,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
              f"setsar=1,fps={fps}")
    if plan["visual"]["type"] == "gif" and plan["visual"].get("mode", "hold") == "hold":
        visual += f",tpad=stop_mode=clone:stop_duration={duration}"

    with ExitStack() as stack:
        stage = Path(stack.enter_context(tempfile.TemporaryDirectory(dir=output.parent, prefix=".render-")))
        movie = stage / "movie.mp4"
        if caption_cues:
            font = plan.get("caption_font", "Malgun Gothic" if os.name == "nt" else "Noto Sans CJK KR")
            subtitles(stage / "captions.ass", caption_cues, width, height, font)
            visual += ",subtitles=filename=captions.ass"
        filters = ";".join([f"[0:v:0]{visual},format=yuv420p[video]", *sound_filters])
        sound_output = ["-map", "[audio]", "-c:a", "aac", "-b:a", "192k"] if sound_filters else []
        run("ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", *visual_args, *sound_args,
            "-filter_complex", filters, "-map", "[video]", *sound_output,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-colorspace", "bt709", "-color_trc", "bt709", "-color_primaries", "bt709",
            "-color_range", "tv", "-t", str(duration), "-movflags", "+faststart", movie, cwd=stage)
        info = probe(movie, frames=True)
        stream = next(s for s in info["streams"] if s["codec_type"] == "video")
        if ((stream["width"], stream["height"], stream["codec_name"], int(stream["nb_read_frames"]))
                != (width, height, "h264", frame_count)
                or bool(sound_filters) != any(s["codec_type"] == "audio" and s["codec_name"] == "aac"
                                             for s in info["streams"])
                or abs(float(info["format"]["duration"]) - duration) > .05):
            raise ValueError("Encoded output does not match the requested tracks, size or frame count")
        if preview:
            seconds = min(duration, number(args.preview_seconds, "preview seconds", minimum=.05))
            preview_stage = Path(stack.enter_context(tempfile.TemporaryDirectory(dir=preview.parent, prefix=".preview-")))
            gif = preview_stage / "preview.gif"
            filter_gif = ("fps=15,scale=480:-2:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];"
                          "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
            run("ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", movie, "-t", str(seconds),
                "-filter_complex", filter_gif, "-loop", "0", gif)
            probe(gif)
        os.link(movie, output)
        if preview:
            os.link(gif, preview)
    print(f"{output} | {width}x{height}, {fps} fps, {frame_count} frames")


if __name__ == "__main__":
    main()
