"""Element library index — fast, filterable search over the .elmt collection.

One pass parses every .elmt into a JSON cache (path, localized names,
terminals, pole pitch, size). Queries then run in milliseconds and can
filter out non-connectable decorative symbols — the two pain points of
scanning XML per query.
"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

INDEX_VERSION = 1


# --------------------------------------------------------------------------- #
# build / cache
# --------------------------------------------------------------------------- #

def _dir_signature(elements_dir: Path) -> "list[int]":
    """Cheap staleness probe: file count + newest mtime."""
    count, newest = 0, 0
    for root, _dirs, files in os.walk(elements_dir):
        for f in files:
            if f.endswith(".elmt"):
                count += 1
                mtime = int(os.stat(os.path.join(root, f)).st_mtime)
                newest = max(newest, mtime)
    return [count, newest]


def _record(elements_dir: Path, path: Path) -> "dict | None":
    try:
        dom = ET.fromstring(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    terminals = [{
        "name": t.get("name", ""),
        "x": float(t.get("x", "0")),
        "y": float(t.get("y", "0")),
        "orientation": t.get("orientation", ""),
    } for t in dom.iter("terminal") if t.get("uuid")]

    xs = sorted({t["x"] for t in terminals})
    pitch = min((b - a for a, b in zip(xs, xs[1:])), default=0)

    return {
        "path": path.relative_to(elements_dir).as_posix(),
        "names": {n.get("lang", "?"): (n.text or "")
                  for n in dom.iter("name")},
        "terminals": terminals,
        "pitch": pitch,
        "width": int(dom.get("width", "0")),
        "height": int(dom.get("height", "0")),
    }


def build_index(elements_dir: Path) -> dict:
    records = []
    for path in sorted(elements_dir.rglob("*.elmt")):
        rec = _record(elements_dir, path)
        if rec is not None:
            records.append(rec)
    return {
        "version": INDEX_VERSION,
        "signature": _dir_signature(elements_dir),
        "records": records,
    }


def load_index(elements_dir: Path, cache_path: Path) -> dict:
    """Load the cached index, rebuilding if missing or stale."""
    if cache_path.exists():
        try:
            index = json.loads(cache_path.read_text(encoding="utf-8"))
            if (index.get("version") == INDEX_VERSION
                    and index.get("signature") == _dir_signature(elements_dir)):
                return index
        except Exception:
            pass
    index = build_index(elements_dir)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(index, ensure_ascii=False),
                          encoding="utf-8")
    return index


# --------------------------------------------------------------------------- #
# search
# --------------------------------------------------------------------------- #

def _token_groups(token: str,
                  synonyms: "dict[str, list[str]]") -> "list[set[str]]":
    """Expand one query token into requirement groups.

    Exact synonym hit -> one group with all variants. Otherwise the token
    is decomposed by vocabulary substrings — CJK queries carry no spaces
    ("三相馬達" must become the 三相-group AND the 馬達-group).
    """
    for key, values in synonyms.items():
        variants = {key.lower(), *(v.lower() for v in values)}
        if token in variants:
            return [variants | {token}]
    groups = []
    for key, values in synonyms.items():
        variants = {key.lower(), *(v.lower() for v in values)}
        if any(len(v) >= 2 and v in token for v in variants):
            groups.append(variants)
    return groups or [{token}]


def search(index: dict, query: str, synonyms: "dict[str, list[str]]",
           limit: int = 12, min_terminals: int = 0) -> "list[dict]":
    """All query tokens must match (path or any localized name),
    each token being satisfiable by any of its synonym expansions."""
    tokens = [t for t in query.lower().split() if t]
    if not tokens:
        return []
    expanded = [g for t in tokens for g in _token_groups(t, synonyms)]

    scored = []
    for rec in index["records"]:
        if len(rec["terminals"]) < min_terminals:
            continue
        path_l = rec["path"].lower()
        filename = path_l.rsplit("/", 1)[-1]
        names_l = [n.lower() for n in rec["names"].values()]
        score = 0
        for variants in expanded:
            best = 0
            for v in variants:
                if v in filename:
                    best = max(best, 3)
                elif v in path_l:
                    best = max(best, 2)
                elif any(v in n for n in names_l):
                    best = max(best, 1)
            if best == 0:
                score = 0
                break
            score += best
        if score:
            scored.append((score, rec))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["path"]))
    return [rec for _score, rec in scored[:limit]]


def categories(index: dict, prefix: str = "") -> dict:
    """Immediate sub-categories under prefix, with element counts."""
    prefix = prefix.strip("/")
    depth = len(prefix.split("/")) if prefix else 0
    subs: "dict[str, int]" = {}
    direct = 0
    for rec in index["records"]:
        parts = rec["path"].split("/")
        if prefix and "/".join(parts[:depth]) != prefix:
            continue
        rest = parts[depth:]
        if len(rest) == 1:
            direct += 1
        else:
            subs[rest[0]] = subs.get(rest[0], 0) + 1
    return {"prefix": prefix, "elements_here": direct,
            "subcategories": [{"name": k, "elements": v}
                              for k, v in sorted(subs.items())]}
