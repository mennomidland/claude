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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
# Reused rather than re-declared: a folder-segment rule that drifts from the one the
# enumeration used would tag paths differently from how they were parsed.
from enumerate_delta import NUM_PREFIX, BUILD_DATE

SCHEMA = pathlib.Path(__file__).resolve().parent.parent / "docs/schema/trailer-photo-tags.schema.json"

# frame-level field -> tag namespace
FRAME_NS = {
    "media_kind": "media", "subject_type": "subject", "shot_type": "shot",
    "content_purpose": "purpose", "setting": "setting",
    "marketing_usability": "use", "competitor_branding_present": "competitor",
    "overall_confidence": "conf",
    "combination_type": "combo",   # v4
}
# per-trailer field -> tag namespace (prefixed with tN:)
TRAILER_NS = {
    "position_in_frame": "pos", "axle_count": "axle", "trailer_configuration": "config",
    "body_type": "body", "is_midland_product": "midland", "build_state": "build",
    "is_loaded": "loaded", "load_type": "load", "chassis_colour": "colour",
    "coupling_type": "coupling", "coaming_type": "coaming",
    "suspension_mount": "suspension", "front_load_restraint": "front-restraint",
    "rear_load_restraint": "rear-restraint", "front_ramp": "front-ramp",
    "rear_ramp": "rear-ramp", "confidence": "conf",
    # v4
    "combination_role": "role", "suspension_type": "susp", "deck_material": "deck",
    "container_capability": "container", "axle_group_layout": "layout",
    "manufacturer_confidence": "mfr-conf",
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
    # Component / feature / demonstrates are unprefixed: they answer "is X in this photo",
    # not "which unit was it attached to", so they do not multiply by max_trailers.
    for e in v["demonstrates"]["items"]["enum"]:
        out.append(f"demonstrates:{slug(e)}")
    for e in t["components_visible"]["items"]["enum"]:
        out.append(f"component:{slug(e)}")
    for e in t["features_present"]["items"]["enum"]:
        out.append(f"feature:{slug(e)}")
    return sorted(set(out))

ABSENT = ("unknown", "not-visible", "not-applicable")

VISION_NAMESPACE = "trailer-photo:vision"   # positive: what the photo shows
STATE_NAMESPACE = "trailer-photo:state"     # absence: looked, could not tell

def tags_for(record, prompt_version, model):
    """Flatten one schema-v4 record into ingest tag sets, keyed by namespace.

    Returns {namespace: [tags]} rather than one list, because the two kinds of tag serve
    different readers and must not share a search index:

    * `trailer-photo:vision` -- what the photo actually shows. This is what a person
      searches. Component, feature and `demonstrates` tags are emitted UNPREFIXED and
      unioned across units: someone looking for a frame with a control panel in it does
      not care whether it belonged to unit 1 or unit 2.
    * `trailer-photo:state` -- every field that came back `unknown` / `not_visible`.
      Worthless to a searcher and 43% of the bag on a real frame, but it is how you tell a
      badly defined field (always unknown) from a guessed one (never unknown), and keeping
      the model free to say "cannot tell" is what stops it inventing specifications.

    Both are written per (asset, namespace), so a re-tag of one leaves the other alone.
    """
    v = record["vision"]
    search, state = [], []

    def put(tag):
        (state if tag.rsplit(":", 1)[-1] in ABSENT else search).append(tag)

    for f, ns in FRAME_NS.items():
        if v.get(f) is not None:
            put(f"{ns}:{slug(v[f])}")
    search += [f"defect:{slug(x)}" for x in (v.get("defects") or [])] or ["defect:none"]
    if v.get("needs_human_review"):
        search.append("review:needed")
    for name in v.get("competitor_names") or []:
        search.append(f"competitor-name:{slug(name).replace(' ', '-')}")
    if v.get("ata_configuration_code"):
        search.append(f"ata:{slug(v['ata_configuration_code'])}")

    # The frame-level answer to "why would anyone pull this photo out of the library".
    for d in v.get("demonstrates") or []:
        search.append(f"demonstrates:{slug(d)}")

    trailers = v.get("trailers") or []
    search.append(f"trailers:{len(trailers)}")
    for i, tr in enumerate(trailers, start=1):
        for f, ns in TRAILER_NS.items():
            if tr.get(f) is not None:
                put(f"t{i}:{ns}:{slug(tr[f])}")
        # Unprefixed and unioned -- these answer "is X in this photo", not "which unit".
        for c in tr.get("components_visible") or []:
            if c != "none_identifiable":
                search.append(f"component:{slug(c)}")
        for ft in tr.get("features_present") or []:
            if ft != "none_visible":
                search.append(f"feature:{slug(ft)}")
        # Builder name as READ from a decal -- never inferred from livery.
        for mk in tr.get("manufacturer_decal_text") or []:
            search.append(f"mfr:{slug(mk).replace(' ', '-')}")

    # provenance travels as tags because the API exposes no provenance field
    search += [f"promptver:{slug(prompt_version)}", f"model:{slug(model)}"]
    # Path-derived terms are emitted under `folder:`, NOT `category:`. The folder is a
    # hypothesis, not a classification: `Midland Trailors CivicCast 13.jpg` sits under
    # Dog Trailers and shows a tri-axle flat top semi, so `category:dog-trailers` asserted
    # something false into the search index. `folder:dog-trailers` says only where the file
    # lives, which is true and still useful for narrowing a search.
    pd = record.get("path_derived") or {}
    if pd.get("product_category"):
        search.append(f"folder:{slug(pd['product_category']).replace(' ', '-')}")
    if pd.get("variant"):
        search.append(f"folder-variant:{slug(pd['variant']).replace(' ', '-')}")
    # EVERY meaningful folder level, not just the top two. `DSC_0045.jpg` is filed under
    # ".../1. Semi Drop Deck Trailers/2. Semi Drop Deck Widener Trailers/2025.07 - Simon
    # Turnbull 4m Widener - 2896/...": the word that makes it findable -- widener -- is at
    # level 3, and taking only two levels dropped it entirely. Nobody searching "widener"
    # would have found the photo. Customer/date folders are excluded because `customer`,
    # `build_date` and `job_numbers` already carry that, and folder-derived terms stay under
    # `folder:` so they never read as a classification the photo itself supports.
    for seg in (pd.get("folder_path") or "").split("/"):
        seg = NUM_PREFIX.sub("", seg).strip()
        if not seg or BUILD_DATE.match(seg):
            continue
        search.append(f"folder:{slug(seg).replace(' ', '-')}")
    # What the PHOTO says the product is, from vision -- distinct from where it is filed.
    for tr in trailers:
        if tr.get("body_type") not in (None, "not_visible", "unknown"):
            search.append(f"product:{slug(tr['body_type'])}")

    return {VISION_NAMESPACE: sorted(set(search)), STATE_NAMESPACE: sorted(set(state))}

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
