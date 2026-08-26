#!/usr/bin/env python3
"""Generate the flat tag vocabulary for /api/media/ingest FROM the schema.

The ingest API takes `tags: string[]` -- a flat keyword bag -- while the tag schema is
typed with closed enums. This module is the single place that maps between them, so the
vocabulary cannot drift from the schema. Run it to emit the full list to pre-register in
the media library.

Convention: `namespace:value`, lowercase, hyphen-separated. Per-trailer tags carry a
1-based unit prefix: `t1:axle:tri`, `t2:axle:not-visible`.

RULE: `unknown` and `not-visible` are ALWAYS emitted, never omitted. In a flat tag bag an
absent tag is indistinguishable from an unknown one, and that distinction is the whole
reason the schema has both states.
"""
import json, sys, pathlib

SCHEMA = pathlib.Path(__file__).resolve().parent.parent / "docs/schema/trailer-photo-tags.schema.json"

# frame-level field -> tag namespace
FRAME_NS = {
    "media_kind": "media", "subject_type": "subject", "shot_type": "shot",
    "content_purpose": "purpose", "setting": "setting",
    "marketing_usability": "use", "competitor_branding_present": "competitor",
    "overall_confidence": "conf",
}
# per-trailer field -> tag namespace (prefixed with tN:)
TRAILER_NS = {
    "position_in_frame": "pos", "axle_count": "axle", "trailer_configuration": "config",
    "body_type": "body", "is_midland_product": "midland", "build_state": "build",
    "is_loaded": "loaded", "load_type": "load", "chassis_colour": "colour",
    "coupling_type": "coupling", "floor_type": "floor", "coaming_type": "coaming",
    "suspension_mount": "suspension", "front_load_restraint": "front-restraint",
    "rear_load_restraint": "rear-restraint", "front_ramp": "front-ramp",
    "rear_ramp": "rear-ramp", "confidence": "conf",
}

def slug(v):
    return str(v).replace("_", "-").lower()

def load():
    return json.loads(SCHEMA.read_text())

def vocabulary(max_trailers=6):
    s = load()
    v = s["properties"]["vision"]["properties"]
    t = v["trailers"]["items"]["properties"]
    out = []
    for f, ns in FRAME_NS.items():
        for e in v[f]["enum"]:
            out.append(f"{ns}:{slug(e)}")
    for e in v["defects"]["items"]["enum"]:
        out.append(f"defect:{slug(e)}")
    out.append("defect:none")                     # explicit, so "no defects" is assertable
    out.append("review:needed")
    for n in range(1, max_trailers + 1):
        for f, ns in TRAILER_NS.items():
            for e in t[f]["enum"]:
                out.append(f"t{n}:{ns}:{slug(e)}")
        out.append(f"trailers:{n}")
    out.append("trailers:0")
    return sorted(set(out))

def tags_for(record, prompt_version, model):
    """Flatten one schema-v2 record into the tags[] array for an ingest call."""
    v = record["vision"]; out = []
    for f, ns in FRAME_NS.items():
        if v.get(f) is not None:
            out.append(f"{ns}:{slug(v[f])}")
    d = v.get("defects") or []
    out += [f"defect:{slug(x)}" for x in d] or ["defect:none"]
    if v.get("needs_human_review"):
        out.append("review:needed")
    for name in v.get("competitor_names") or []:
        out.append(f"competitor-name:{slug(name).replace(' ', '-')}")
    trailers = v.get("trailers") or []
    out.append(f"trailers:{len(trailers)}")
    for i, tr in enumerate(trailers, start=1):
        for f, ns in TRAILER_NS.items():
            if tr.get(f) is not None:
                out.append(f"t{i}:{ns}:{slug(tr[f])}")
    # provenance travels as tags because the API exposes no provenance field
    out.append(f"promptver:{slug(prompt_version)}")
    out.append(f"model:{slug(model)}")
    pd = record.get("path_derived") or {}
    if pd.get("product_category"):
        out.append(f"category:{slug(pd['product_category']).replace(' ', '-')}")
    if pd.get("variant"):
        out.append(f"variant:{slug(pd['variant']).replace(' ', '-')}")
    return sorted(set(out))

if __name__ == "__main__":
    vocab = vocabulary()
    if "--json" in sys.argv:
        print(json.dumps(vocab, indent=1))
    else:
        print(f"{len(vocab)} tags to pre-register\n")
        ns = {}
        for tg in vocab:
            ns.setdefault(tg.split(":")[0], []).append(tg)
        for k in sorted(ns):
            print(f"{k:12s} {len(ns[k]):4d}")
