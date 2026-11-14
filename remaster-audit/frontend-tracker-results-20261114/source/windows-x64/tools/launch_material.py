"""Manual, receipt-checked launcher for a staged material profile.

--check performs read-only validation and never starts a game.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

from material_profiles import CONTRACT, detail_selection, enemy_selection, environment, runtime_receipt, saved_selection, selection, source_records, within


def prepare_launch(root, config_path):
    root = Path(root).resolve()
    config_path = Path(config_path).resolve()
    workspace = within(root, "tools/material-profiles")
    if not config_path.is_relative_to(workspace) or config_path.name != "material.json":
        raise ValueError("Choose a material.json staged inside tools/material-profiles")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("contract") != CONTRACT or config.get("schema_version") != 1:
        raise ValueError("Unsupported material descriptor contract")
    identity, strength, targets = selection(config)
    enemy_identity, enemy_strength, enemy_targets = enemy_selection(config)
    detail = detail_selection(config, root)
    enemy_detail = detail_selection(config, root, enemy=True)
    for channel, receipt in (("player", detail), ("enemy", enemy_detail)):
        if receipt["id"] != "none":
            expected_detail = config.get("authored_detail", {}).get(channel, {})
            if expected_detail.get("id") != receipt["id"] or expected_detail.get("sha256") != receipt["sha256"]:
                raise ValueError("Authored detail receipt changed; stage a new material descriptor")
    records, pack = source_records(root, targets + enemy_targets)
    if pack["manifest_sha256"] != config.get("source_pack", {}).get("manifest_sha256"):
        raise ValueError("Installed pack manifest changed; stage a new material descriptor")
    expected = {record["key"]: record["sha256"] for record in config.get("source_textures", [])}
    if any(expected.get(record["key"]) != record["sha256"] for record in records):
        raise ValueError("Source texture receipt changed; stage a new material descriptor")
    player_active = identity != "stock" and strength > 0 or detail["id"] != "none" and detail["strength"] > 0
    enemy_active = enemy_identity != "stock" and enemy_strength > 0 or enemy_detail["id"] != "none" and enemy_detail["strength"] > 0
    detail_active = detail["id"] != "none" and detail["strength"] > 0 or enemy_detail["id"] != "none" and enemy_detail["strength"] > 0
    runtime = runtime_receipt(root, verify_hash=True, player_keys=targets if player_active else None,
                              enemy_keys=enemy_targets if enemy_active else None,
                              profiles=[profile for profile in (identity, enemy_identity) if profile != "stock"], require_detail=detail_active)
    if not runtime.get("ready"):
        raise ValueError(runtime["reason"])
    game = root / "game.toml"
    disc = root.parent / "ROM" / "Einhander (USA).cue"
    bios = root / "build-release" / "bios" / "SCPH1001.BIN"
    for path in (game, disc, bios):
        if not path.is_file():
            raise ValueError("Required local game path is missing: " + str(path))
    overrides = environment(identity, strength, targets, root, enemy_identity, enemy_strength, enemy_targets, detail, enemy_detail)
    arguments = [runtime["executable"], "--launcher", "--renderer", "opengl", "--game", str(game), "--disc", str(disc), "--bios", str(bios)]
    return dict(arguments=arguments, cwd=str(root), environment_overrides=overrides, runtime=runtime,
                profile=identity, strength=strength, targets=targets, enemy_profile=enemy_identity,
                enemy_strength=enemy_strength, enemy_targets=enemy_targets, authored_detail=dict(player=detail, enemy=enemy_detail), status="validated_not_launched")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config")
    source.add_argument("--saved", action="store_true", help="Use the explicitly saved local preset")
    parser.add_argument("--check", action="store_true", help="Validate only; never launch a game")
    arguments = parser.parse_args(argv)
    try:
        root = Path(__file__).resolve().parents[1]
        config_path = arguments.config
        if arguments.saved:
            saved = saved_selection(root)
            if not saved.get("valid"):
                raise ValueError(saved.get("error", "No material preset has been explicitly saved"))
            config_path = saved["config_path"]
        prepared = prepare_launch(root, config_path)
        if arguments.check:
            print(json.dumps(dict(ok=True, **prepared), indent=2))
            return 0
        env = os.environ.copy()
        env.update(prepared["environment_overrides"])
        return subprocess.run(prepared["arguments"], cwd=prepared["cwd"], env=env, check=False).returncode
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps(dict(ok=False, error=str(exc), game_launched=False)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
