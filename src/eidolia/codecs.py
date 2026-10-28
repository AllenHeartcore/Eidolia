"""Optional generic conversion functions. No ACB/AWB or vgmstream dependency."""

import subprocess
from io import BytesIO
from pathlib import Path


def convert(asset, data: bytes, fmt: str) -> bytes:
    """Convert simple images/Unity content and supported audio/video only.

    CRI ACB/AWB is deliberately excluded even if an external ffmpeg could handle it.
    """
    fmt = fmt.lower().lstrip(".")
    name = asset.name.lower()
    if fmt in ("raw", "unity3d"):
        return data
    if name.endswith((".acb", ".awb")) or data[:4] in (b"AFS2", b"@UTF"):
        raise NotImplementedError("CRI ACB/AWB decoding intentionally excluded from Eidolia 0.1; raw downloads work")
    if asset.kind == "assetbundle":
        try:
            import UnityPy
        except ImportError as exc:
            raise ImportError("For Unity media conversions install eidolia[media]") from exc
        env = UnityPy.load(data)
        objects = list(dict.fromkeys(list(env.container.values()) + list(env.objects)))
        if fmt in ("png", "jpeg", "jpg", "webp"):
            images = [o.read() for o in objects if o.type.name in ("Texture2D", "Sprite")]
            if not images:
                raise ValueError(f"No image found in {asset.name}")
            img = max(images, key=lambda obj: getattr(obj, "m_CompleteImageSize", 0)).image
            buf = BytesIO()
            if fmt in ("jpeg", "jpg"):
                img = img.convert("RGB")
            img.save(buf, format="JPEG" if fmt == "jpg" else fmt.upper())
            return buf.getvalue()
        if fmt in ("wav", "mp3", "ogg", "flac"):
            clips = [o.read() for o in objects if o.type.name == "AudioClip"]
            samples = {key: value for clip in clips for key, value in clip.samples.items()}
            if len(samples) != 1:
                raise ValueError(f"Expected 1 AudioClip sample in {asset.name}; got {len(samples)}")
            return _audio(next(iter(samples.values())), fmt)
        if fmt in ("txt", "json"):
            txt = [o.read() for o in objects if o.type.name == "TextAsset"]
            if len(txt) != 1:
                raise ValueError(f"Expected one TextAsset in {asset.name}; got {len(txt)}")
            script = txt[0].m_Script
            return script if isinstance(script, bytes) else script.encode("utf-8")
        if fmt == "mp4":
            video = [o.read() for o in objects if o.type.name == "VideoClip"]
            if len(video) != 1:
                raise ValueError(f"Expected one VideoClip in {asset.name}; got {len(video)}")
            return bytes(video[0].m_VideoData)
        raise NotImplementedError(f"No Unity converter to {fmt!r}")
    if fmt in ("png", "jpeg", "jpg", "webp") and name.startswith("img_"):
        try:
            from PIL import Image
        except ImportError as exc:
            raise ImportError("Install eidolia[media] for image conversion") from exc
        buf = BytesIO()
        im = Image.open(BytesIO(data))
        if fmt in ("jpeg", "jpg"):
            im = im.convert("RGB")
        im.save(buf, format="JPEG" if fmt == "jpg" else fmt.upper())
        return buf.getvalue()
    if fmt in ("wav", "mp3", "flac", "ogg") and name.startswith("sud_"):
        return _audio(data, fmt)
    if fmt == "mp4" and name.startswith("mov_"):
        codec = subprocess.run(
            [
                "ffprobe",
                "-i",
                "pipe:0",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
            ],
            input=data,
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.strip()
        cmd = ["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "mp4"]
        cmd += ["-preset", "ultrafast"] if codec == b"mpeg1video" else ["-c:v", "copy"]
        cmd += ["-c:a", "aac", "-b:a", "1024k", "-movflags", "faststart+frag_keyframe", "pipe:1"]
        return subprocess.run(cmd, input=data, stdout=subprocess.PIPE, check=True).stdout
    raise NotImplementedError(f"No converter from {asset.name} to {fmt!r}; use download() for raw content")


def _audio(data: bytes, fmt: str) -> bytes:
    if fmt == "wav" and data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return data
    try:
        from pydub import AudioSegment
    except ImportError as exc:
        raise ImportError("Install eidolia[media] for audio conversion") from exc
    return AudioSegment.from_file(BytesIO(data)).export(format=fmt).read()


def extract_audio_clips(asset, data: bytes, *, fmt: str = "wav") -> dict[str, bytes]:
    """Extract one or more audio clips for dataset workflows.

    IDOLY PRIDE Unity AudioClips can contain several named samples; retain all.
    Ordinary resource audio yields one named sample. CRI containers are omitted.
    """
    if asset.name.lower().endswith((".acb", ".awb")) or data[:4] in (b"AFS2", b"@UTF"):
        raise NotImplementedError("CRI ACB/AWB not supported")
    if asset.kind != "assetbundle":
        return {Path(asset.name).stem: _audio(data, fmt)}
    try:
        import UnityPy
    except ImportError as exc:
        raise ImportError("Unity samples require the eidolia[media] extra") from exc
    env = UnityPy.load(data)
    objects = list(dict.fromkeys([*env.container.values(), *env.objects]))
    clips = {obj.read().name: obj.read() for obj in objects if obj.type.name == "AudioClip"}
    samples = {name: pcm for clip in clips.values() for name, pcm in clip.samples.items()}
    return {Path(name).stem: _audio(pcm, fmt) for name, pcm in samples.items()}
