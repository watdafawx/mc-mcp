"""Pack-aware palette resolver: abstract material roles -> real blocks of the pack in front of us.

A style kit (architect/kits.json) maps every role (wall, trim, glass, glow, ...) to an ordered fallback chain
[preferred mod block, ..., vanilla block]. resolve_kit() picks, per role, the first block of the chain that the pack
has (available_blocks, e.g. the `registry_blocks` tool output). Without a registry it takes the preferred block (what
massing.KITS used before); when nothing in the chain exists it takes the last entry, which kits.json keeps vanilla.

Blockstate suffixes are preserved: "minecraft:oak_leaves[persistent=true]" is checked as "minecraft:oak_leaves" and
returned with its state. Pure Python, no Minecraft connection.

    >>> resolve_kit("solarpunk", available_blocks="vanilla")["wall"]
    'minecraft:calcite'
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KITS_PATH = HERE / "kits.json"
VANILLA_PATH = HERE / "knowledge" / "vanilla_blocks_1.21.1.json"
AIR = frozenset({"minecraft:air", "minecraft:cave_air", "minecraft:void_air"})


class PaletteError(ValueError):
    pass


# ------------------------------------------------------------------------------------------ block ids

def split_state(block: str) -> tuple[str, str]:
    """'ns:id[a=b]' -> ('ns:id', 'a=b'); a bare id gets the minecraft: namespace."""
    if not isinstance(block, str) or not block.strip():
        raise PaletteError(f"block must be a non-empty string, got {block!r}")
    s = block.strip()
    base, sep, rest = s.partition("[")
    if sep and not rest.endswith("]"):
        raise PaletteError(f"bad blockstate {block!r}: missing ']'")
    base = base.strip().lower()
    if ":" not in base:
        base = "minecraft:" + base
    return base, rest[:-1].strip() if sep else ""


def base_id(block: str) -> str:
    """Registry id of a block or blockstate string ('stone' -> 'minecraft:stone', 'x:y[a=b]' -> 'x:y')."""
    return split_state(block)[0]


def with_state(block: str, state: str | dict | None) -> str:
    """Merge extra state properties into a block string; existing properties are overridden by `state`."""
    base, own = split_state(block)
    props: dict[str, str] = {}
    for part in filter(None, (p.strip() for p in own.split(","))):
        k, _, v = part.partition("=")
        props[k.strip()] = v.strip()
    if isinstance(state, dict):
        props.update({str(k): str(v) for k, v in state.items()})
    elif state:
        for part in filter(None, (p.strip() for p in state.split(","))):
            k, _, v = part.partition("=")
            props[k.strip()] = v.strip()
    return base + ("[" + ",".join(f"{k}={v}" for k, v in props.items()) + "]" if props else "")


class Registry(frozenset):
    """A normalized set of block ids (what normalize_available returns; passed through unchanged)."""


_VANILLA: Registry | None = None


def vanilla_blocks() -> Registry:
    """Every block id of vanilla 1.21.1 (from knowledge/vanilla_blocks_1.21.1.json)."""
    global _VANILLA
    if _VANILLA is None:
        _VANILLA = Registry(set(json.loads(VANILLA_PATH.read_text(encoding="utf-8"))["blocks"]) | AIR)
    return _VANILLA


def normalize_available(available) -> Registry | None:
    """Accepts None (no registry: take preferred blocks), "vanilla", a `registry_blocks` result ({"blocks": [...]}),
    a path to a JSON file holding either, or any iterable of ids / blockstates / {"id": ...} dicts."""
    if available is None or isinstance(available, Registry):
        return available
    if isinstance(available, str):
        if available == "vanilla":
            return vanilla_blocks()
        available = Path(available)
    if isinstance(available, Path):
        available = json.loads(available.read_text(encoding="utf-8"))
    if isinstance(available, dict):
        if "blocks" not in available:
            raise PaletteError("available_blocks dict needs a 'blocks' list (the registry_blocks tool result)")
        available = available["blocks"]
    return Registry(base_id(b["id"] if isinstance(b, dict) else b) for b in available)


# ------------------------------------------------------------------------------------------ kits.json

_CACHE: dict[str, dict] = {}


def load_kits(path: str | Path | None = None) -> dict:
    """The parsed kits.json (cached per path). Treat it as read-only; kit_info() returns copies."""
    p = str(Path(path or KITS_PATH).resolve())
    if p not in _CACHE:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        errs = validate(data)
        if errs:
            raise PaletteError(f"{p}: " + "; ".join(errs))
        _CACHE[p] = data
    return _CACHE[p]


def as_chain(value, what: str = "role") -> list[str]:
    """A role value as a fallback chain: "id" -> ["id"], ["a", "b"] stays."""
    chain = [value] if isinstance(value, str) else list(value) if isinstance(value, (list, tuple)) else None
    if not chain or not all(isinstance(b, str) and b.strip() for b in chain):
        raise PaletteError(f"{what}: expected a block id or a non-empty list of block ids, got {value!r}")
    for b in chain:
        split_state(b)  # syntax check
    return chain


def validate(data: dict) -> list[str]:
    """Structural errors in a kits.json document ([] = fine): required roles, non-empty chains, vanilla last entry."""
    errs = []
    kits = data.get("kits") if isinstance(data, dict) else None
    if not isinstance(kits, dict) or not kits:
        return ["no 'kits' object"]
    required = data.get("required", [])

    def chk(name, where, chain):
        try:
            as_chain(chain, f"{name}.{where}")
        except PaletteError as e:
            errs.append(str(e))
            return
        if not base_id(chain[-1]).startswith("minecraft:"):
            errs.append(f"{name}.{where}: last fallback {chain[-1]} is not vanilla")

    for name, kit in kits.items():
        roles = kit.get("roles") if isinstance(kit, dict) else None
        if not isinstance(roles, dict):
            errs.append(f"{name}: no roles")
            continue
        for r in required:
            if r not in roles:
                errs.append(f"{name}: missing required role {r}")
        for r, chain in roles.items():
            chk(name, r, chain)
        meta = kit.get("meta") or {}
        for i, chain in enumerate(meta.get("roof_mats") or []):
            chk(name, f"meta.roof_mats[{i}]", chain)
        for r, chain in (meta.get("wing_roles") or {}).items():
            chk(name, f"meta.wing_roles.{r}", chain)
    return errs


def list_kits(path: str | Path | None = None) -> list[str]:
    return sorted(load_kits(path)["kits"])


def _kit(name: str, path=None) -> dict:
    kits = load_kits(path)["kits"]
    if name not in kits:
        raise PaletteError(f"unknown kit {name!r}; one of {sorted(kits)}")
    return kits[name]


def kit_info(kit_name: str, path: str | Path | None = None) -> dict:
    """{name, description, roles: {role: chain}, meta: {...}} -- a deep copy, safe to change."""
    k = _kit(kit_name, path)
    return {"name": kit_name, "description": k.get("description", ""), "roles": copy.deepcopy(k["roles"]),
            "meta": copy.deepcopy(k.get("meta") or {})}


# ------------------------------------------------------------------------------------------ resolution

def pick(chain, available=None) -> tuple[str, int, bool]:
    """(block, index in chain, found in registry). available None -> chain[0]; nothing found -> the last entry.
    The block comes back normalized (namespace added, state kept)."""
    chain = as_chain(chain, "chain")
    avail = normalize_available(available)
    if avail is None:
        return with_state(chain[0], None), 0, True
    for i, b in enumerate(chain):
        if base_id(b) in avail:
            return with_state(b, None), i, True
    return with_state(chain[-1], None), len(chain) - 1, False


def resolve_report(kit_name: str, available_blocks=None, overrides: dict | None = None,
                   path: str | Path | None = None) -> dict[str, dict]:
    """Per role: {block, index, found, source: kit|override, chain}. An override (a block or a chain) goes in front
    of the kit's chain for that role, so an override the pack lacks falls back to the kit choice instead of failing.
    An override for a role the kit lacks adds that role. None as an override value is ignored."""
    roles = _kit(kit_name, path)["roles"]
    avail = normalize_available(available_blocks)
    out = {}
    over = {r: as_chain(v, f"override {r}") for r, v in (overrides or {}).items() if v is not None}
    for role in list(roles) + [r for r in over if r not in roles]:
        own = over.get(role, [])
        chain = own + list(roles.get(role, []))
        block, i, found = pick(chain, avail)
        out[role] = {"block": block, "index": i, "found": found, "source": "override" if i < len(own) else "kit",
                     "chain": chain}
    return out


def resolve_kit(kit_name: str, available_blocks=None, overrides: dict | None = None,
                path: str | Path | None = None) -> dict[str, str]:
    """{role: block} for a kit in this pack (see resolve_report for the rules)."""
    return {r: v["block"] for r, v in resolve_report(kit_name, available_blocks, overrides, path).items()}


def resolve_list(chains, available_blocks=None) -> list[str]:
    """Resolve a list of chains (e.g. meta.roof_mats) the same way."""
    avail = normalize_available(available_blocks)
    return [pick(c, avail)[0] for c in chains]


def resolve_meta(kit_name: str, available_blocks=None, path: str | Path | None = None) -> dict:
    """kit meta with its block tables resolved: roof_mats -> [block], wing_roles -> {role: block}."""
    meta = kit_info(kit_name, path)["meta"]
    avail = normalize_available(available_blocks)
    if "roof_mats" in meta:
        meta["roof_mats"] = resolve_list(meta["roof_mats"], avail)
    if "wing_roles" in meta:
        meta["wing_roles"] = {r: pick(c, avail)[0] for r, c in meta["wing_roles"].items()}
    if "glass_cycle" in meta:
        meta["glass_cycle"] = resolve_list(meta["glass_cycle"], avail)
    return meta


def fallbacks(report: dict[str, dict]) -> list[dict]:
    """Roles of a resolve_report that did not get their first choice: [{role, wanted, picked, found}]."""
    return [{"role": r, "wanted": v["chain"][0], "picked": v["block"], "found": v["found"]}
            for r, v in report.items() if v["index"] > 0 or not v["found"]]


if __name__ == "__main__":
    import sys
    avail = sys.argv[2] if len(sys.argv) > 2 else None
    for name in ([sys.argv[1]] if len(sys.argv) > 1 else list_kits()):
        print(name, json.dumps(resolve_kit(name, avail), indent=1))
