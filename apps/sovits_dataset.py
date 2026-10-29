"""Small cross-Profile voice dataset example, based on legacy GOM/IPOM sovits_dataset.py.

This version intentionally does NOT decode ACB/AWB or infer captions from Uguiss.
It collects supported AudioClip audio and optionally incorporates user-supplied
captions, preserving the app-level composition pattern outside the P-C-A library.

Usage: python apps/sovits_dataset.py ipr ktn --limit 15 --output voices.zip
       python apps/sovits_dataset.py gakumas hski --captions caption_map.json
"""

import json
from argparse import ArgumentParser
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from eidolia import open_profile
from eidolia.codecs import extract_audio_clips


def build_dataset(
    profile_name: str,
    character: str,
    output: str | Path,
    *,
    limit: int | None = None,
    captions: dict[str, str] | None = None,
    language: str = "ja",
) -> tuple[int, int]:
    """Create a ZIP with audio files and an optional GPT-SoVITS .list index.

    Returns number of successful clips and unsupported/failing source assets.
    """
    profile = open_profile(profile_name)
    catalog = profile.get_catalog()
    captions = captions or {}
    candidates = [a for a in catalog.search(r"sud_vo.*") if character.lower() in a.name.lower()]
    if limit is not None:
        candidates = candidates[:limit]
    collected: dict[str, bytes] = {}
    skipped = 0
    for i, asset in enumerate(candidates, 1):
        print(f"[{i}/{len(candidates)}] {asset.name}")
        try:
            samples = extract_audio_clips(asset, asset.get_raw(), fmt="wav")
        except (NotImplementedError, ValueError, ImportError, OSError) as exc:
            print(f"  skipped: {exc}")
            skipped += 1
            continue
        for sample_name, pcm in samples.items():
            # Keep only matching voice samples, not unrelated clips in a bank.
            if character.lower() not in sample_name.lower() and character.lower() not in asset.name.lower():
                continue
            key = f"{asset.id}_{sample_name}".replace("/", "_").replace("\\", "_")
            collected[f"audio/{key}.wav"] = pcm
    if not collected:
        raise RuntimeError(
            "No decodable samples. The requested voices may be ACB/AWB (explicitly unsupported), "
            "or require a UnityPy codec not available in this environment."
        )
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(output)
    with ZipFile(output, "w", ZIP_DEFLATED) as out:
        records = []
        for name, pcm in sorted(collected.items()):
            out.writestr(name, pcm)
            stem = Path(name).stem
            caption = captions.get(stem, captions.get(stem.split("_", 1)[-1], ""))
            if caption:
                records.append(f"{name}|{character}|{language}|{caption}\n")
        if records:
            out.writestr("metadata.list", "".join(records))
    return len(collected), skipped


def main():
    parser = ArgumentParser(description="Eidolia SoVITS dataset downloader (supported codecs only)")
    parser.add_argument("profile", choices=["gakumas", "ipr", "idoly_pride"])
    parser.add_argument("character", help="Character slug in catalog/voice names (e.g. hski, ktn)")
    parser.add_argument("-o", "--output", default="dataset.zip")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of source assets")
    parser.add_argument("--captions", type=Path, help="Optional JSON mapping sample names to captions")
    parser.add_argument("--language", default="ja")
    args = parser.parse_args()
    captions = json.loads(args.captions.read_text(encoding="utf-8")) if args.captions else {}
    ok, skipped = build_dataset(
        args.profile, args.character, args.output, limit=args.limit, captions=captions, language=args.language
    )
    print(f"Saved {ok} clips to {args.output} ({skipped} unsupported source assets)")


if __name__ == "__main__":
    main()
