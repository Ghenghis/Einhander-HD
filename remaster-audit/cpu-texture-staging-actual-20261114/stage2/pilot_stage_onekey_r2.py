"""s23 one-key J10 runtime pilot STAGER r2 (r1 0b4e0c16... and r0 7f59f1ea... preserved). Stages files only;
it never launches the game. Each mode runs only under a coordinator grant/staging slot.

  python -I -B pilot_stage_onekey_r1.py selftest <new_dir>                         settings-patch fixtures (pure, tiny)
  python -I -B pilot_stage_onekey_r1.py qualify  <new_dir>                         write a pinnable v68 cache manifest
  python -I -B pilot_stage_onekey_r1.py stage    <new_pilot_dir> <manifest> <manifest_sha256>

r2 = codex-einhander review msg_1b0641efa6ee1c91 of r1: the stage manifest is read ONCE (bytes -> sha256 -> json.loads);
every namespace (s23/runs, s23/pilot) and every source must RESOLVE inside C:/github/Einhander (realpath, so ancestor
junctions are covered); the qualify receipt states that it records only an immutable CURRENT cache inventory, not
historical code correctness or ABI compatibility. The cue .bin stays size-only: executable/ROM binding remains the
qualified launcher's responsibility before any launch.
r1 fixed codex-einhander's full review msg_ef85dad7bfc28339 of r0:
  * r0 BUG: `hd_textures = true` was counted as a change although it is unchanged, so the diff (4 lines) never matched the
    5 recorded lines and staging ALWAYS failed. r1 separates ONE asserted-unchanged line from FOUR mutations
    ([video] hd_texture_root, [memcard] dir / card1 / card2), each anchor exactly once in its section, every other byte
    identical; selftest covers the assertion, the 4 mutations, missing and duplicate anchors, LF and CRLF;
  * the settings file is read ONCE; its raw bytes must hash to db24f4ab... and exactly those bytes are patched;
  * cache is COPY-ONLY (no hardlinks: a game rewriting a shared file could not be undone for v68);
  * the cache must match a QUALIFIED manifest: no existing v68 staging receipt lists the cache (build.json 21944d69...
    covers the exe/link inputs only), so `qualify` writes one (sorted rel path, size, sha256; refuses unless exactly
    EXPECTED_CACHE_FILES files) and `stage` copies only against that manifest pinned by sha256 (count, sizes, hashes);
  * paths: the pilot must resolve inside s23/pilot; every source and every cache entry must resolve inside
    C:/github/Einhander and must not be a symlink, junction or other reparse point (checked with lstat attributes);
  * every copy and receipt is written exclusively into the fresh tree, flushed and fsynced, then re-hashed from disk;
  * the launch plan names only paths inside the new pilot tree; inherited settings paths (BIOS, disc cue) are pinned
    and disclosed separately (the cue's referenced .bin is not hashed: size only).
Layout: hdroot/28127931-7C2D834A.png (only file), runtime/Einhander_Recompiled.exe + settings.toml + cache/,
state/card1.mcd, logs/ (PSXRECOMP_HD_PROOF_LOG target must not exist). No Hashes.ini in hdroot or the pilot folder
(the loader falls back to the parent's Hashes.ini, hd_texture_pack.cpp:1101-1104). Exit 0 ok, 2 error, 3 refused.
"""
import hashlib
import json
import os
import stat
import sys
import time
from datetime import datetime, timezone

EXIT_OK, EXIT_FAIL, EXIT_REFUSED = 0, 2, 3
PROJECT = "C:/github/Einhander"
RA = PROJECT + "/remaster-audit"
S23 = RA + "/parallel-stages-20261114/s23"
PILOT_NS = S23 + "/pilot"
V68 = RA + "/dev-center-evidence/stage1-completion-20261112/v68-unassisted-r1/hd-on_rewind-off"
KEY = "28127931-7C2D834A"
PNG = dict(path=S23 + "/proposals/j10-preview-2152/s2-28127931-7C2D834A/keys/page2048/28127931-7C2D834A.png",
           sha256="40434c40285348142b15c2609e572c0aa640eca9d886e3021e50d6c7fb5ff70a")
EXE = dict(path=V68 + "/runtime/Einhander_Recompiled.exe", sha256="5c1436ff778701d981410da61046aca60c0da60215a5f724523197b58199dfaa")
SETTINGS = dict(path=V68 + "/runtime/settings.toml", sha256="db24f4abd3529aae216618406fd978418a8f08850b5c2a06bdea295e17ce525c")
CARD1 = dict(path=V68 + "/state/card1.mcd", sha256="8156843599078d7776e54a385ffbb523415bd5ad32eeb0cd47fba44e362b2595")
CACHE = V68 + "/runtime/cache"
EXPECTED_CACHE_FILES = 4405
ASSERT = [("[video]", "hd_textures = true")]
MUTATE_FROM = [("[video]", 'hd_texture_root = "' + RA + '/dev-center-evidence/stage1-completion-20261112/world-integrated-mijpq-roi-r1/pack"'),
               ("[memcard]", 'dir = "' + V68 + '/state"'),
               ("[memcard]", 'card1 = "' + V68 + '/state/card1.mcd"'),
               ("[memcard]", 'card2 = "' + V68 + '/state/card2.mcd"')]


def mutate_to(pilot):
    return ['hd_texture_root = "' + pilot + '/hdroot"', 'dir = "' + pilot + '/state"',
            'card1 = "' + pilot + '/state/card1.mcd"', 'card2 = "' + pilot + '/state/card2.mcd"']


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def refuse(reason):
    print(json.dumps(dict(status="REFUSED", reason=reason, utc=datetime.now(timezone.utc).isoformat())), flush=True)
    sys.exit(EXIT_REFUSED)


def norm(p):
    return os.path.normcase(os.path.realpath(p))


def inside(p, root):
    try:
        return os.path.commonpath([norm(p), norm(root)]) == norm(root)
    except ValueError:
        return False


def plain(p):
    """True if p is not a symlink / junction / reparse point (lstat, no following)."""
    st = os.lstat(p)
    if stat.S_ISLNK(st.st_mode):
        return False
    return not (getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def patch_settings(raw, pilot):
    """Pure: (patched_bytes, report). Raises ValueError on any anchor that is missing or not unique in its section,
    or if anything other than the four mutation lines would change."""
    text = raw.decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    section, hits = None, {i: [] for i in range(len(ASSERT) + len(MUTATE_FROM))}
    anchors = ASSERT + MUTATE_FROM
    for n, line in enumerate(lines):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s
            continue
        for i, (sec, old) in enumerate(anchors):
            if section == sec and line == old:
                hits[i].append(n)
    for i, rows in hits.items():
        if len(rows) != 1:
            raise ValueError(f"anchor {anchors[i]} found {len(rows)} times (need exactly 1)")
    new_lines = list(lines)
    targets = mutate_to(pilot)
    mutated = []
    for j, (sec, old) in enumerate(MUTATE_FROM):
        n = hits[len(ASSERT) + j][0]
        new_lines[n] = targets[j]
        mutated.append(dict(line=n + 1, section=sec, old=old, new=targets[j]))
    out = nl.join(new_lines).encode("utf-8")
    diff = [n + 1 for n, (a, b) in enumerate(zip(lines, new_lines)) if a != b]
    if len(new_lines) != len(lines) or diff != sorted(m["line"] for m in mutated) or len(diff) != len(MUTATE_FROM):
        raise ValueError(f"patch changed lines {diff}, expected exactly the {len(MUTATE_FROM)} mutation lines")
    asserted = [dict(line=hits[i][0] + 1, section=ASSERT[i][0], text=ASSERT[i][1], unchanged=lines[hits[i][0]] == new_lines[hits[i][0]])
                for i in range(len(ASSERT))]
    if not all(a["unchanged"] for a in asserted):
        raise ValueError("an asserted line changed")
    return out, dict(asserted_unchanged=asserted, mutated=mutated, newline="CRLF" if nl == "\r\n" else "LF", lines=len(lines))


def selftest():
    pilot = PILOT_NS + "/j10-onekey-FIXTURE"
    base = ["[video]", "renderer = \"opengl\"", ASSERT[0][1], MUTATE_FROM[0][1], "[audio]", "volume = 80", "[memcard]",
            MUTATE_FROM[1][1], MUTATE_FROM[2][1], MUTATE_FROM[3][1], "enable1 = true", ""]
    r = {}
    for nlname, nl in (("LF", "\n"), ("CRLF", "\r\n")):
        raw = nl.join(base).encode("utf-8")
        out, rep = patch_settings(raw, pilot)
        o_lines, n_lines = raw.decode().split(nl), out.decode().split(nl)
        changed = [i for i, (a, b) in enumerate(zip(o_lines, n_lines)) if a != b]
        r[f"ok_{nlname}"] = (len(rep["mutated"]) == 4 and rep["asserted_unchanged"][0]["unchanged"] and len(changed) == 4
                             and n_lines[2] == ASSERT[0][1] and all(o_lines[i] == n_lines[i] for i in range(len(o_lines)) if i not in changed))
    for name, mutate in (("missing_assert", lambda b: [x for x in b if x != ASSERT[0][1]]),
                         ("missing_mutation", lambda b: [x for x in b if x != MUTATE_FROM[2][1]]),
                         ("duplicate_mutation", lambda b: b[:9] + [MUTATE_FROM[2][1]] + b[9:]),
                         ("assert_wrong_section", lambda b: [x for x in b if x != ASSERT[0][1]][:5] + [ASSERT[0][1]] + [x for x in b if x != ASSERT[0][1]][5:]),
                         ("assert_false", lambda b: [("hd_textures = false" if x == ASSERT[0][1] else x) for x in b])):
        try:
            patch_settings("\n".join(mutate(list(base))).encode("utf-8"), pilot)
            r[f"rejects_{name}"] = False
        except ValueError:
            r[f"rejects_{name}"] = True
    r["passed"] = all(r.values())
    return r


def inherited_paths(raw):
    """Disclose the unchanged [bios] / [disc] paths of the pinned settings (read by the game at launch, not copied):
    each must be a plain in-project file; the BIOS and the cue are hashed; files a cue references are recorded by size."""
    text = raw.decode("utf-8").replace("\r\n", "\n")
    section, found = None, {}
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s
            continue
        if section in ("[bios]", "[disc]") and s.startswith("path") and "=" in s:
            found[section] = s.split("=", 1)[1].strip().strip('"')
    out = {}
    for sec in ("[bios]", "[disc]"):
        p = found.get(sec)
        if not p or not os.path.isfile(p) or not plain(p) or not inside(p, PROJECT):
            raise RuntimeError(f"inherited {sec} path missing, linked or outside the project: {p}")
        item = dict(path=p, sha256=sha_file(p), size=os.path.getsize(p))
        if p.lower().endswith(".cue"):
            refs = []
            for cl in open(p, encoding="utf-8", errors="replace"):
                cl = cl.strip()
                if cl.upper().startswith("FILE") and '"' in cl:
                    ref = os.path.join(os.path.dirname(p), cl.split('"')[1])
                    if not os.path.isfile(ref) or not plain(ref) or not inside(ref, PROJECT):
                        raise RuntimeError(f"cue reference missing, linked or outside the project: {ref}")
                    refs.append(dict(path=ref.replace("\\", "/"), size=os.path.getsize(ref), hashed=False))
            item["cue_files"] = refs
        out[sec] = item
    out["note"] = "unchanged settings lines, shared read-only inputs (same as the v68 run); the .bin is size-checked only"
    return out


def write_x(path, data):
    with open(path, "xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    return sha_file(path)


def copy_x(src, dst, expect):
    if not plain(src) or not inside(src, PROJECT):
        raise RuntimeError(f"source not a plain in-project file: {src}")
    with open(src, "rb") as fi, open(dst, "xb") as fo:
        for chunk in iter(lambda: fi.read(1 << 20), b""):
            fo.write(chunk)
        fo.flush()
        os.fsync(fo.fileno())
    got = sha_file(dst)
    if got != expect:
        raise RuntimeError(f"copy hash mismatch {dst}: {got} != {expect}")
    return got


def walk_cache():
    """Sorted list of (rel, abs) plain in-project files under CACHE; refuses links/junctions/reparse points."""
    if not plain(CACHE) or not inside(CACHE, PROJECT):
        raise RuntimeError("cache root is not a plain in-project directory")
    out = []
    for dirpath, dirnames, filenames in os.walk(CACHE, followlinks=False):
        for d in list(dirnames):
            if not plain(os.path.join(dirpath, d)):
                raise RuntimeError(f"cache contains a link/junction directory: {os.path.join(dirpath, d)}")
        dirnames.sort()
        for name in sorted(filenames):
            p = os.path.join(dirpath, name)
            if not plain(p) or not inside(p, CACHE):
                raise RuntimeError(f"cache contains a link or out-of-tree file: {p}")
            out.append((os.path.relpath(p, CACHE).replace("\\", "/"), p))
    return out


def new_dir(path, ns):
    parent = os.path.dirname(os.path.abspath(path))
    if not inside(ns, PROJECT):
        refuse(f"namespace does not resolve inside the project: {ns}")
    if not os.path.isdir(parent) or not plain(parent) or not inside(parent, ns) or os.path.lexists(path):
        refuse(f"output must be a NEW folder inside {ns}: {path}")
    try:
        os.mkdir(path)
    except OSError as e:
        refuse(f"exclusive mkdir failed: {e}")
    if not inside(path, ns):
        refuse("output escaped its namespace")
    return os.path.realpath(path).replace("\\", "/")


def finish(out, rec, ok, t0, name):
    rec["ok"] = bool(ok)
    rec["exit_code"] = EXIT_OK if ok else EXIT_FAIL
    rec["seconds"] = round(time.monotonic() - t0, 2)
    rec["finished_utc"] = datetime.now(timezone.utc).isoformat()
    h = write_x(f"{out}/{name}", json.dumps(rec, indent=1).encode("utf-8"))
    print(json.dumps({q: rec.get(q) for q in ("ok", "exit_code", "error", "seconds")}), name, h, flush=True)
    return rec["exit_code"]


def main(argv):
    t0 = time.monotonic()
    if sys.flags.optimize:
        refuse("run without -O")
    if not sys.flags.isolated:
        refuse("run with python -I")
    if len(argv) < 2 or argv[0] not in ("selftest", "qualify", "stage"):
        refuse("usage: selftest <new_dir> | qualify <new_dir> | stage <new_pilot_dir> <manifest> <manifest_sha256>")
    mode = argv[0]
    base = dict(owner="claude-einhander-s23", tool="pilot_stage_onekey_r2.py", self_sha256=sha_file(os.path.abspath(__file__)), mode=mode,
                started_utc=datetime.now(timezone.utc).isoformat(), pid=os.getpid(), affinity=os.environ.get("S23_CPU"))
    if mode == "selftest":
        out = new_dir(argv[1], S23 + "/runs")
        rec, ok = dict(base), False
        try:
            rec["selftest"] = selftest()
            ok = rec["selftest"]["passed"]
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"
        return finish(out, rec, ok, t0, "SELFTEST.json")
    if mode == "qualify":
        out = new_dir(argv[1], S23 + "/runs")
        rec, ok = dict(base, cache_root=CACHE, expected_files=EXPECTED_CACHE_FILES,
                       inventory_scope="immutable CURRENT inventory of the v68 runtime cache (relative names, sizes, sha256) at qualify time; it does NOT establish historical code correctness or ABI compatibility of the cached overlays"), False
        try:
            entries = walk_cache()
            man = [dict(rel=rel, size=os.path.getsize(p), sha256=sha_file(p)) for rel, p in entries]
            if len(man) != EXPECTED_CACHE_FILES:
                raise RuntimeError(f"cache has {len(man)} files, expected {EXPECTED_CACHE_FILES}")
            h = write_x(f"{out}/cache-manifest.json", json.dumps(man).encode("utf-8"))
            rec["manifest"] = dict(path=f"{out}/cache-manifest.json", sha256=h, files=len(man), bytes=sum(m["size"] for m in man))
            ok = True
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"
        return finish(out, rec, ok, t0, "QUALIFY.json")
    # ---- stage
    if len(argv) != 4:
        refuse("stage needs <new_pilot_dir> <manifest> <manifest_sha256>")
    man_path, man_sha = argv[2], argv[3]
    for pin in (PNG, EXE, CARD1):
        if not os.path.isfile(pin["path"]) or not plain(pin["path"]) or not inside(pin["path"], PROJECT) or sha_file(pin["path"]) != pin["sha256"]:
            refuse(f"pinned source missing, linked, out of project or changed: {pin['path']}")
    for root in (S23, PILOT_NS, V68, CACHE):
        if not inside(root, PROJECT):
            refuse(f"does not resolve inside the project: {root}")
    if not os.path.isfile(man_path) or not plain(man_path) or not inside(man_path, S23 + "/runs"):
        refuse("cache manifest missing, linked or outside s23/runs")
    with open(man_path, "rb") as f:
        man_bytes = f.read()                                            # read ONCE
    if sha_bytes(man_bytes) != man_sha:
        refuse("cache manifest bytes do not hash to the pin")
    man = json.loads(man_bytes.decode("utf-8"))
    with open(SETTINGS["path"], "rb") as f:
        if not plain(SETTINGS["path"]) or not inside(SETTINGS["path"], PROJECT):
            refuse("settings source linked or out of project")
        raw = f.read()                                                     # read ONCE
    if sha_bytes(raw) != SETTINGS["sha256"]:
        refuse("settings bytes do not hash to the pin")
    if os.path.lexists(PILOT_NS + "/Hashes.ini"):
        refuse("a Hashes.ini exists in the pilot namespace parent")
    pilot = new_dir(argv[1], PILOT_NS)
    rec, ok = dict(base, pilot=pilot, sources=dict(png=PNG, exe=EXE, settings=SETTINGS, card1=CARD1, cache=CACHE,
                                                    cache_manifest=dict(path=man_path, sha256=man_sha))), False
    try:
        for sub in ("hdroot", "runtime", "runtime/cache", "state", "logs"):
            os.mkdir(f"{pilot}/{sub}")
        rec["png"] = copy_x(PNG["path"], f"{pilot}/hdroot/{KEY}.png", PNG["sha256"])
        rec["exe"] = copy_x(EXE["path"], f"{pilot}/runtime/Einhander_Recompiled.exe", EXE["sha256"])
        rec["card1"] = copy_x(CARD1["path"], f"{pilot}/state/card1.mcd", CARD1["sha256"])
        patched, rep = patch_settings(raw, pilot)
        rec["settings"] = dict(sha256=write_x(f"{pilot}/runtime/settings.toml", patched), base_sha256=SETTINGS["sha256"], **rep)
        entries = walk_cache()
        if [e[0] for e in entries] != [m["rel"] for m in man] or len(man) != EXPECTED_CACHE_FILES:
            raise RuntimeError("v68 cache tree differs from the qualified manifest (names/count)")
        for (rel, src), m in zip(entries, man):
            dst = os.path.join(f"{pilot}/runtime/cache", rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if not inside(dst, pilot + "/runtime/cache"):
                raise RuntimeError(f"cache destination escaped: {dst}")
            copy_x(src, dst, m["sha256"])
        rec["cache"] = dict(mode="copy", files=len(man), bytes=sum(m["size"] for m in man), manifest_sha256=man_sha)
        hd = sorted(os.listdir(f"{pilot}/hdroot"))
        rec["hdroot_check"] = dict(files=hd, only_key_png=hd == [f"{KEY}.png"], hashes_ini_in_root=os.path.lexists(f"{pilot}/hdroot/Hashes.ini"),
                                   hashes_ini_in_parent=os.path.lexists(f"{pilot}/Hashes.ini"), exact_regions=os.path.lexists(f"{pilot}/hdroot/ExactRegions.tsv"))
        rec["inherited_settings_paths"] = inherited_paths(raw)
        rec["launch_plan"] = dict(exe=f"{pilot}/runtime/Einhander_Recompiled.exe", settings=f"{pilot}/runtime/settings.toml",
                                  hd_root=f"{pilot}/hdroot", proof_log_env=dict(PSXRECOMP_HD_PROOF_LOG=f"{pilot}/logs/hd-proof.jsonl"),
                                  proof_log_exists_now=os.path.lexists(f"{pilot}/logs/hd-proof.jsonl"),
                                  note="all launch paths are inside the new pilot tree; do not set a different PSXRECOMP_HD_TEXTURE_ROOT; route = codex AQ-01 (historical frames 40717..41099 are targets, not a replay identity)")
        ok = (rec["hdroot_check"]["only_key_png"] and not rec["hdroot_check"]["hashes_ini_in_root"] and not rec["hdroot_check"]["hashes_ini_in_parent"]
              and not rec["hdroot_check"]["exact_regions"] and not rec["launch_plan"]["proof_log_exists_now"])
    except Exception as e:
        import traceback
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc()[-2000:]
    return finish(pilot, rec, ok, t0, "PILOT-STAGE.json")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
