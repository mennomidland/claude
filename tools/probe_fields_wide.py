import sys, os, json
sys.path.insert(0, '/home/user/claude/tools')
import ingest_library as il

NAMES = [
  # removal, every spelling I can think of
  "removeTags","removeTag","tagsToRemove","tagsRemove","unsetTags","dropTags","detachTags",
  "deleteTags","deleteTag","tagsToDelete","removedTags","untag","untagAll","clearTags",
  "purgeTags","resetTags","pruneTags","truncateTags","removeTagIds","tagIdsToRemove",
  "excludeTags","negativeTags","minusTags","withdrawTags","retractTags","revokeTags",
  # replace / authoritative-set semantics
  "replaceTags","setTags","overwriteTags","syncTags","exclusiveTags","desiredTags",
  "finalTags","canonicalTags","tagSet","authoritativeTags","replaceExisting","replaceGroup",
  "replaceTagGroup","clearTagGroup","replaceNamespace","overwrite","isReplace","reconcile",
  "deleteMissingTags","removeMissingTags","deleteMissing","prune",
  # mode switches
  "tagMode","tagsMode","tagStrategy","tagOperation","tagAction","mode","op","operation",
  "strategy","action","replace","merge","append","replaceMode","tagSync",
  # byte-free addressing -- just as important
  "mediaId","sha256","sha","hash","existingMediaId","occurrenceId","skipUpload","tagsOnly",
]
CONTROLS = ["tags","createMissingTags","tagGroup","filename","dataBase64","driveId","itemId",
            "sourcePath","caption","albumName","createMissingAlbum","entityType","entityId",
            "trailer","job","contentType"]

key = os.environ["MEDIA_INGEST_KEY"]
payload = {n: {"__probe__": 1} for n in NAMES + CONTROLS}
status, resp = il.post(payload, key)
errs = (resp.get("errors") or {})
print("HTTP", status, "-- validator named", len(errs), "fields\n")
hits = [n for n in NAMES if n in errs]
ctl  = [n for n in CONTROLS if n in errs]
print("controls recognised :", len(ctl), "of", len(CONTROLS), "->", ", ".join(ctl))
print("candidates recognised:", hits or "NONE")
unknown_ctl = [n for n in CONTROLS if n not in errs]
if unknown_ctl:
    print("controls NOT named   :", unknown_ctl)
