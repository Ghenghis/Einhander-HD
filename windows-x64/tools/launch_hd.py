"""Launch HD with the explicitly saved material preset, or stock when none exists.

--check validates without starting a game. --stock deliberately skips a saved
preset. An invalid saved preset fails visibly instead of silently losing it.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

from launch_material import prepare_launch as prepare_material_launch
from material_profiles import DEFAULT_PLAYER_KEYS, ENEMY_KEYS, environment, saved_selection


def prepare_hd_launch(root, *, stock=False, game_arguments=()):
    root = Path(root).resolve()
    saved = saved_selection(root) if not stock else {"exists": False}
    if saved.get("exists"):
        if not saved.get("valid"):
            raise ValueError("Saved skin preset needs attention: " + saved.get("error", "invalid receipt"))
        prepared = prepare_material_launch(root, saved["config_path"])
        # Ordinary Play-HD keeps its direct-game behavior; the separate material
        # launcher still opens the frontend for interactive configuration.
        prepared["arguments"][prepared["arguments"].index("--launcher")] = "--no-launcher"
        prepared.update(selection_source="explicit_saved_preset", saved_descriptor=saved["config_path"])
    else:
        paths = {
            "executable": root / "build-release/Einhander_Recompiled.exe",
            "pack_manifest": root / "hd-textures/stage1-v1/manifest.json",
            "game": root / "game.toml",
            "disc": root.parent / "ROM/Einhander (USA).cue",
            "bios": root / "build-release/bios/SCPH1001.BIN",
        }
        for label, path in paths.items():
            if not path.is_file():
                raise ValueError("Required HD launch file is missing (" + label + "): " + str(path))
        prepared = dict(
            arguments=[str(paths["executable"]), "--no-launcher", "--game", str(paths["game"]),
                       "--disc", str(paths["disc"]), "--bios", str(paths["bios"])],
            cwd=str(root), environment_overrides=environment(
                "stock", 0, list(DEFAULT_PLAYER_KEYS), root, "stock", 0, list(ENEMY_KEYS)),
            profile="stock", enemy_profile="stock", selection_source="explicit_stock" if stock else "no_saved_preset",
            status="validated_not_launched")
    prepared["arguments"].extend(game_arguments)
    prepared["environment_overrides"]["PSX_DISPLAY_RING"] = os.environ.get("PSX_DISPLAY_RING", "0")
    return prepared


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--stock", action="store_true")
    args, game_arguments = parser.parse_known_args(argv)
    try:
        prepared = prepare_hd_launch(Path(__file__).resolve().parents[1], stock=args.stock,
                                     game_arguments=game_arguments)
        if args.check:
            print(json.dumps(dict(ok=True, game_launched=False, **prepared), indent=2))
            return 0
        env = os.environ.copy()
        env.update(prepared["environment_overrides"])
        return subprocess.run(prepared["arguments"], cwd=prepared["cwd"], env=env, check=False).returncode
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps(dict(ok=False, error=str(error), game_launched=False)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
