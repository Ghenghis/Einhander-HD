"""Evidence-led development operations for the local Einhander bridge.

The native protocol writes one byte at a time. This layer never truncates a
value, records every mutation, and reads it back. Addresses without adequate
evidence remain in the research catalog rather than becoming cheat buttons.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import threading
import time
import uuid

from material_profiles import MaterialProfiles


FIELDS = [
    dict(id="lives", label="Remaining lives", category="player", address="0x800813C4", width=1,
         min=0, max=99, default=9, evidence="verified_ram", lockable=True,
         source="docs/DEBUG_FINDINGS.md: Runtime RAM access", note="RAM read/write verified; a locked life after death still requires gameplay proof."),
    dict(id="invincibility", label="Invulnerability countdown", category="player", address="0x80085718", width=1,
         min=0, max=255, default=165, evidence="verified_ram", lockable=True,
         source="docs/DEBUG_FINDINGS.md: Runtime RAM access", note="Countdown decrements about 30 times/second. A one-shot value expires; a bounded hold rewrites it."),
    dict(id="hyper", label="Hyper mode flag", category="player", address="0x80085709", width=1,
         min=0, max=255, default=255, evidence="documented", lockable=False,
         source="docs/MODS_AND_TOOLS.md: Decoded addresses", note="Legacy documented mapping; game behavior has not been independently validated."),
    dict(id="score_multiplier", label="Score multiplier", category="player", address="0x80081326", width=1,
         min=0, max=40, default=40, evidence="documented", lockable=False,
         source="docs/MODS_AND_TOOLS.md: Decoded addresses", note="Conservative single-byte operation. Wider interpretation remains unverified."),
    dict(id="hits", label="Hits counter", category="player", address="0x80085710", width=1,
         min=0, max=255, default=99, evidence="documented", lockable=False,
         source="docs/MODS_AND_TOOLS.md: Decoded addresses", note="The source table says u8; the previous bridge comment incorrectly said u32."),
    dict(id="ammo", label="Active gunpod ammunition", category="weapons", address="0x80084832", width=2,
         min=0, max=65535, default=999, evidence="documented", lockable=False,
         source="docs/MODS_AND_TOOLS.md and remaster-audit/capture_stage1.py", note="Little-endian u16, written as two explicit bytes. Does not select a gun or prevent equipment loss."),
    dict(id="ammo_counter", label="Ammunition counter", category="weapons", address="0x80084834", width=2,
         min=0, max=65535, default=999, evidence="documented", lockable=False,
         source="docs/MODS_AND_TOOLS.md and remaster-audit/capture_stage1.py", note="Little-endian u16. The displayed quantity and pickup behavior still require a controlled gameplay test."),
]
for _field in FIELDS:
    _field["writable"] = True
FIELD_MAP = {f["id"]: f for f in FIELDS}

RESEARCH = [
    dict(id="gun_durability_top", label="Upper gunpod durability", category="weapons", address="0x80084830", status="research_required", reason="Legacy table suggests u16 0x03C0; entity lifetime and protection behavior are unverified."),
    dict(id="gun_durability_bottom", label="Lower gunpod durability", category="weapons", address="0x80084980", status="research_required", reason="Legacy table suggests u16 0x03C0; do not freeze until the owning gunpod is identified."),
    dict(id="gun_integrity", label="Secondary gunpod integrity", category="weapons", address="0x80084B62 / 0x80084CB2", status="research_required", reason="Width and top/bottom ownership require controlled pickup and damage captures."),
    dict(id="weapon_slots", label="Gun type, slot count and equipment retention", category="weapons", status="research_required", reason="No validated gun identity, equip function, slot ownership or drop flag. An ammo hold cannot lock equipment."),
    dict(id="pickup_timer", label="Pickup timer / infinite pickup lifetime", category="weapons", status="research_required", reason="No validated pickup object or lifetime offset."),
    dict(id="stage_select", label="Mission and stage selection", category="stages", address="0x800ADA40–0x800ADA53", status="research_required", reason="A previous direct RAM shortcut produced a black display. Native progression or validated checkpoints are required."),
    dict(id="boss_select", label="Boss practice and checkpoints", category="stages", status="research_required", reason="Boss identity, spawn dependencies and reliable savestate restore are not validated."),
    dict(id="enemy_shields", label="Enemy and boss shields / health", category="stages", status="research_required", reason="No validated entity pool, ownership, health or shield offsets."),
    dict(id="ship_skins", label="Named ship and weapon skin assignment", category="skins", status="research_required", reason="Texture replacement works, but semantic ship / gun / effect key mapping is incomplete. Templates remain uninstalled candidates."),
]

STYLES = [dict(id="stock", label="Stock restoration"), dict(id="us-olive", label="US olive / stencil concept"),
          dict(id="arctic", label="Arctic camouflage concept"), dict(id="desert", label="Desert camouflage concept"),
          dict(id="enemy-industrial", label="Enemy industrial insignia concept")]


def integer(value, label="value"):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 16 if value.lower().startswith("0x") else 10)
        except ValueError:
            pass
    raise ValueError(f"{label} must be an integer or a 0x-prefixed hexadecimal value")


def scoped_path(root: Path, relative: str) -> Path:
    """Resolve including symlinks; sibling paths sharing a prefix are forbidden."""
    root = root.resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Path must remain inside the requested workspace")
    return target


class DevTools:
    def __init__(self, root, command, clock=time.monotonic):
        self.root = Path(root).resolve()
        self.command = command
        self.clock = clock
        self.mutex = threading.RLock()
        self.history = []
        self.locks = {}
        self.last_stop_reason = "No holds armed."
        self.last_frame = None
        self.skin_root = self.root / "skin-workspace"
        self.skin_mutex = threading.RLock()
        self._source_assets_cache = None
        self._source_assets_stamp = None
        self.evidence_root = self.root.parent / "remaster-audit" / "dev-center-evidence"
        self._quit = threading.Event()
        self.thread = None
        self.material_profiles = MaterialProfiles(self.root, self.source_assets, command=self.command)

    def catalog(self):
        return dict(ok=True, title="Einhander Development Center", disc="SCUS-94243", fields=FIELDS,
                    research=RESEARCH, milestones=[
                        dict(id="foundation", label="Correct protocol and reversible controls", status="implemented"),
                        dict(id="proof", label="Windowed native / HD visual proof", status="evidence_report"),
                        dict(id="mapping", label="Map guns, shields, stage and boss dependencies", status="research_required"),
                        dict(id="skins", label="Review mapped skin candidates in game", status="research_required")],
                    lock_policy="Lives and invulnerability only; 5–300 second leases; stop on disconnect, frame reset, implausible lives, transitions through this bridge, or emergency release. Scene identity is not validated: release before changing scenes elsewhere.")

    def _read(self, field):
        reply = self.command(dict(cmd="read_ram", addr=field["address"], len=field["width"]), timeout=1.5)
        if not reply.get("ok"):
            raise RuntimeError(reply.get("error", "RAM read failed"))
        raw = reply.get("hex", reply.get("data", ""))
        try:
            data = bytes.fromhex(raw)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Malformed RAM response") from exc
        if len(data) != field["width"]:
            raise RuntimeError("RAM response width does not match request")
        return int.from_bytes(data, "little")

    def _bytes(self, field, value):
        address = int(field["address"], 16)
        completed = 0
        for offset, byte in enumerate(value.to_bytes(field["width"], "little")):
            reply = self.command(dict(cmd="write_ram", addr=f"0x{address + offset:08X}", val=f"0x{byte:02X}"), timeout=1.5)
            if not reply.get("ok"):
                raise RuntimeError(f"Write failed after {completed}/{field['width']} bytes: " + reply.get("error", "unknown error"))
            completed += 1

    def write(self, request):
        field = FIELD_MAP.get(request.get("field"))
        if field is None:
            raise ValueError("Unknown or research-only field; use a catalog field id")
        value = integer(request.get("value"))
        if not field["min"] <= value <= field["max"]:
            raise ValueError(f"{field['label']} must be between {field['min']} and {field['max']}")
        with self.mutex:
            if field["id"] in self.locks:
                raise ValueError("Release this field's hold before a one-shot write")
            return self._write_record(field, value)

    def _write_record(self, field, value):
        before = self._read(field)
        record = dict(id=uuid.uuid4().hex[:12], field=field["id"], label=field["label"],
                      before=before, after=value, at=time.time(), verified=False, undone=False)
        self.history.insert(0, record)
        self.history = self.history[:100]
        try:
            self._bytes(field, value)
            actual = self._read(field)
            record.update(readback=actual, verified=actual == value)
            if actual != value:
                record["note"] = "The game may update a live countdown between write and readback; exact equality was not observed."
            return dict(ok=record["verified"], operation=dict(record), error=None if record["verified"] else "Readback differed from requested value")
        except RuntimeError as exc:
            record["error"] = str(exc)
            # A multi-byte write may be partial. Restore immediately only if the
            # connection still accepts writes; preserve the error in history.
            try:
                self._bytes(field, before)
                record["rollback_verified"] = self._read(field) == before
            except RuntimeError:
                record["rollback_verified"] = False
            return dict(ok=False, operation=dict(record), error=str(exc))

    def undo(self, request):
        with self.mutex:
            record = next((r for r in self.history if not r["undone"] and (not request.get("id") or r["id"] == request["id"])), None)
            if record is None:
                raise ValueError("No matching operation to undo")
            field = FIELD_MAP[record["field"]]
            if field["id"] in self.locks:
                raise ValueError("Release the active hold before undo")
            actual = self._read(field)
            if actual != record["after"]:
                raise ValueError("Value changed since the write; undo would overwrite newer game state")
            self._bytes(field, record["before"])
            verified = self._read(field) == record["before"]
            record["undone"] = verified
            return dict(ok=verified, operation=dict(record))

    def lock(self, request):
        field = FIELD_MAP.get(request.get("field"))
        if field is None or not field["lockable"]:
            raise ValueError("Only verified lives and invulnerability mappings support bounded holds")
        with self.mutex:
            if request.get("enabled") is False:
                removed = self.locks.pop(field["id"], None)
                # Do not restore an old countdown/life after combat. Releasing
                # stops rewriting and lets the game own the current value.
                return dict(ok=True, released=bool(removed), note="Rewrites stopped; prior combat state is not restored.")
            value = integer(request.get("value"))
            ttl = integer(request.get("ttl_seconds", 60), "ttl_seconds")
            if not field["min"] <= value <= field["max"] or not 5 <= ttl <= 300:
                raise ValueError("Value is out of range or lease is outside 5–300 seconds")
            if field["id"] == "lives" and value == 0:
                raise ValueError("A lives hold must keep at least one life")
            lives = self._read(FIELD_MAP["lives"])
            if not 1 <= lives <= 99:
                raise ValueError("Holds require plausible live player state (1–99 lives)")
            probe = self.command(dict(cmd="gpu_state"), timeout=1.5)
            if not probe.get("ok"):
                raise RuntimeError(probe.get("error", "Game is unavailable"))
            frame = probe.get("ws", {}).get("cur_frame")
            if not isinstance(frame, int):
                raise ValueError("This server does not expose a frame counter; restart guards are unavailable")
            result = self._write_record(field, value)
            if result["ok"] or field["id"] == "invincibility" and result.get("operation", {}).get("readback", -1) in range(max(0, value-8), value+1):
                self.last_frame = frame
                self.locks[field["id"]] = dict(field=field["id"], value=value, expires=self.clock() + ttl,
                                              status="armed", original=result["operation"]["before"])
                self.last_stop_reason = ""
                return dict(ok=True, lock=self._public_lock(self.locks[field["id"]]), operation=result["operation"])
            return result

    def stop(self, reason="Emergency release"):
        with self.mutex:
            count = len(self.locks)
            self.locks.clear()
            self.last_stop_reason = reason
            return dict(ok=True, released=count, reason=reason)

    def _public_lock(self, item):
        return dict(field=item["field"], value=item["value"], status=item["status"],
                    expires_in=max(0, round(item["expires"] - self.clock(), 1)))

    def tick(self):
        with self.mutex:
            for key in list(self.locks):
                if self.locks[key]["expires"] <= self.clock():
                    del self.locks[key]
                    self.last_stop_reason = "Hold lease expired."
            if not self.locks:
                return
            try:
                probe = self.command(dict(cmd="gpu_state"), timeout=1.5)
                if not probe.get("ok"):
                    raise RuntimeError("Game disconnected; holds disarmed.")
                frame = probe.get("ws", {}).get("cur_frame")
                if frame is not None and self.last_frame is not None and frame < self.last_frame:
                    raise RuntimeError("Frame counter reset; holds disarmed.")
                self.last_frame = frame
                lives = self._read(FIELD_MAP["lives"])
                if not 1 <= lives <= 99:
                    raise RuntimeError("Player state changed; holds disarmed.")
                for item in self.locks.values():
                    self._bytes(FIELD_MAP[item["field"]], item["value"])
            except RuntimeError as exc:
                self.stop(str(exc))

    def start(self):
        def run():
            while not self._quit.wait(0.15):
                self.tick()
        self.thread = threading.Thread(target=run, name="devtools-holds", daemon=True)
        self.thread.start()

    def status(self):
        game = self.command(dict(cmd="gpu_state"), timeout=1.5)
        values = {}
        if game.get("ok"):
            for field in FIELDS:
                try:
                    value = self._read(field)
                    values[field["id"]] = dict(ok=True, value=value, hex=f"0x{value:0{field['width']*2}X}", address=field["address"], width=field["width"])
                except RuntimeError as exc:
                    values[field["id"]] = dict(ok=False, error=str(exc))
        with self.mutex:
            return dict(ok=True, connected=bool(game.get("ok")), game=game, values=values,
                        locks=[self._public_lock(item) for item in self.locks.values()],
                        history=[dict(item) for item in self.history[:20]], last_stop_reason=self.last_stop_reason)

    def evidence(self):
        target = self.evidence_root / "summary.json"
        if not target.is_file():
            return dict(ok=True, available=False, captures=[], limitations=["Fresh evidence report is being prepared; no current proof is claimed."])
        result = json.loads(target.read_text(encoding="utf-8-sig"))
        result.update(ok=True, available=True)
        images = list(result.get("captures", []))
        for comparison in result.get("texture_comparisons", []):
            images.extend(comparison.get("images", []))
        for capture in images:
            if capture.get("relative_path"):
                from urllib.parse import quote
                capture["url"] = "/dev/evidence/files/" + quote(capture["relative_path"].replace("\\", "/"))
        return result

    def _source_pack(self):
        path = self.root / "hd-textures" / "stage1-v1" / "manifest.json"
        if not path.is_file():
            return dict(available=False, count=0)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        files = manifest.get("files", [])
        return dict(available=True, path=str(path.parent), version=manifest.get("version"), count=len(files),
                    neural_count=sum(bool(item.get("neural_detail")) for item in files), scope=manifest.get("scope"))

    def source_assets(self):
        """Read small PNG headers; do not decode 964 large textures for a menu."""
        manifest_path = self.root / "hd-textures" / "stage1-v1" / "manifest.json"
        if not manifest_path.is_file():
            return []
        stamp = manifest_path.stat().st_mtime_ns
        with self.skin_mutex:
            if stamp == self._source_assets_stamp and self._source_assets_cache is not None:
                return self._source_assets_cache
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            assets = []
            for row in manifest.get("files", []):
                key = row.get("key", "")
                if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{3,160}", key):
                    continue
                path = scoped_path(manifest_path.parent / "einhander-texture-replacements", key + ".png")
                try:
                    with path.open("rb") as stream:
                        header = stream.read(24)
                    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
                        continue
                    width, height = struct.unpack(">II", header[16:24])
                except (OSError, struct.error):
                    continue
                assets.append(dict(key=key, width=width, height=height, method=row.get("method"),
                                   neural_detail=bool(row.get("neural_detail")), sha256=row.get("sha256"),
                                   semantic_mapping="unverified", url="/dev/skins/source/" + key + ".png"))
            self._source_assets_cache = assets
            self._source_assets_stamp = stamp
            return assets

    def source_image(self, filename):
        if not isinstance(filename, str) or not filename.endswith(".png"):
            raise ValueError("Source preview must be a known PNG identity")
        key = filename[:-4]
        if key not in {asset["key"] for asset in self.source_assets()}:
            raise ValueError("Source preview is absent from the installed manifest")
        return scoped_path(self.root / "hd-textures" / "stage1-v1" / "einhander-texture-replacements", filename)

    def styles(self):
        """Merge generated art directions without treating concepts as UV art."""
        styles = [dict(style) for style in STYLES]
        collection = self.root / "tools" / "skin_collection" / "collection.json"
        if not collection.is_file():
            return styles
        try:
            if collection.stat().st_size > 1024 * 1024:
                return styles
            data = json.loads(collection.read_text(encoding="utf-8-sig"))
            seen = {style["id"] for style in styles}
            for item in data.get("skins", []):
                identity = item.get("id", "")
                if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", identity) or identity in seen:
                    continue
                # Collection artwork is local and must resolve to its named PNG.
                image = "/files/tools/skin_collection/" + identity + ".png"
                if item.get("image") != image:
                    continue
                concept = dict(id=identity, name=str(item.get("name", identity))[:120],
                               role=str(item.get("role", "ship"))[:40], image=image,
                               width=item.get("width"), height=item.get("height"),
                               sha256=item.get("sha256"), description=str(item.get("description", ""))[:1200],
                               palette=[color for color in item.get("palette", []) if isinstance(color, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", color)],
                               status="concept_unmapped", in_game=False)
                styles.append(dict(id=identity, label=concept["name"], kind="generated_concept", concept_art=concept))
                seen.add(identity)
        except (OSError, ValueError, TypeError, AttributeError):
            # Draft workspaces remain accessible while a producer writes a new
            # collection manifest. Incomplete art cannot become an active style.
            pass
        return styles

    def _style_snapshot(self, identity):
        selected = next((style for style in self.styles() if style["id"] == identity), None)
        if selected is None:
            raise ValueError("Unknown skin style")
        concept = selected.get("concept_art")
        if concept:
            source = scoped_path(self.root / "tools" / "skin_collection", concept["id"] + ".png")
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != concept.get("sha256"):
                raise ValueError("Concept artwork is missing or does not match the collection SHA256")
            with source.open("rb") as stream:
                header = stream.read(24)
            if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
                raise ValueError("Concept artwork is not a supported PNG")
            if struct.unpack(">II", header[16:24]) != (concept["width"], concept["height"]):
                raise ValueError("Concept dimensions do not match the source PNG")
        return selected

    def skins(self):
        with self.skin_mutex:
            return self._skins()

    def _skins(self):
        packs = []
        if self.skin_root.is_dir():
            for path in sorted(self.skin_root.glob("*/skin.json")):
                try:
                    record = json.loads(path.read_text(encoding="utf-8"))
                    record["path"] = str(path.parent)
                    packs.append(record)
                except (OSError, ValueError):
                    pass
        return dict(ok=True, styles=self.styles(), packs=packs, source_pack=self._source_pack(), source_assets=self.source_assets(),
                    import_policy=dict(max_encoded_bytes=24*1024*1024, dimensions="exact", alpha="exact source alpha bytes", activation="draft_only"),
                    notes=["Skin workspaces are candidates; creating one does not generate art or activate a pack.",
                           "Preserve exact replacement keys, dimensions and alpha bytes. Verify named asset ownership and compare fixed-frame captures before activation.",
                           "Renderer caches require a game restart after replacing files. Stock pack remains untouched."])

    def skin_action(self, request):
        with self.skin_mutex:
            return self._skin_action(request)

    def _skin_action(self, request):
        name = request.get("name", "")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", name):
            raise ValueError("Use a 1–48 character workspace name containing letters, digits, - or _")
        target = scoped_path(self.skin_root, name)
        action = request.get("action", "create")
        if action == "create":
            style = request.get("style", "stock")
            selected = self._style_snapshot(style)
            target.mkdir(parents=True, exist_ok=False)
            (target / "einhander-texture-replacements").mkdir()
            manifest = dict(name=name, style=style, version=1, status="draft_uninstalled", created_at=time.time(),
                            target_disc="SCUS-94243", source_pack="stage1-v1", assets=[],
                            review=dict(semantic_mapping=False, alpha_classes=False, in_game=False))
            if selected.get("concept_art"):
                manifest["concept_art"] = selected["concept_art"]
            (target / "skin.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            (target / "README.txt").write_text("SKIN CANDIDATE — NOT INSTALLED\n\nMap a stock hash to an observed ship, gun or effect before editing.\nImport an edited PNG using the local API action import with key and png_base64.\nThe importer requires identical dimensions and exact source alpha bytes.\nReview RGB changes, palettes and animated effects in game at 1440p and 4K.\nThis workspace never writes to the installed stock pack.\n", encoding="utf-8")
            return dict(ok=True, manifest=manifest, path=str(target), note="Draft workspace created; art generation and semantic mapping are still required.")
        if action == "import":
            return self._import_skin(target, request)
        if action == "inspect":
            return dict(ok=True, manifest=json.loads((target / "skin.json").read_text(encoding="utf-8")), path=str(target))
        if action == "set-style":
            selected = self._style_snapshot(request.get("style"))
            manifest_path = target / "skin.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["style"] = selected["id"]
            manifest.pop("concept_art", None)
            if selected.get("concept_art"):
                manifest["concept_art"] = selected["concept_art"]
            manifest["style_updated_at"] = time.time()
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            return dict(ok=True, manifest=manifest, note="Art direction saved as draft metadata; replacement assets and game activation are unchanged.")
        raise ValueError("Use create, import, inspect or set-style")

    def _import_skin(self, target, request):
        # Import is scoped to a draft workspace and existing installed identities.
        # Pillow is optional: inspection/create remain usable without it.
        try:
            from PIL import Image
        except ImportError as exc:
            raise ValueError("PNG validation requires the project's Pillow environment") from exc
        key = request.get("key", "")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{3,160}", key):
            raise ValueError("Invalid replacement identity")
        source = scoped_path(self.root / "hd-textures" / "stage1-v1" / "einhander-texture-replacements", key + ".png")
        if not source.is_file():
            raise ValueError("Key is absent from the installed source pack")
        source_asset = next((item for item in self.source_assets() if item["key"] == key), None)
        if source_asset is None:
            raise ValueError("Key is absent from the installed manifest")
        source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
        if source_sha != source_asset.get("sha256"):
            raise ValueError("Installed source PNG no longer matches its recorded SHA256")
        encoded = request.get("png_base64", "")
        if not isinstance(encoded, str) or len(encoded) > 24 * 1024 * 1024:
            raise ValueError("PNG must be base64 with at most 24 MiB encoded data")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid base64 PNG") from exc
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Only PNG files can be imported")
        if len(data) < 24 or data[12:16] != b"IHDR" or struct.unpack(">II", data[16:24]) != (source_asset["width"], source_asset["height"]):
            raise ValueError("PNG header dimensions must exactly match the installed source")
        manifest_path = target / "skin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        with Image.open(source) as original, Image.open(io.BytesIO(data)) as edited:
            if original.size != edited.size or edited.format != "PNG":
                raise ValueError("Dimensions must exactly match the installed source PNG")
            before = original.convert("RGBA").getchannel("A").tobytes()
            after = edited.convert("RGBA").getchannel("A").tobytes()
            # Renderer STP boundary is alpha >= 0.5. Treating all intermediate
            # values alike would accept a destructive 64 -> 128 class change.
            # Match the existing pack verifier: every alpha byte stays exact.
            if before != after:
                raise ValueError("Source alpha bytes changed; transparency / STP classes must remain exact")
            dimensions = list(edited.size)
        destination = scoped_path(target, "einhander-texture-replacements/" + key + ".png")
        if destination.exists():
            raise ValueError("This identity is already imported; create a new workspace for another revision")
        with destination.open("xb") as output:
            output.write(data)
        manifest["assets"].append(dict(key=key, sha256=hashlib.sha256(data).hexdigest(),
                                       source_sha256=source_sha,
                                       dimensions=dimensions, alpha_classes=True, alpha_exact=True, semantic_mapping=False, in_game=False))
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return dict(ok=True, manifest=manifest, note="PNG imported and class-checked. Semantic ownership and in-game appearance are unverified; candidate remains uninstalled.")
