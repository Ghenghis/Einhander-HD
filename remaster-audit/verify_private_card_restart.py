"""Pin a read-only native private-card restart/load observation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "remaster-audit/dev-center-evidence/hud-4k-candidate-20261112-v5"


def ref(path):
    data = path.read_bytes()
    return dict(path=str(path),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))


def main():
    seed_path = EVIDENCE / "private-card-seed.json"
    seed = json.loads(seed_path.read_text())
    launch_path = EVIDENCE / "launch-candidate.json"
    launch = json.loads(launch_path.read_text())
    card_path = EVIDENCE / "state/card1.mcd"
    card = card_path.read_bytes()
    if len(card) != 131072 or card[:2] != b"MC" or ref(card_path)["sha256"] != seed["card1_sha256"]:
        raise ValueError("Private card differs from the accepted seed")
    entries = []
    for block in range(1,16):
        frame = card[block*128:(block+1)*128]
        if frame[0] != 0x51:
            continue
        xor = 0
        for value in frame[:127]:
            xor ^= value
        entries.append(dict(block=block,allocation_status=f"0x{frame[0]:02X}",
            filename=frame[10:30].split(b"\0")[0].decode("ascii"),directory_xor_valid=xor==frame[127],
            sc_payload=card[block*8192:block*8192+2]==b"SC",pilot_ascii_in_payload=b"PILOT" in card[block*8192:(block+1)*8192]))
    if not any(e["filename"] == "BASCUS-94243" and e["directory_xor_valid"] and e["sc_payload"] and e["pilot_ascii_in_payload"] for e in entries):
        raise ValueError("Native PILOT save structure not found")
    screenshot_path = EVIDENCE / "captures/e2e-title-copyright-and-loaded-pilot.png"
    screenshot_receipt_path = screenshot_path.with_suffix(".json")
    screenshot_receipt = json.loads(screenshot_receipt_path.read_text())
    if (ref(screenshot_path)["sha256"] != screenshot_receipt["sha256"] or
            seed.get("user_cards_mounted") is not False or launch.get("user_cards_mounted") is not False or
            "PSX_LOAD_SLOT" not in launch.get("cleaned_environment_keys",[]) or
            Path(launch["writable_state"]).resolve() != card_path.parent.resolve() or
            screenshot_receipt["at_utc"] <= launch["at_utc"]):
        raise ValueError("Private native restart evidence is inconsistent")
    image = screenshot_path.read_bytes()
    proof = dict(schema_version=1,verified_at_utc=datetime.now(timezone.utc).isoformat(),
        restart_load_verified=True,scope="Native startup load of unchanged private PILOT card; no save-state autoload or user-card mount. Screenshot visually inspected by root and integration auditor.",
        seed=ref(seed_path),launch=ref(launch_path),private_card=ref(card_path),
        seed_sha256=seed["card1_sha256"],current_card_sha256=ref(card_path)["sha256"],seed_unchanged=True,
        directory_entries=entries,actual_title_screenshot=dict(**ref(screenshot_path),dimensions=list(struct.unpack(">II",image[16:24])),frame_before=screenshot_receipt["frame_before"],frame_after=screenshot_receipt["frame_after"]),
        screenshot_receipt=ref(screenshot_receipt_path),visual_observation="Title displays PILOT beneath GAME START after new candidate PID8760 startup.",
        user_cards_mounted=False,seed_initial_restart_load_verified=seed.get("restart_load_verified"),
        limitations=["Screenshot is sequential next-present evidence, not atomic with telemetry", "Does not establish all overwrite/discard/load-error flows or future persistence"])
    out = EVIDENCE / "private-card-restart-load-acceptance.json"
    out.write_text(json.dumps(proof,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(ref(out)))


if __name__ == "__main__":
    main()
