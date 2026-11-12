"""Stage key-scoped GL material profiles without copying or altering the HD pack."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct
import threading
import time
import uuid

CONTRACT = "ein-material-v3"
DEFAULT_STRENGTH = 0.75
FIGHTER_KEY = "5CC44E5F-053D9A00"
PLAYER_KEYS = (FIGHTER_KEY, "724E77DA-21FDE894", "7E3ADD56-21FDE894", "B16492B1-21FDE894", "E2F3477C-21FDE894")
# The mechanical sheet has mixed/unpartitioned ownership. Keep it supported
# for explicit experiments but outside the default hull-only selection.
DEFAULT_PLAYER_KEYS = PLAYER_KEYS[1:]
ENEMY_KEYS = ("3594C110-527B28B9", "3FE0776D-527B28B9", "6BB2A2A3-527B28B9", "784BFD39-527B28B9", "DEA9D15C-527B28B9", "05C32A1E-527B28B9")
ALLOWED_KEYS = set(PLAYER_KEYS)
DETAIL_IDS = ("gold-obsidian-engraved", "titanium-teal-nanoceramic", "crimson-gold-plating", "neon-circuit-tracery", "ultraviolet-plasma-grid", "reactor-lime-hazard")
DETAIL_STRENGTH = 0.12
DETAIL_SCALE = 8.

# Primary/accent mirror hd_skin_material.h. Recess is visual direction metadata;
# the runtime preserves neutral metal using the original saturation mask.
_COLORS = [
    ("aurora-teal", "Aurora Vector", "player", "#16E6CD", "#53F6FF", "#102A34"),
    ("solar-orange", "Solar Flare", "player", "#FF6A13", "#FFBE37", "#261912"),
    ("ultraviolet-violet", "Ultraviolet Phantom", "enemy", "#9B43FF", "#EF50FF", "#190E35"),
    ("glacier-blue", "Glacier Strike", "player", "#3D9EFF", "#A5F4FF", "#15283D"),
    ("crimson-red", "Crimson Reaver", "enemy", "#E51A37", "#FF5C51", "#290A16"),
    ("toxic-lime", "Toxic Viper", "enemy", "#B7FF16", "#4FE36A", "#152B18"),
    ("gold-obsidian", "Obsidian Sovereign", "enemy", "#F3BD4A", "#FFE7A0", "#12151B"),
    ("pearl-magenta", "Pearlescent Mirage", "player", "#F2F4FF", "#FF4AC5", "#B7A9FA"),
    ("aurora-gilt", "Aurora Gilt", "player", "#16E6CD", "#F3BD4A", "#102A34"),
    ("crimson-regalia", "Crimson Regalia", "enemy", "#E51A37", "#FFD16A", "#290A16"),
    ("glacier-gilt", "Glacier Gilt", "player", "#3D9EFF", "#E8C46A", "#15283D"),
    ("neon-circuit", "Neon Circuit", "player", "#00F0FF", "#FF32D2", "#101426"),
    ("ultraviolet-grid", "Ultraviolet Grid", "enemy", "#8426FF", "#38F6FF", "#160D2F"),
    ("reactor-lime", "Reactor Lime", "enemy", "#B6FF00", "#F8FF59", "#19220B"),
]


def rgb(color):
    return [int(color[offset:offset+2], 16) / 255 for offset in (1, 3, 5)]


PROFILES = [dict(id="stock", label="Stock material", role="stock", primary="#FFFFFF", accent="#FFFFFF", recess="#171D27", primary_rgb=[1., 1., 1.], accent_rgb=[1., 1., 1.], strength_default=0.)]
PROFILES += [dict(id=identity, label=label, role=role, primary=primary, accent=accent, recess=recess,
                  primary_rgb=rgb(primary), accent_rgb=rgb(accent), strength_default=DEFAULT_STRENGTH)
             for identity, label, role, primary, accent, recess in _COLORS]
PROFILE_MAP = {profile["id"]: profile for profile in PROFILES}
for _profile in PROFILES:
    _profile["category"] = ("Stock" if _profile["id"] == "stock" else "Gold" if _profile["id"] in ("gold-obsidian", "aurora-gilt", "crimson-regalia", "glacier-gilt")
                            else "Neon-Cyberpunk" if _profile["id"] in ("neon-circuit", "ultraviolet-grid", "reactor-lime") else "Vibrant-Elemental")


def within(root, relative):
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Material files must remain inside this project")
    return target


def selection(request):
    identity = request.get("profile", "stock")
    if not isinstance(identity, str) or identity not in PROFILE_MAP:
        raise ValueError("Unknown material profile")
    strength = request.get("strength", PROFILE_MAP[identity]["strength_default"])
    if isinstance(strength, bool):
        raise ValueError("Material strength must be a finite number from 0 to 1")
    try:
        strength = float(strength)
    except (TypeError, ValueError) as exc:
        raise ValueError("Material strength must be a finite number from 0 to 1") from exc
    if not math.isfinite(strength) or not 0 <= strength <= 1:
        raise ValueError("Material strength must be a finite number from 0 to 1")
    targets = request.get("targets", list(DEFAULT_PLAYER_KEYS))
    if not isinstance(targets, list) or not 1 <= len(targets) <= len(ALLOWED_KEYS) or any(not isinstance(key, str) or key not in ALLOWED_KEYS for key in targets):
        raise ValueError("Player targets must be mapped fighter atlas identities from the material catalog")
    if len(set(targets)) != len(targets):
        raise ValueError("Material target identities must be unique")
    return identity, strength, targets


def enemy_selection(request):
    identity = request.get("enemy_profile", "stock")
    if not isinstance(identity, str) or identity not in PROFILE_MAP:
        raise ValueError("Unknown enemy material profile")
    strength = request.get("enemy_strength", PROFILE_MAP[identity]["strength_default"])
    if isinstance(strength, bool):
        raise ValueError("Enemy strength must be a finite number from 0 to 1")
    try:
        strength = float(strength)
    except (TypeError, ValueError) as exc:
        raise ValueError("Enemy strength must be a finite number from 0 to 1") from exc
    if not math.isfinite(strength) or not 0 <= strength <= 1:
        raise ValueError("Enemy strength must be a finite number from 0 to 1")
    targets = request.get("enemy_targets", list(ENEMY_KEYS))
    if not isinstance(targets, list) or not 1 <= len(targets) <= len(ENEMY_KEYS) or any(not isinstance(key, str) or key not in ENEMY_KEYS for key in targets):
        raise ValueError("Enemy targets must be observed green/yellow fighter atlas identities from the material catalog")
    if len(set(targets)) != len(targets):
        raise ValueError("Enemy material target identities must be unique")
    return identity, strength, targets


def detail_catalog(root):
    root = Path(root).resolve()
    manifest_path = within(root, "tools/skin_collection/materials/materials.json")
    if not manifest_path.is_file():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    maps = []
    for item in manifest.get("maps", []):
        if not isinstance(item, dict) or item.get("id") not in DETAIL_IDS:
            continue
        identity = item["id"]
        maps.append(dict(id=identity, label=item.get("label", identity), width=item.get("width"), height=item.get("height"),
                         category=item.get("category", "Neon-Cyberpunk" if identity in DETAIL_IDS[3:] else "Gold" if identity != "titanium-teal-nanoceramic" else "Vibrant-Elemental"),
                         sha256=item.get("sha256"), url="/files/tools/skin_collection/materials/" + identity + ".png",
                         image="/files/tools/skin_collection/materials/" + identity + ".png", wrap="mirrored_repeat",
                         strength_default=DETAIL_STRENGTH, scale_default=DETAIL_SCALE, native_4k=bool(item.get("native_4k")),
                         unchanged_generated_png=bool(item.get("unchanged_generated_png")), in_game_verified=False))
    return maps


def detail_selection(request, root, enemy=False):
    prefix = "enemy_" if enemy else ""
    identity = request.get(prefix + "detail_map", "none")
    if identity in (None, ""):
        identity = "none"
    if not isinstance(identity, str) or identity not in ("none",) + DETAIL_IDS:
        raise ValueError("Choose an authored detail-map identity from the material catalog")
    values = {}
    for suffix, default, minimum, maximum in (("detail_strength", DETAIL_STRENGTH, 0., 0.35), ("detail_scale", DETAIL_SCALE, 1., 64.)):
        value = request.get(prefix + suffix, default)
        if isinstance(value, bool):
            raise ValueError(prefix + suffix + f" must be a finite number from {minimum} to {maximum}")
        try:
            value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(prefix + suffix + " must be numeric") from exc
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(prefix + suffix + f" must be a finite number from {minimum} to {maximum}")
        values[suffix] = value
    result = dict(id=identity, path="", sha256=None, strength=values["detail_strength"], scale=values["detail_scale"], wrap="mirrored_repeat")
    if identity == "none":
        return result
    asset = next((item for item in detail_catalog(root) if item["id"] == identity), None)
    if asset is None:
        raise ValueError("Selected authored detail map is absent from the local asset manifest")
    path = within(root, Path("tools") / "skin_collection" / "materials" / (identity + ".png"))
    if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Detail PNG is missing or exceeds the native 64 MiB encoded limit")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != asset.get("sha256"):
        raise ValueError("Detail PNG no longer matches its recorded SHA256")
    with path.open("rb") as source:
        header = source.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("Detail map must be a valid PNG with an IHDR header")
    width, height = struct.unpack(">II", header[16:24])
    if not 1 <= width <= 4096 or not 1 <= height <= 4096 or (width, height) != (asset["width"], asset["height"]):
        raise ValueError("Detail PNG dimensions exceed 4096 or differ from the asset receipt")
    return dict(result, path=str(path), sha256=digest, width=width, height=height)


def environment(identity, strength, targets, root, enemy_identity="stock", enemy_strength=0., enemy_targets=ENEMY_KEYS, detail=None, enemy_detail=None):
    detail = detail or dict(path="", strength=DETAIL_STRENGTH, scale=DETAIL_SCALE)
    enemy_detail = enemy_detail or dict(path="", strength=DETAIL_STRENGTH, scale=DETAIL_SCALE)
    return {
        "EIN_DEV_URL": "http://127.0.0.1:8094",
        "EIN_DEBUG_PORT": "4370",
        "PSXRECOMP_SKIN_PROFILE": identity,
        "PSXRECOMP_SKIN_KEYS": ",".join(targets),
        "PSXRECOMP_SKIN_STRENGTH": format(strength, ".6f"),
        "PSXRECOMP_SKIN_ENEMY_PROFILE": enemy_identity,
        "PSXRECOMP_SKIN_ENEMY_KEYS": ",".join(enemy_targets),
        "PSXRECOMP_SKIN_ENEMY_STRENGTH": format(enemy_strength, ".6f"),
        "PSXRECOMP_SKIN_DETAIL_PATH": detail["path"],
        "PSXRECOMP_SKIN_DETAIL_STRENGTH": format(detail["strength"], ".6f"),
        "PSXRECOMP_SKIN_DETAIL_SCALE": format(detail["scale"], ".6f"),
        "PSXRECOMP_SKIN_ENEMY_DETAIL_PATH": enemy_detail["path"],
        "PSXRECOMP_SKIN_ENEMY_DETAIL_STRENGTH": format(enemy_detail["strength"], ".6f"),
        "PSXRECOMP_SKIN_ENEMY_DETAIL_SCALE": format(enemy_detail["scale"], ".6f"),
        "PSXRECOMP_HD_TEXTURE_ROOT": str(Path(root).resolve() / "hd-textures" / "stage1-v1"),
        "PSXRECOMP_HD_PAGE_FALLBACK": "1",
        "PSXRECOMP_HD_DECODE_BUDGET_MB": "256",
        "PSXRECOMP_HD_CPU_AUTHORITY": "0",
        "PSXRECOMP_HD_DUMP": "",
        "PSXRECOMP_HD_SOURCE_SIDECARS": "",
        "PSXRECOMP_HD_PROOF_LOG": "",
        "PSXRECOMP_HD_PROOF_CONTROL": "",
    }


def runtime_receipt(root, verify_hash=False, player_keys=None, enemy_keys=None, profiles=None, require_detail=False):
    path = Path(root) / "tools" / "material-runtime.json"
    result = dict(receipt_path=str(path), receipt_present=path.is_file(), ready=False)
    if not path.is_file():
        return dict(result, reason="Shader-enabled runtime build receipt is pending. No game was launched.")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if data.get("contract") != CONTRACT or data.get("material_shader") is not True:
            raise ValueError("Runtime receipt does not certify the material shader contract")
        recorded_player = data.get("player_keys", [])
        recorded_enemy = data.get("enemy_keys", [])
        supported_profiles = data.get("profiles", [])
        if profiles and not set(profiles).issubset(supported_profiles):
            raise ValueError("Runtime receipt does not certify the selected material profile identities")
        if require_detail and data.get("detail_maps") is not True:
            raise ValueError("Runtime receipt does not certify authored RGB detail-map support")
        if player_keys and not set(player_keys).issubset(recorded_player):
            raise ValueError("Runtime receipt does not certify the selected player texture identities")
        if enemy_keys and (data.get("dual_profiles") is not True or not set(enemy_keys).issubset(recorded_enemy)):
            raise ValueError("Runtime receipt does not certify independent enemy material profiles and their texture identities")
        executable = Path(data.get("executable", ""))
        if not executable.is_absolute() or not executable.is_file():
            raise ValueError("Shader-enabled executable is missing")
        digest = data.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("Runtime receipt has no valid executable SHA256")
        verified = False
        if verify_hash:
            if hashlib.sha256(executable.read_bytes()).hexdigest() != digest.lower():
                raise ValueError("Executable changed after the material build receipt was recorded")
            verified = True
        return dict(result, ready=True, executable=str(executable), sha256=digest, executable_hash_verified=verified,
                    dual_profiles=data.get("dual_profiles") is True, player_keys=recorded_player, enemy_keys=recorded_enemy,
                    profiles=supported_profiles, detail_maps=data.get("detail_maps") is True,
                    reason="Build receipt exists. In-game material validation remains pending; this API has not launched a game.")
    except (OSError, ValueError, TypeError) as exc:
        return dict(result, reason=str(exc))


def source_records(root, targets):
    root = Path(root).resolve()
    pack = root / "hd-textures" / "stage1-v1"
    path = pack / "manifest.json"
    if not path.is_file():
        raise ValueError("Installed HD source manifest is missing")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    records = []
    for key in targets:
        source = next((row for row in manifest.get("files", []) if row.get("key") == key), None)
        if source is None:
            raise ValueError("Selected texture is absent from the installed HD manifest")
        png = within(pack / "einhander-texture-replacements", key + ".png")
        if not png.is_file() or hashlib.sha256(png.read_bytes()).hexdigest() != source.get("sha256"):
            raise ValueError("Selected source PNG is missing or does not match its recorded SHA256")
        records.append(dict(key=key, sha256=source["sha256"], path=str(png)))
    return records, dict(path=str(pack), manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         entries=len(manifest.get("files", [])), all_entries_preserved=True, copied_pngs=0)


def saved_selection(root):
    """Read the saved pointer and verify its confined descriptor, without I/O to the game."""
    root = Path(root).resolve()
    result = dict(exists=False, valid=False, status="none", game_launched=False)
    try:
        pointer_path = within(root, "tools/material-selection.json")
        if not pointer_path.is_file():
            return result
        result["exists"] = True
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        if pointer.get("schema_version") != 1 or pointer.get("contract") != CONTRACT:
            raise ValueError("Saved material pointer has an unsupported schema or contract")
        relative = pointer.get("descriptor_relative")
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise ValueError("Saved descriptor must use a project-relative path")
        descriptor_path = within(root, relative)
        workspace = within(root, "tools/material-profiles")
        if not descriptor_path.is_relative_to(workspace) or descriptor_path.name != "material.json":
            raise ValueError("Saved descriptor must remain inside tools/material-profiles")
        content = descriptor_path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != pointer.get("descriptor_sha256"):
            raise ValueError("Saved descriptor changed after the preset was saved")
        descriptor = json.loads(content)
        if descriptor.get("schema_version") != 1 or descriptor.get("contract") != CONTRACT:
            raise ValueError("Saved descriptor has an unsupported schema or contract")
        identity, strength, targets = selection(descriptor)
        enemy_identity, enemy_strength, enemy_targets = enemy_selection(descriptor)
        return dict(result, valid=True, status="saved_not_launched", config_path=str(descriptor_path),
                    config_url="/files/" + descriptor_path.relative_to(root).as_posix(), descriptor_sha256=digest,
                    saved_at=pointer.get("saved_at"), profile=identity, strength=strength, targets=targets,
                    enemy_profile=enemy_identity, enemy_strength=enemy_strength, enemy_targets=enemy_targets,
                    detail_map=descriptor.get("detail_map", "none"), enemy_detail_map=descriptor.get("enemy_detail_map", "none"),
                    validation_scope="Pointer scope and descriptor integrity verified; all asset hashes are checked again by the manual launcher")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return dict(result, status="invalid_saved_pointer", error=str(exc))


class MaterialProfiles:
    def __init__(self, root, source_assets, command=None):
        self.root = Path(root).resolve()
        self.source_assets = source_assets
        self.command = command
        self.save_lock = threading.Lock()
        self.last_live_ack = None

    def catalog(self):
        available = {asset["key"]: asset for asset in self.source_assets()}
        targets = []
        for group, keys in (("player", DEFAULT_PLAYER_KEYS + (FIGHTER_KEY,)), ("enemy", ENEMY_KEYS)):
            for index, key in enumerate(keys):
                target = dict(available.get(key, {}))
                mechanical = key == FIGHTER_KEY
                label = "Shared mechanical atlas / unpartitioned ownership" if mechanical else ("Observed blue fighter hull atlas" if group == "player" else "Observed green/yellow enemy fighter atlas")
                target.update(key=key, label=label + f" · {index + 1}", role=group, group=group,
                              native_width=64 if group == "player" else 256, native_height=64 if group == "player" else 8,
                              category="shared_mechanical" if mechanical else "hull" if group == "player" else "enemy_hull_atlas",
                              slot="unpartitioned" if mechanical else "hull_surface" if group == "player" else "unpartitioned_enemy_surface",
                              default_selected=not mechanical, independent_weapon_slot=False, craft_id=None, hardpoint_id=None,
                              component_isolation_verified=False,
                              ownership_note="Mixed mechanical panels; hull versus gun ownership is unpartitioned" if mechanical else "Observed on one starter craft; built-in gun versus hull UV separation is unproven" if group == "player" else "Observed green/yellow enemy atlas family; per-part and entity-instance isolation are unproven",
                              available=key in available, semantic_mapping="observed_source_atlas",
                              evidence="remaster-audit/dev-center-evidence/skin-mapping.json",
                              scope="Exact upload texture + palette identity only. Cross-stage entity exclusivity is unverified; shared pixels retain source ownership.")
                targets.append(target)
        return dict(ok=True, contract=CONTRACT, profiles=PROFILES, default_profile="stock", strength_default=DEFAULT_STRENGTH,
                    profile_categories=["Gold", "Neon-Cyberpunk", "Vibrant-Elemental"],
                    saved_selection=saved_selection(self.root),
                    live_supported=dict(command="skin_material", bridge_available=self.command is not None, color_only=True,
                                        engine_polled=False, profiles=list(PROFILE_MAP), strength_percent_min=0, strength_percent_max=100,
                                        target_scope="Existing runtime key subsets stay unchanged", detail_layers="Unchanged by live color apply",
                                        restart_required_for=["detail_map", "enemy_detail_map", "detail_strength", "enemy_detail_strength", "detail_scale", "enemy_detail_scale", "targets", "enemy_targets"]),
                    targets=targets, player_keys=list(PLAYER_KEYS), default_player_keys=list(DEFAULT_PLAYER_KEYS), enemy_keys=list(ENEMY_KEYS), default_enemy_profile="stock",
                    runtime=runtime_receipt(self.root, profiles=[identity for identity in PROFILE_MAP if identity != "stock"], require_detail=True),
                    detail_maps=detail_catalog(self.root), default_detail_map="none",
                    detail_policy=dict(strength_default=DETAIL_STRENGTH, strength_min=0., strength_max=0.35, scale_default=DETAIL_SCALE,
                                       scale_min=1., scale_max=64., wrap="mirrored_repeat", max_dimension=4096, max_encoded_bytes=64*1024*1024,
                                       rgb_only=True, alpha_source="original game texture", uv_basis="native atlas pixel coordinates / 64 * scale", no_layer_by_default=True),
                    component_support=dict(hull=dict(selectable=True, scope="Observed blue fighter hull atlas family; individual playable craft and UV-island exclusivity remain unverified"),
                                           built_in_gun=dict(selectable=False, reason="No independently verified built-in gun atlas ownership or hardpoint mapping"),
                                           pickup_gunpod=dict(selectable=False, reason="No independently verified pickup Gunpod atlas ownership or per-weapon mapping"),
                                           shared_mechanical=dict(selectable=True, default_selected=False, reason="Explicit-only mixed mechanical atlas; not an independent gun or hull component")),
                    shader_source="psxrecomp/runtime/src/hd_skin_material.h", status="staging_available_gameplay_unverified",
                    limitations=["Staging writes configuration and a manual launcher; it never starts or changes a running game.",
                                 "Material palettes recolor matched surface pixels. They do not install the generated concept geometry, markings or gun models.",
                                 "The complete installed HD pack remains referenced; no replacement PNG is copied or overwritten.",
                                 "Four observed blue fighter hull atlas identities are selected by default. The mixed mechanical atlas is supported only by explicit target selection and remains stock by default.",
                                 "Playable-craft identity, built-in guns and pickup Gunpods are not independently mapped. A shared atlas must not be presented as an independently selectable equipment slot.",
                                 "Six observed green/yellow enemy fighter identities are allowlisted. Other enemies, bosses and effects are not covered; cross-stage exclusivity remains unverified.",
                                 "GL material RGB changes preserve source alpha and STP classification. Native gameplay validation is still required.",
                                 "Authored detail maps are RGB-only surface modulation, not depth, normals, roughness or PBR. Mirrored-repeat sampling makes generated borders continuous without editing the PNGs.",
                                 "Detail maps are off by default and may be selected with stock colors. Their measured source dimensions do not constitute native 4K artwork.",
                                 "Neon and fluorescent categories describe vivid RGB colors; they do not enable emission lighting, HDR output or bloom.",
                                 "OpenGL and enabled HD replacements are required. Persisted hd_textures=false takes precedence over the launch environment."])

    def dispatch(self, request):
        action = request.get("action", "stage")
        if action == "stage":
            return self.stage(request)
        if action == "apply":
            return self.apply(request)
        if action == "save":
            return self.save(request)
        raise ValueError("Use stage, apply or save; this API never starts a game")

    def apply(self, request):
        allowed = {"action", "profile", "strength", "enemy_profile", "enemy_strength"}
        if set(request) - allowed:
            raise ValueError("Live apply accepts colors only; save a preset for detail or texture-scope changes")
        if not {"profile", "strength", "enemy_profile", "enemy_strength"}.issubset(request):
            raise ValueError("Live apply requires both player and enemy profiles and strengths")
        identity, strength, _ = selection(request)
        enemy_identity, enemy_strength, _ = enemy_selection(request)
        percentages = []
        for amount in (strength, enemy_strength):
            percent = round(amount * 100)
            if abs(amount * 100 - percent) > 0.000001:
                raise ValueError("Live color strength must use whole percentage steps")
            percentages.append(percent)
        if self.command is None:
            return dict(ok=False, error="Live color apply is unavailable in this bridge", saved=False)
        result = self.command(dict(cmd="skin_material", player_profile=identity, player_strength_percent=percentages[0],
                                   enemy_profile=enemy_identity, enemy_strength_percent=percentages[1]), timeout=3.)
        if not result.get("ok"):
            return dict(ok=False, error=result.get("error", "Running game rejected live material colors"), live=result, saved=False)
        player, enemy = result.get("player", {}), result.get("enemy", {})
        if result.get("contract") != CONTRACT or result.get("ready") is not True or result.get("applied") is not True or result.get("apply_scope") != "color_only_next_draw" or player.get("profile") != identity or enemy.get("profile") != enemy_identity or player.get("strength_percent") != percentages[0] or enemy.get("strength_percent") != percentages[1]:
            return dict(ok=False, error="Native material acknowledgement does not match the requested pair", live=result, saved=False)
        self.last_live_ack = result
        return dict(ok=True, action="apply", live=result, saved=False, detail_layers_changed=False,
                    note="Colors acknowledged by the running game. Existing detail layers and key subsets are unchanged; this operation did not save a preset.")

    def save(self, request):
        with self.save_lock:
            staged = self.stage(dict(request, action="stage"))
            descriptor = Path(staged["config_path"])
            pointer = dict(schema_version=1, contract=CONTRACT, saved_at=time.time(),
                           descriptor_relative=descriptor.relative_to(self.root).as_posix(),
                           descriptor_sha256=hashlib.sha256(descriptor.read_bytes()).hexdigest())
            target = within(self.root, "tools/material-selection.json")
            if (self.root / "tools" / "material-selection.json").is_symlink():
                raise ValueError("Saved preset pointer must be a regular project file")
            temporary = within(self.root, "tools/.material-selection-" + uuid.uuid4().hex + ".json")
            try:
                with temporary.open("x", encoding="utf-8") as output:
                    output.write(json.dumps(pointer, indent=2) + "\n")
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            saved = saved_selection(self.root)
            if not saved["valid"]:
                raise ValueError(saved.get("error", "Saved preset could not be verified"))
            return dict(staged, action="save", status="saved_not_launched", saved=True, live_applied=False, game_launched=False, saved_selection=saved,
                        saved_launcher_path=str(self.root / "Play-Saved-Skin.cmd"),
                        note="Preset saved for the next manual launch. The running game and its current detail layers were not changed.")

    def stage(self, request):
        if request.get("action", "stage") != "stage":
            raise ValueError("Use action stage; this API does not launch or activate a game")
        identity, strength, targets = selection(request)
        enemy_identity, enemy_strength, enemy_targets = enemy_selection(request)
        detail = detail_selection(request, self.root)
        enemy_detail = detail_selection(request, self.root, enemy=True)
        player_active = identity != "stock" and strength > 0 or detail["id"] != "none" and detail["strength"] > 0
        enemy_active = enemy_identity != "stock" and enemy_strength > 0 or enemy_detail["id"] != "none" and enemy_detail["strength"] > 0
        detail_active = detail["id"] != "none" and detail["strength"] > 0 or enemy_detail["id"] != "none" and enemy_detail["strength"] > 0
        records, pack = source_records(self.root, targets + enemy_targets)
        slug = identity + "-" + time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + uuid.uuid4().hex[:8]
        target = within(self.root, Path("tools") / "material-profiles" / slug)
        target.mkdir(parents=True, exist_ok=False)
        descriptor = dict(schema_version=1, contract=CONTRACT, profile=identity, profile_label=PROFILE_MAP[identity]["label"],
                          strength=strength, targets=targets, created_at=time.time(), status="staged_not_launched", renderer="opengl",
                          enemy_profile=enemy_identity, enemy_strength=enemy_strength, enemy_targets=enemy_targets,
                          detail_map=detail["id"], detail_strength=detail["strength"], detail_scale=detail["scale"],
                          enemy_detail_map=enemy_detail["id"], enemy_detail_strength=enemy_detail["strength"], enemy_detail_scale=enemy_detail["scale"],
                          authored_detail=dict(player=detail, enemy=enemy_detail),
                          environment=environment(identity, strength, targets, self.root, enemy_identity, enemy_strength, enemy_targets, detail, enemy_detail), source_pack=pack, source_textures=records,
                          runtime=runtime_receipt(self.root, verify_hash=True, player_keys=targets if player_active else None,
                                                  enemy_keys=enemy_targets if enemy_active else None,
                                                  profiles=[profile for profile in (identity, enemy_identity) if profile != "stock"], require_detail=detail_active), in_game_verified=False)
        config = target / "material.json"
        config.write_text(json.dumps(descriptor, indent=2) + "\n", encoding="utf-8")
        launcher = target / "Launch-material.cmd"
        launcher.write_text('@echo off\nsetlocal\npython "%~dp0..\\..\\launch_material.py" --config "%~dp0material.json" %*\nexit /b %ERRORLEVEL%\n', encoding="utf-8")
        (target / "README.txt").write_text("STAGED MATERIAL PROFILE — NO GAME LAUNCHED\n\nRun Launch-material.cmd --check to validate the shader-enabled executable receipt, source pack and local game paths.\nRun Launch-material.cmd manually when ready to start the game launcher.\nChoose OpenGL, enable HD replacements and choose windowed settings.\nThe stock HD pack is referenced intact; the shader changes only the allowlisted texture+palette key.\nTo return to stock, launch normally without material environment overrides or stage the stock profile.\nConcept artwork is a direction reference, not an installed UV texture.\nNative in-game appearance and pacing still require review.\n", encoding="utf-8")
        return dict(ok=True, status="staged_not_launched", descriptor=descriptor, config_path=str(config), launcher_path=str(launcher),
                    config_url="/files/" + config.relative_to(self.root).as_posix(),
                    check_command='"' + str(launcher) + '" --check',
                    note="Material configuration prepared. No game process was started; existing textures and running sessions were untouched.")
