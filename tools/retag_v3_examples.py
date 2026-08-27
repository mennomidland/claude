#!/usr/bin/env python3
"""Bring mediaId 5 and 6 up to schema v3, tagged from actually looking at each frame."""
import base64, json, os, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import graph_check as g
from tag_vocabulary import tags_for, VISION_NAMESPACE, STATE_NAMESPACE

INGEST = "https://qm3staging.midlandind.com.au/api/media/ingest"
PROMPT_VERSION, MODEL = "v3.0-features", "claude-opus-5"
MANIFEST = "/tmp/claude-0/-home-user-claude/f98d3e32-f559-5f1f-9db2-1a7eb6ab1152/scratchpad/manifest/manifest.jsonl"

BLANK = {"trailer_configuration": "unknown", "coupling_type": "unknown",
         "floor_type": "not_visible", "coaming_type": "not_visible",
         "suspension_mount": "not_visible", "front_load_restraint": "not_visible",
         "rear_load_restraint": "not_visible", "front_ramp": "not_visible",
         "rear_ramp": "not_visible", "plate_type": "no_plate_visible"}


def t(**kw):
    return {**BLANK, **kw}


RECORDS = {
"20251029_153352.jpg": {
  "caption": "Loaded skel combination, MSC containers — Tasman Logistics",
  "vision": {
    "media_kind": "photograph", "subject_type": "multiple_trailers",
    "shot_type": "side_elevation", "content_purpose": "marketing_photography",
    "competitor_branding_present": "none", "competitor_names": [],
    "setting": "yard_or_hardstand",
    "demonstrates": ["whole_trailer_appearance", "loaded_in_service",
                     "branding_or_livery", "wheel_finish"],
    "trailers": [
      t(position_in_frame="lead", axle_count="not_visible", body_type="skeletal",
        is_midland_product="midland", build_state="finished", is_loaded="loaded",
        load_type="shipping_containers", chassis_colour="grey_or_silver",
        components_visible=["chassis_rail", "twist_locks", "landing_legs", "mudflaps"],
        features_present=[], identifying_text=["MIDLAND"], confidence="medium",
        notes="Carries two 20ft MSC boxes. Its axle group is shadowed and not separable "
              "from the following unit's in this frame."),
      t(position_in_frame="second", axle_count="tri", body_type="skeletal",
        is_midland_product="midland", build_state="finished", is_loaded="loaded",
        load_type="shipping_containers", chassis_colour="grey_or_silver",
        components_visible=["axle_group", "wheels_rims", "tyres", "mudguards",
                            "mudflaps", "chassis_rail", "suspension", "twist_locks"],
        features_present=[], identifying_text=["MIDLAND"], confidence="high",
        notes="Tri group fully in frame: three axles, white guards, polished alloy rims."),
    ],
    "visible_text": ["MEDITERRANEAN SHIPPING CO", "MSC", "MIDLAND",
                     "TASMAN LOGISTICS SERVICES", "22G1"],
    "marketing_usability": "hero", "defects": [], "duplicate_group": None,
    "overall_confidence": "high", "needs_human_review": True,
    "notes": "Twist lock hardware is visible on the rail but the auto actuator is not "
             "legible at this resolution, so auto_twist_locks is NOT claimed despite the "
             "folder name. Also: the v2 worked example attributes the tri group to the "
             "LEAD unit; read here it sits under the second. Needs a human call.",
  },
  "audit": {"axle_agreement": "path_unstated", "category_agreement": "agree",
            "provenance_conflict": False, "non_marketing_in_marketing_folder": False},
},
"Midland Trailors CivicCast 13.jpg": {
  "caption": "Flat deck loaded with precast concrete at CivilCast — load restraint in use",
  "vision": {
    "media_kind": "photograph", "subject_type": "multiple_trailers",
    "shot_type": "in_service_loaded", "content_purpose": "marketing_photography",
    "competitor_branding_present": "none", "competitor_names": [],
    "setting": "customer_site",
    "demonstrates": ["load_restraint_in_use", "loaded_in_service",
                     "deck_configuration", "whole_trailer_appearance"],
    "trailers": [
      t(position_in_frame="lead", axle_count="tri", body_type="flat_top",
        is_midland_product="midland", build_state="finished", is_loaded="loaded",
        load_type="steel_or_building_products", chassis_colour="grey_or_silver",
        front_load_restraint="none", rear_load_restraint="none",
        components_visible=["axle_group", "wheels_rims", "tyres", "mudguards", "mudflaps",
                            "chassis_rail", "deck_floor", "toolbox", "ladder",
                            "load_racks"],
        features_present=["toolbox", "ladder"], identifying_text=["MIDLAND"],
        confidence="high",
        notes="Precast concrete units strapped with blue webbing. Tri-axle group clearly "
              "in frame with three alloy rims."),
      t(position_in_frame="second", axle_count="not_visible", body_type="flat_top",
        is_midland_product="midland", build_state="finished", is_loaded="empty",
        load_type="none", chassis_colour="grey_or_silver",
        components_visible=["deck_floor", "chassis_rail", "landing_legs"],
        features_present=[], identifying_text=[], confidence="medium",
        notes="Second flat deck alongside, empty, being loaded by forklift."),
    ],
    "visible_text": ["CIVILCAST", "MIDLAND", "KOMATSU", "1800 134 058",
                     "EXPERT ADVICE", "LARGE STOCKS", "FAST LEAD TIMES"],
    "marketing_usability": "good", "defects": ["people_visible"],
    "duplicate_group": None, "overall_confidence": "high", "needs_human_review": True,
    "notes": "Professionally shot. Folder path reads '2 Axle Dog Trailer' but three axles "
             "are clearly visible on the loaded unit -- flagged as an axle disagreement "
             "for a human to resolve: either the frame is filed in the wrong folder, or "
             "the folder term counts something other than axles.",
  },
  "audit": {"axle_agreement": "disagree", "category_agreement": "not_comparable",
            "provenance_conflict": False, "non_marketing_in_marketing_folder": False},
},
}


def main():
    key = os.environ["MEDIA_INGEST_KEY"]
    st = {}
    g.step2_token(st)
    tok = st["token"]
    recs = [json.loads(l) for l in open(MANIFEST)]

    for name, spec in RECORDS.items():
        p = next(r["photo"] for r in recs if r["photo"]["filename"] == name)
        pd = next(r["path_derived"] for r in recs if r["photo"]["filename"] == name)
        w, h = p["width"], p["height"]
        # full-resolution rendition: smaller than /content, auto-oriented, under the cap
        sz = f"c{w}x{h}_Crop"
        _, _, rb = g.request(
            f"{g.GRAPH}/drives/{g.DRIVE_ID}/items/{p['item_id']}/thumbnails?select={sz}&expand={sz}",
            token=tok)
        _, _, img = g.request(json.loads(rb)["value"][0][sz]["url"])

        record = {"schema_version": "3.0", "vision": spec["vision"],
                  "audit": spec["audit"], "path_derived": pd}
        sets = tags_for(record, PROMPT_VERSION, MODEL)
        print(f"\n{name}")
        print(f"  {len(img)/1e6:.1f} MB rendition (original {p['size_bytes']/1e6:.1f} MB)")
        print(f"  search {len(sets[VISION_NAMESPACE])} / state {len(sets[STATE_NAMESPACE])}")
        content = [x for x in sets[VISION_NAMESPACE]
                   if x.split(":")[0] in ("component", "feature", "demonstrates")]
        print(f"  content tags: {', '.join(content)}")

        for ns in (VISION_NAMESPACE, STATE_NAMESPACE):
            body = json.dumps({
                "filename": name, "dataBase64": base64.b64encode(img).decode(),
                "contentType": "image/jpeg", "tags": sets[ns], "createMissingTags": True,
                "tagGroup": ns, "caption": spec["caption"], "sourcePath": p["path"],
                "driveId": g.DRIVE_ID, "itemId": p["item_id"],
            }).encode()
            s, _, resp = g.request(INGEST, method="POST", data=body,
                                   headers={"Content-Type": "application/json",
                                            "x-media-key": key})
            d = json.loads(resp)
            print(f"    {ns:24s} HTTP {s} mediaId={d.get('mediaId')} "
                  f"occ={d.get('occurrenceId')} applied={len(d.get('appliedTags') or [])}")


if __name__ == "__main__":
    main()
