# Eidolia 🌸

**Every Stage, Every World.**

Eidolia is a Python framework for discovering, acquiring, and exploring content
from idol game worlds. Its minimal first release covers two Octo-backed titles:
**Gakuen Idolmaster** and **IDOLY PRIDE**.

## Install

```bash
python -m pip install -e .
# Optional image, Unity texture / AudioClip, and media conversion:
python -m pip install -e '.[media]'
```

On Windows, use double quotes instead of single quotes in PowerShell if needed.
Some media conversions also require an external `ffmpeg` executable.

## Use

```python
from eidolia.profiles import GkmasProfile, IdolyPrideProfile

profile = GkmasProfile()             # or GkmasProfile(pc=True)
# profile = IdolyPrideProfile()
catalog = profile.get_catalog()      # online; later calls reuse the in-memory catalog
print(catalog.revision, len(catalog))

assets = catalog.search(r"img_general_cidol.*")
print(assets[:5])
if assets:
    assets[:1]              # plain Python list of Asset handles
    assets[0].download("objects")

# Offline Octo data and previously exported JSON are supported too:
# catalog = profile.load_catalog("octocacheevai")
# catalog.export_json("catalog.json")
```

`Catalog.search()` uses `re.match` regex-prefix matching as in GOM/IPOM.
`catalog['name']` retrieves exactly one item; `Asset.get_raw()` returns verified,
normalized bytes; `Asset.download()` writes those bytes to disk. A directory path
without an extension is interpreted as a download directory.

`Asset.export(format, path)` offers small optional conversions for images, Unity
Texture2D/Sprite, Unity AudioClip, TextAsset, and selected videos. It is intentionally
**not** a general game rendering engine.

### Example overarching application

```bash
python -m pip install -e '.[media]'
python apps/sovits_dataset.py ipr ktn --limit 20 -o voices.zip
# Optional: --captions caption_map.json (sample stem -> transcript)
```

The SoVITS example collects supported Unity AudioClip/standard audio into a ZIP,
optionally writing `metadata.list` when captions are supplied. It **does not** decode
CRI ACB/AWB, reconstruct missing game transcripts, or promise that every game's
voice content can be converted. The original apps' automatic caption extraction
and voice merging depended on the Adventure/CRI layers excluded from this release.

## Scope / known omissions

- No game-catalog version history, diff/patch, or Wayback Machine.
- No `stagecraft/`, `adventurer/`, Flask UI, frontend, or Unity worker.
- No ACB/AWB, HCA decoding, vgmstream executables, or packaged CRI binaries.
- No guarantee of access to game servers or current compatibility with changing APIs.
- GOM PC/mobile catalog paths are retained; IPOM's generation/version/asset-type
  URL placeholders are retained. Live network calls should be validated by users.
- Offline corpus/protobuf tests do not require server access.

## Migration notes (GOM vs. IPOM)

| Area                | GOM (Gakumas)                    | IPOM (IDOLY PRIDE)                             | Eidolia starter                                   |
| ------------------- | -------------------------------- | ---------------------------------------------- | ------------------------------------------------- |
| Live catalog        | App 400; per-response 16-byte IV | App 212; fixed IV and 16-byte decrypted prefix | Both retained                                     |
| Desktop             | Separate PC version 705100       | No separate PC option                          | `GkmasProfile(pc=True)`                           |
| ProtoDB             | Octo `Database` / `Data`         | Exactly the same schema                        | One shared parser                                 |
| Asset URL           | Primarily `{o}`                  | `{o}`, `{g}`, `{v}`, `{type}`                  | Template resolved per entry                       |
| Bundle encoding     | GOM header-mask routine          | Equivalent routine                             | Shared, validated after MD5 wire check            |
| Audio               | MP3, Unity AudioClip, CRI        | Unity AudioClip, sometimes multiple clips      | Ordinary/Unity audio only; no CRI                 |
| Other media         | images, USM                      | images, TextAsset, VideoClip                   | Small optional converters; no advanced inspection |
| Historical versions | era-aware Wayback                | revision-based Wayback                         | Intentionally omitted                             |
| Web app             | Flask                            | Flask port                                     | Omitted                                           |
| SoVITS app          | ADV captions and CRI voice data  | Similar port                                   | Limited codec-only dataset example                |

The initial constants are inherited from upstream main branches as inspected on
October 27, 2026. They are not a promise that the upstream servers will continue
to accept those protocol versions. Customize `api_version=` if a game's live API changes.

## Lineage and license

Derived from [AllenHeartcore/GkmasObjectManager](https://github.com/AllenHeartcore/GkmasObjectManager)
and [AllenHeartcore/IdolyPrideObjectManager](https://github.com/AllenHeartcore/IdolyPrideObjectManager).
The shared Octo ProtoDB descriptor, AES/deobfuscation framing, media conversion
algorithms, and source constants were adapted from those GPL-3.0 projects.
Underlying game-specific retrieval research was credited to DreamGallery,
kishidanatsumi, Vibbit, and MalitsPlus in the upstream repositories.

Eidolia is licensed under **GPL-3.0-only** to preserve derivative licensing.
All game assets remain the property of their respective rights holders.
