# Scene graph IR, semantic anchors and pack-aware palettes (Phase 1A)

Status: implemented as a standalone library (`architect/scene.py`, `architect/palettes.py`, `architect/kits.json`),
tested offline by `architect/test_scene.py`. Not yet wired into `architect.py` / `campus.py` / the Java side; that is
Phase 1B (see the end).

## Why

Today the model builds by calling generators and passing world coordinates (`origin`, `at`, `room_origins`). Three
problems follow:

1. **World arithmetic.** To put a dish on a wing's roof the model has to know the wing's origin, its footprint and
   its roof height (`sum(floor_hs) + 1`). It gets this wrong often, and the floating-part guard then drops the part.
2. **Iteration redraws everything.** `--iterate` regenerates the campus; a small change ("make the hub wider") moves
   nothing that depends on it, or moves everything by hand.
3. **Palettes are ATM10-only.** `massing.KITS` names chipped/luminax/connectedglass/create blocks directly, and the
   kits were patched in place (v7/v10 `.update()` calls, v15/v16 tables in `campus.py`). On another pack or pure
   vanilla, those blocks do not exist.

The fix is a declarative layer between the model and the generators: the model writes a small JSON scene graph that
names things and attaches them to each other by name; a deterministic compiler turns it into ghost specs.

## 1. The IR

A scene is plain JSON. Flat node list; hierarchy is expressed by `attach` (a node's parent is its attach target).

```json
{
  "version": 1, "id": "base1", "origin": [120, 64, -300], "kit": "steampunk",
  "roles": {"glass": "minecraft:cyan_stained_glass"},
  "ground_y": 0,
  "nodes": [
    {"id": "hub", "kind": "structure", "tag": "volume",
     "params": {"shape": "octagon", "w": 25, "d": 25, "floors": 2, "program": [["workshop", "storage"], "living"]}},
    {"id": "wing_create", "kind": "structure", "tag": "wing",
     "attach": {"target": "hub", "surface": "wall:east", "offset": [3, 0, 0]},
     "params": {"w": 17, "d": 13, "floor_hs": [8], "roof": "flat", "roof_details": 0, "antennas": 0}},
    {"id": "dish", "kind": "shape", "tag": "roof",
     "attach": {"target": "wing_create", "surface": "roof_deck", "align": "center"},
     "params": {"shape": "dome", "r": 3, "block": "$glass"}},
    {"id": "cpu", "kind": "multiblock", "tag": "multiblock",
     "attach": {"target": "hub", "surface": "pad[1]"}, "params": {"kind": "crafting_cpu", "sx": 3}},
    {"id": "crates", "kind": "boxes", "tag": "prop",
     "attach": {"target": "hub", "surface": "wall:north", "align": "min"},
     "params": {"boxes": [[0, 0, 0, 2, 1, 1, "$detail"]]}}
  ]
}
```

| Concept (design vocabulary) | How it is expressed |
|---|---|
| **Site** | the scene itself: `origin` (world position of scene-local 0,0,0), `kit`, `roles`, `ground_y` |
| **Volume / Wing** | `kind: structure` (massing facade engine). `tag` says what it is (`volume`, `wing`, ...) |
| **Room** | `params.program` on a structure (fit-out by `interiors.py`); each ground-floor room becomes an anchor `pad[i]` |
| **Roof** | `params.roof` on a structure, or a `shape` node tagged `roof` attached to `roof_deck` |
| **Part** | `kind: shape` (any `shapes.KINDS` part, or `parts: [...]`), `platform`, `bridge`, `slope`, `spire` |
| **Multiblock** | `kind: multiblock`, `params.kind` = a `multiblocks.KINDS` preset (rule-checked) |
| **Prop** | `kind: boxes`: a raw ghost spec (`palette`, `boxes`, `blocks`), the escape hatch |

Node fields: `id` (no `/` or spaces), `kind`, `params` (the generator's own arguments, checked against its
signature, so `widht` fails with a hint instead of being ignored), `at` *or* `attach`, `kit` / `roles` (node palette
override), `tag`, `anchors` (custom node-local anchors), `floating: true` (opt out of the floating check, e.g. an
airship). Unknown keys are errors with a "did you mean" hint.

`"$role"` anywhere in params is replaced with the resolved kit block (`"$glass"`, `"$trim[axis=y]"` keeps the
state). That makes classic shapes, props and multiblock surrounds follow the kit and the pack too.

## 2. Semantic anchors

Every compiled node exposes named anchors. An anchor is a box plus an outward normal:
`{"min": [x,y,z], "max": [x,y,z], "normal": [nx,ny,nz]}` (world coordinates in the output).

| Anchor | All nodes (from the bounding box) | `structure` (from the footprint maths massing uses) |
|---|---|---|
| `top` | top face, normal +y | same |
| `roof_deck` | = `top` | the deck inside the parapet at `y = sum(floor_hs) + 1` |
| `floor` | lowest layer, normal +y | ground-floor slab inside the walls (stand at y+1) |
| `floor[i]` | | slab of storey i |
| `interior` | whole box, no normal | inside of the walls, floor to deck |
| `wall:north\|south\|east\|west` | bbox faces | facade faces spanning the wall thickness (outer ring to inner wall) |
| `door:<side>` | | the 3x3 doorway massing cuts for each entrance (through the wall) |
| `pad[i]` | | ground-floor room i of `program[0]`, split exactly like `interiors.fit_floor`; `label` = room kind |
| `bottom` | bottom face, normal -y (hang below) | same |
| `ground` | footprint at the base level, no normal | same |
| `center` | centre point | same |

`platform` overrides `roof_deck`/`floor` with its top step. Custom anchors can be declared per node.

### Attachment

`attach: {target, surface, align?, align_y?, offset?, side?}` (shorthand: `"attach": "hub.roof_deck"`).

- **Normal axis**: the child sits against the surface on the outside: on top of `roof_deck`, in front of
  `wall:east`, hanging under `bottom`. `side: inside` puts it just inside instead (a sign on the inner face of
  `wall:north`).
- **Other axes**: `align` = `center` (default) | `min` | `max`. A string applies to x and z; a dict
  `{"x": "max", "z": "min", "y": "max"}` sets axes one by one. y defaults to `min` (stand on the base), or `align_y`.
- **Offset** `[dx, dy, dz]` is applied last.

The compiler generates every node at local 0,0,0 first (generation never depends on position), then places nodes in
attach order. Errors are specific: `attach cycle: hub -> dish -> wing -> hub`,
`node 'dish' attaches to unknown node 'wingg' (did you mean 'wing'?)`,
`'wing' has no anchor 'roof_dek' (did you mean 'roof_deck'?); anchors: top roof_deck floor ... pad[0-2]`.

Positions are computed from the generator output before any pack filtering, so the same scene lands in the same
place on ATM10 and on vanilla.

## 3. Compile output and checks

`Scene.compile(available_blocks=None, on_missing="report") -> CompileResult`:

- `ghosts`: one spec per node, scene order:
  `{id, ghost_id: "<scene>/<node>", kind, tag, kit, origin, palette, boxes, blocks, count, bounds{min,max,size},
  anchors, attach, info, fallbacks}`. `ghost_set_args(compact=True)` turns them into `ghost_set` calls (block states
  folded into short palette keys). The `scene/` prefix lets `ghost_clear <scene>/` remove a whole scene.
- `floating`: nodes with no 6-face contact (directly or through other nodes) to a node that touches `ground_y`.
  Attachment guarantees contact for solid children; a pinned child whose parent was removed shows up here.
- `overlaps`: `[{a, b, cells}]` node pairs sharing cells (a dish on a roof with vents, furniture under a CPU). Put
  the example's dish on `roof_deck` of a `sawtooth` wing and this reports `dish~wing_create 41`: attach to `top`
  or use a flat roof.
- `missing_blocks`: with a registry, every block a generator emits that the pack lacks (mod blocks from
  `interiors`/`services`, derived slabs such as `minecraft:cyan_stained_glass_slab`). `on_missing`: `report`,
  `drop` (remove those entries, geometry kept), `error`.
- `describe(verbose=False)`: what the model sees. One line per node with placement, size, bounds and the anchor
  *names* (`wall:north|south|west|east floor[0-1] pad[0-2]`), then the checks. No block lists. `verbose=True` adds
  each anchor box.

## 4. Patch operations (`--iterate`)

`Scene.apply_patch(ops)` is atomic (all ops or none) and returns `{changed, removed, dirty}`; `dirty` adds every
node attached to a changed node, since it may move.

| Op | Effect |
|---|---|
| `{"op": "set_node", "node": {...}}` | add or replace (keeps list position) |
| `{"op": "add_node", "node": {...}}` | add; error if the id exists |
| `{"op": "patch_node", "id": "hub", "patch": {"params": {"w": 31}}}` | RFC 7386 merge patch on the node dict; `null` deletes; setting `at` detaches, setting `attach` drops `at` |
| `{"op": "remove_node", "id": "wing", "orphans": "error\|remove\|pin"}` | dependents: refuse (default), cascade, or pin them where they are (`at` = current origin) |
| `{"op": "set_palette", "kit": "gothic", "roles": {"glass": "...", "trim": null}, "id"?: "wing"}` | scene or node palette; roles merge (`replace_roles: true` replaces) |
| `{"op": "set_scene", "origin": [x, y, z], "ground_y": 0}` | move the whole site |

Redraw set: `new_result.diff(old_result)` -> `{set, clear, keep}` by content hash of each ghost spec. That is the
authority (dirty tracking is a hint): resize the hub and only the hub and what hangs on it are re-sent; swap the kit
and the multiblock (fixed blocks) stays.

## 5. Pack-aware palettes

`architect/kits.json` holds all eight kits (`station_white`, `cyber_dark`, `ae_sky`, `hextech`, `steampunk`, `gothic`,
`solarpunk`, `rust_industrial`), with the v7 and v10 overrides folded in. There are no `.update()` patches any more:
element 0 of each chain is exactly the block `massing.KITS` holds after its patches (a test checks this). Each role
is an ordered chain, last entry vanilla:

```json
"glass": ["connectedglass:borderless_glass_light_blue", "minecraft:light_blue_stained_glass"],
"detail": ["minecraft:oak_leaves[persistent=true]"]
```

`meta` carries the per-kit layout tables that were spread over massing, interiors and campus: `roof_default`,
`wood`, `colour`, `alt_roof`, `tower_roof`, `hub_roof`, `roof_cycle` (v15), `roof_mats` (v16, chains too),
`glass_cycle`, gothic `wing_roles`, `hall_style`, `no_gold`.

Resolution (`palettes.resolve_kit(kit, available_blocks=None, overrides=None)`), per role:

1. Chain = override (a block or a chain) + the kit chain. An override the pack lacks falls back to the kit's choice
   instead of failing.
2. No registry (`None`): take element 0 (today's behaviour).
3. Registry given: take the first element whose id (state stripped) is in it. The returned block keeps its state.
4. Nothing matches: take the last element (vanilla).

`available_blocks` accepts the `registry_blocks` tool result (`{"blocks": [...]}`), a list of ids/states/`{"id"}`
dicts, a JSON file path, or `"vanilla"` (the 1.21.1 id list in `architect/knowledge/vanilla_blocks_1.21.1.json`,
taken from the client jar's blockstate files). `resolve_report` also says per role which index was used and
whether it was found; `resolve_meta` resolves the meta block tables. Every vanilla id in kits.json is checked
against the 1.21.1 list, and every mod id was checked against the ATM10 block library during authoring.

## Trade-offs

- **Flat node list + attach, not nested children.** Diffs and patches address nodes by id without walking a tree;
  re-parenting is one `patch_node`. The cost is that "children" are implicit (`Scene.dependents`).
- **Anchors from bounding boxes, plus structure-specific ones.** Footprint-exact anchors for octagon/round/L shapes
  would need polygons; bbox faces are what the model can reason about. `roof_deck` of a structure with a shaped
  roof (mansard, dome) is still the deck under it: attach to `top` to stand on the roof instead.
- **Positions ignore the pack.** Bounds come from the unfiltered generator output, so dropping missing blocks never
  moves anything. A node whose blocks are all dropped keeps its anchors.
- **massing keeps its per-kit special cases** (`kit == "gothic"` lancets, station solar panels). Known kits are
  passed by name with the resolved roles as overrides, so that behaviour stays; a kit massing does not know goes in
  as a role dict and gets `meta.roof_default`.
- **Data duplication for now.** The campus tables (`ROOF_CYCLE`, `ROOF_MATS`, ...) are copied into `kits.json`
  meta; the test compares them while campus still defines them. Phase 1B should make campus read them from here.
- **Generic `floor` on non-structure nodes is the lowest layer.** Right for bridges and decks, meaningless for a solid
  prop. The model gets the anchor list in `describe()` and can use `top`.

## Phase 2A: wired into the architect (`scene_set` / `scene_patch`)

- `massing.KITS` / `massing.ROOF_DEFAULT` are now built from `kits.json` (element 0 of each chain); the hardcoded tables and
  `.update()` patches are gone. Values are identical, so `campus.py` and every test see the same dicts.
- `architect.py` has two local tools. `scene_set {scene}` compiles a whole scene; `scene_patch {ops}` applies atomic patch
  ops to the saved scene. Both diff against the last compile and send only `ghost_set` for `diff.set` and `ghost_clear`
  for `diff.clear`; the reply is `describe()` plus a `redraw: {set, keep, clear, warnings}` line.
- The active scene is saved as `sessions/<name>/scene.json`; a new `Architect` on the same session (`--iterate`) reloads it,
  compiles it as the baseline and re-sends scene ghosts the game no longer has (checked with `ghost_list`).
- The live registry is fetched once per session (`registry_blocks`; per kit/mod namespace when the unfiltered list is
  truncated) and passed to `compile(available_blocks=...)`; no registry = preferred blocks.
- Tests: `architect/test_agent_scene.py` (mock Mcp, records every call).

## Phase 1B (not in this change)

- Model tools in `architect.py`: `scene_apply(ops)` -> `compile` -> `diff` -> `ghost_set` only for `set`,
  `ghost_clear` for `clear`; `describe()` goes back to the model instead of block counts.
- `campus.py` emits a Scene (hub, wings, gallery, tower as nodes) instead of raw ghosts, and reads kits via
  `palettes` with the live `registry_blocks` list, so the model can patch a procedural campus.
- Anchors for upper-floor rooms (`pad[f.i]`), bridge ends, and footprint-exact walls for non-rect shapes.
- Substitution for non-kit mod blocks emitted by `interiors`/`services` (today: reported or dropped).
