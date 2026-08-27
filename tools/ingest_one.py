#!/usr/bin/env python3
"""Reference client: Graph bytes -> schema-v2 tag record -> /api/media/ingest.

The worked end-to-end example behind `routines/03-media-library-api.md`. Writes ONE asset
into staging. The vision record below was produced by looking at the frame, so the
pipeline is exercised with a real record rather than a stub.

Two things this deliberately demonstrates, both covered in that file:
  * `attributes` / `model` / `promptVersion` are sent but are NOT in the API validator --
    they return 200 and are silently dropped. The flat `tags[]` bag is the real contract.
  * bytes come from `/content` here. For a bulk run prefer the full-resolution Graph
    rendition: ~4x smaller, auto-oriented, and it stays under the 40 MB base64 cap.
"""
import base64, json, os, sys, urllib.parse
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import graph_check as g
from tag_vocabulary import tags_for

ITEM_NAME = "20241010_084259.jpg"
FOLDER = "Sales/1. Trailer Photos/Auto Twist Lock Skels"
PROMPT_VERSION = "v2.0-e2e"
MODEL = "claude-opus-5"
NAMESPACE = "trailer-photo:vision"
INGEST = "https://qm3staging.midlandind.com.au/api/media/ingest"

VISION = {
    "media_kind": "photograph",
    "subject_type": "partial_view_cropped",
    "shot_type": "side_elevation",
    "content_purpose": "marketing_photography",
    "non_marketing_reason": None,
    "competitor_branding_present": "none",
    "competitor_names": [],
    "setting": "yard_or_hardstand",
    "trailers": [
        {
            "position_in_frame": "lead",
            "axle_count": "not_visible",
            "trailer_configuration": "unknown",
            "body_type": "skeletal",
            "is_midland_product": "midland",
            "build_state": "finished",
            "is_loaded": "loaded",
            "load_type": "shipping_containers",
            "chassis_colour": "pearl_white",
            "coupling_type": "unknown",
            "floor_type": "no_floor_skeletal",
            "coaming_type": "none",
            "suspension_mount": "not_visible",
            "front_load_restraint": "not_visible",
            "rear_load_restraint": "not_visible",
            "front_ramp": "none",
            "rear_ramp": "none",
            "identifying_text": ["MIDLAND"],
            "plate_type": "no_plate_visible",
            "confidence": "medium",
            "notes": "Skeletal semi carrying a rust-red container. The axle group is cut "
                     "at the left frame edge, so the count cannot be taken from this "
                     "frame; confidence capped for that reason.",
        },
        {
            "position_in_frame": "second",
            "axle_count": "not_visible",
            "trailer_configuration": "unknown",
            "body_type": "not_visible",
            "is_midland_product": "midland",
            "build_state": "unknown",
            "is_loaded": "not_visible",
            "load_type": "not_visible",
            "chassis_colour": "not_visible",
            "coupling_type": "unknown",
            "floor_type": "not_visible",
            "coaming_type": "not_visible",
            "suspension_mount": "not_visible",
            "front_load_restraint": "not_visible",
            "rear_load_restraint": "not_visible",
            "front_ramp": "not_visible",
            "rear_ramp": "not_visible",
            "identifying_text": ["MIDLAND", "BEHIND YOU ALL THE WAY"],
            "plate_type": "no_plate_visible",
            "confidence": "low",
            "notes": "Only the rear mudflap and tail lamp of a second unit enter the "
                     "frame at the right edge. Midland branding legible on the mudflap.",
        },
    ],
    "visible_text": ["MIDLAND", "BEHIND YOU ALL THE WAY", "HAULSTAR", "LEGION"],
    "marketing_usability": "usable",
    "defects": ["partial_crop"],
    "duplicate_group": None,
    "overall_confidence": "medium",
    "needs_human_review": False,
    "notes": "Close side view showing the auto twist lock control panel and air lines. "
             "Useful as a feature detail rather than a whole-trailer hero frame.",
}
AUDIT = {
    "axle_agreement": "path_unstated",
    "category_agreement": "agree",
    "provenance_conflict": False,
    "non_marketing_in_marketing_folder": False,
}


def main():
    key = os.environ.get("MEDIA_INGEST_KEY")
    if not key:
        raise SystemExit("MEDIA_INGEST_KEY not set")

    state = {}
    ok, detail = g.step2_token(state)
    if not ok:
        raise SystemExit(f"graph auth failed: {detail}")
    tok = state["token"]

    # 1. locate the item
    path = urllib.parse.quote(FOLDER)
    s, _, b = g.request(f"{g.GRAPH}/drives/{g.DRIVE_ID}/root:/{path}:/children?$top=200", token=tok)
    item = {c["name"]: c for c in json.loads(b)["value"]}[ITEM_NAME]
    print(f"1. item      {item['id']}  {item['size']/1e6:.1f} MB  "
          f"{item['image']['width']}x{item['image']['height']}")

    # 2. original bytes (the library auto-orients its own renditions, so store the original)
    s, _, raw = g.request(f"{g.GRAPH}/drives/{g.DRIVE_ID}/items/{item['id']}/content", token=tok)
    print(f"2. bytes     {len(raw)} fetched, status {s}")

    # 3. flatten the schema record into the flat tag bag the API actually accepts
    record = {"vision": VISION, "audit": AUDIT,
              "path_derived": {"product_category": "Auto Twist Lock Skels", "variant": None}}
    tags = tags_for(record, PROMPT_VERSION, MODEL)
    print(f"3. tags      {len(tags)} generated, e.g. {tags[:4]}")

    payload = {
        "filename": ITEM_NAME,
        "dataBase64": base64.b64encode(raw).decode(),
        "contentType": "image/jpeg",
        "tags": tags,
        "createMissingTags": True,
        "tagGroup": NAMESPACE,
        "caption": "Auto twist lock skel, loaded — side detail (end-to-end pipeline test)",
        "sourcePath": f"{FOLDER}/{ITEM_NAME}",
        "driveId": g.DRIVE_ID,
        "itemId": item["id"],
        # attributes/model/promptVersion are NOT in the API's validator yet -- sent here
        # deliberately to confirm whether they are stored or silently dropped.
        "attributes": {"trailers": [
            {"axle": t["axle_count"], "body": t["body_type"], "midland": t["is_midland_product"]}
            for t in VISION["trailers"]]},
        "model": MODEL,
        "promptVersion": PROMPT_VERSION,
    }
    body = json.dumps(payload).encode()
    print(f"4. POST      {len(body)/1e6:.1f} MB payload -> {INGEST}")
    s, h, resp = g.request(INGEST, method="POST", data=body,
                           headers={"Content-Type": "application/json", "x-media-key": key})
    print(f"5. response  HTTP {s}")
    try:
        print(json.dumps(json.loads(resp), indent=1)[:1500])
    except Exception:
        print(resp[:800])


if __name__ == "__main__":
    main()
