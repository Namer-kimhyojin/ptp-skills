# Performance workflow

## Goal

Load only the references required for the requested channel, format, mode, and character. Reuse approved character poses and unchanged layers before invoking image generation again.

For comics, the user's scene-progression preference overrides scene/pose cache reuse: reuse identity anchors as references, but redraw acting, staging and camera for each beat. Never duplicate a finished scene and replace only dialogue. Follow [panel variation](creative-variation.md#웹툰의-컷별-장면-변화); cache hits do not prove that a scene is appropriate.

## 1. Resolve the minimum context

Run `scripts/resolve_context.py` before production. Read the returned `references` and `assets`, plus their linked references needed for the current stage. The full asset manifest is reserved for standard/publication validation. For homepage notice collection and two-channel publishing, add `--workflow notice-to-social`; ordinary creative routing remains unchanged.

```powershell
python scripts/resolve_context.py --production-mode standard --content-type social-post --character both --render-style 3d --pose open-hand-guide --platform instagram --format png
```

## 2. Reuse character poses

Resolve the saved character set first with `--character-set`. The Theo/Pio library below applies only to its own members. Other sets use their registered identity/style files. With `none`, omit all character and pose assets. Include the job's `character_set` snapshot in cache dependencies (for example, `layer_cache.py --job <job.json>`).

- `assets/characters/3d/poses/pose-library.json` is the approved AI-reference library.
- Reuse the requested pose reference when it fits the scene.
- In comics, use pose references for anatomy/identity guidance without repeating the same finished figure and scene across different beats. Prefer newly staged acting over recycling poses.
- Generate a new character pose only when none of the eight roles communicates the required action.
- These PNGs have a baked checkerboard and are references, not transparent composition layers.
- The approved 2D anchors remain the identity authority; the 3D sheets and pose library define volume, material, lighting, and pose only.

## 3. Validate by production mode

- Quick draft: `validate_job.py --level fast`; skip expensive delivery and full asset checks.
- Standard: `validate_job.py --level standard` plus cached `validate_assets.py --level standard --cache-dir .ptp-cache`.
- Publication delivery: `validate_publication.py --job <job.json>` checks the locked job, library integrity, declared used assets, and job-specific review evidence. Do not fabricate brand or rights clearance. `validate_assets.py --level publication` is a separate whole-library approval audit; do not promote unused CI or global pending policy fields just to pass one delivery.

## 4. Reuse unchanged layers

Use `scripts/layer_cache.py` for source, copy, concept, character, background, lettering, and assembly layers. Record every input dependency and semantic value that can change the output. A cache hit is valid only when all dependency hashes and output hashes match.

```powershell
python scripts/layer_cache.py check --layer character --dependency anchor=assets/characters/teo/teo-master-sheet-v1.2.png --value pose=open-hand-guide --output work/character.png
python scripts/layer_cache.py record --layer character --dependency anchor=assets/characters/teo/teo-master-sheet-v1.2.png --value pose=open-hand-guide --output work/character.png
```

## 5. Benchmark

Run `python scripts/benchmark_workflows.py` after changing routing, validation, caching, or the pose library. The benchmark reports reference-context reduction and validator/cache timings without making paid image-generation calls.
