"""Timer-only survival aid for explicitly labelled, isolated facade reviews.

Reuses the existing verified devtools hold. Never changes lives, stage, camera,
speed or saves. Stopping releases the hold without forcing the countdown to zero.
"""
import json
from pathlib import Path
import sys


class SurvivalAid:
    def __init__(self, report, identity, command, stamp):
        identity(report)
        spec = report["launches"]["candidate"]
        directory = Path(report["evidence"]).resolve()
        state = Path(spec["writable_state"]).resolve()
        if spec["user_cards_mounted"] or not state.is_relative_to(directory):
            raise ValueError("Survival aid requires isolated private state")
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "windows-x64/tools"))
        from devtools_service import DevTools

        self.report, self.stamp = report, stamp
        self.started = stamp()
        self.writes = 0
        self.last_write = None

        def scoped(request, timeout=1.5):
            cmd = request.get("cmd")
            allowed = cmd == "gpu_state"
            if cmd == "read_ram":
                allowed = request.get("addr") in ("0x80085718", "0x800813C4") and request.get("len") == 1
            if cmd == "write_ram":
                allowed = request.get("addr") == "0x80085718" and request.get("val") == "0xA5"
            if not allowed:
                raise RuntimeError("Command outside timer-only survival scope")
            try:
                reply = command(report, json.dumps(request))
            except Exception as error:
                raise RuntimeError(str(error)) from error
            if cmd == "write_ram" and reply.get("ok"):
                self.writes += 1
                self.last_write = stamp()
            return reply

        self.dev = DevTools(directory, scoped)
        self.arm = self.dev.lock(dict(field="invincibility", value=165, ttl_seconds=180))
        if not self.arm.get("ok"):
            raise RuntimeError("Private survival hold did not arm: " + str(self.arm))
        self.dev.start()

    def stop(self):
        self.dev._quit.set()
        self.dev.stop("Private facade review ended; no direct timer clear")
        self.dev.thread.join(timeout=20)
        if self.dev.thread.is_alive():
            raise RuntimeError("Survival worker did not stop; do not close/reuse this port")
        return dict(kind="invincibility countdown only", address="0x80085718", width_bytes=1,
                    value=165, lease_seconds=180, interval_seconds=0.15,
                    started_at_utc=self.started, stopped_at_utc=self.stamp(),
                    successful_writes=self.writes, last_write_at_utc=self.last_write,
                    arm=self.arm, forced_timer_clear=False, lives_writes=False,
                    stage_jumps=False, state_loads=False, command_receipts="commands/",
                    purpose="Visual reachability aid; not unassisted gameplay or performance evidence")
