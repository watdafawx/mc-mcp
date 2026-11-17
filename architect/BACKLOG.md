# Architect backlog

## Queued: build from a reference image or video

Status: queued 2026-11-16. Not started.

Goal: paste an image (a photo, concept art, or a screenshot of someone's Minecraft build) or a video
(a file, or a YouTube build showcase), and get a ghost build modelled on it. The usual tools then
iterate on it and export it.

### Inputs
- CLI: `architect.py --ref <file|url> [--ref ...] "make this, but AE2-themed"`.
- In game: `@claude build this <url>` in chat (`--chat` mode).
- Paste in the REPL: a line that is only a path or URL to an image or video counts as a reference.
- Video: `ffmpeg` scene-change keyframes (`select='gt(scene,0.3)'`), capped at 8 frames and downscaled to
  ~1024px. YouTube links go through `yt-dlp` first.

### Pipeline
1. **Read the reference** (one vision call, Haiku). Images go in as image blocks. The call returns a
   structured brief: footprint and proportions in blocks, massing as a list of volumes, roof type, wall
   depth layers, a palette mapped to real block ids (checked with `registry_blocks`), signature features,
   and the closest theme in `knowledge/themes.json`.
2. **Scale.** Pick a block scale from a known size (a door is 2 high, a storey is about 4–5 blocks) or
   from the user's size hint.
3. **Build** with the normal loop, with the brief, the images and the knowledge base in context.
4. **Compare.** Take a `view` from the angle closest to the reference's camera, show the reference and the
   view side by side, and ask the model for a list of differences. Fix them (two rounds max).
5. **Export** as usual.

### Later, optional
- Exact geometry: image → 3D mesh (TRELLIS / Hunyuan3D class, on rig's 3080) → voxelize → map colours
  to the nearest block palette → ghost. Best for organic shapes (statues, ships, trees). The LLM still adds
  doors, lighting and detail on top.
- Minecraft screenshots: detect block textures directly (texture atlas matching) for near-exact copies.

### Notes
- Costs about $0.01–0.02 per reference on Haiku (images are ~1.5k tokens each at 1024px).
- Video keyframes add up: 8 frames is about 12k tokens. Keep the cap.

## Done 2026-11-16
- Reference mode (`refs.py`): images, URLs, YouTube/video keyframes, `/paste` clipboard. Castle photo test: $0.014.
- Shape generators (`shapes.py`, `shapes` tool): round_tower, cone_roof, gable_roof (crow-stepped option),
  pyramid_roof, dome, battlements, window_row, arch, pillar_row. Bad derived stairs/slab ids fall back to stone brick.
- Photo -> 3D (`img3d/`, `image_to_3d` tool): Hunyuan3D-2mini-Turbo on rig (~4 s warm), voxelize, colour by projection.
  Horse statue test: 3643 blocks, silhouette IoU 0.77, $0.008. (First run sent only `blocks`, not `boxes`: fixed.)

## Next ideas
- Proportion check: compare the reference's height/width ratios per part with the ghost's bounds before viewing.
- More shapes: square tower with machicolations, dormer, buttress row, spiral stair, bridge, wall segment with walkway.
- Crow-stepped gable and small domes look rough; smooth both.
