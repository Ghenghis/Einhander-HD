#!/usr/bin/env python3
"""Einhander Recompiled - dev bridge + Robin bot.

Serves the dev menu (tools/dev_menu.html), proxies JSON line commands to the
game debug server on 127.0.0.1:4370, and hosts the built-in autoplay bot
"Robin" (name configurable) as a background thread.

    GET  /            -> dev_menu.html
    POST /cmd         body: {"line": "<raw JSON debug command>"} -> response
    GET  /bot/status  -> bot state JSON
    POST /bot         {"action":"start|stop|config", ...config fields}
    GET  /demo/status -> native attract control state
    POST /demo        {"action":"watch|exit|release"}
    GET  /files/*     -> files from the workspace root (screenshots, saves)
    GET  /health      -> bridge + game probe

Usage:  python tools/ein_bridge.py [port]   (default 8090)
Set EIN_DEBUG_PORT to target an isolated debug server (default 4370).
"""
import http.server
import json
import os
import socket
import struct
import sys
import threading
import time
import urllib.parse
from pathlib import Path

from devtools_service import DevTools, scoped_path
from research_service import ResearchService
import robin_stage_policy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
DEBUG_HOST = "127.0.0.1"
DEBUG_PORT = int(os.environ.get("EIN_DEBUG_PORT", "4370"))
DEBUG_IO_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# Debug-server primitives
# ---------------------------------------------------------------------------

def send_cmd(line: str, timeout: float = 8.0) -> str:
    if "\n" in line.strip() or "\r" in line.strip():
        raise ValueError("Send one JSON command at a time")
    with DEBUG_IO_LOCK, socket.create_connection((DEBUG_HOST, DEBUG_PORT), timeout=timeout) as s:
        with s.makefile("rw") as f:
            f.write(line.rstrip("\n") + "\n")
            f.flush()
            return f.readline().strip()


def cmd(obj: dict, timeout: float = 8.0) -> dict:
    try:
        obj = dict(obj)
        if obj.get("cmd") in ("read_ram", "dump_ram"):
            obj["len"] = int(obj.pop("size", obj.get("len", 1)))
            if not 1 <= obj["len"] <= 0x200000:
                raise ValueError("RAM read length must be between 1 and 2097152")
        if obj.get("cmd") == "memcard_status":
            obj["cmd"] = "mc_status"
        if obj.get("cmd") == "write_ram":
            value = obj.get("val", "")
            numeric = int(value, 16) if isinstance(value, str) else int(value)
            if not 0 <= numeric <= 255:
                raise ValueError("Native write_ram is u8 only; use /dev/write for a catalog u16 operation")
            obj["val"] = f"0x{numeric:02X}"
        result = json.loads(send_cmd(json.dumps(obj), timeout))
        if obj.get("cmd") in ("read_ram", "dump_ram") and "hex" in result:
            result["data"] = result["hex"]  # compatibility with earlier browser/bot clients
        return result
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Robin - autoplay bot
# ---------------------------------------------------------------------------
# Decoded game addresses (US Einhander, SCUS-94243):
ADDR_LIVES = "0x800813C4"      # u8 remaining lives
ADDR_INVINC = "0x80085718"     # u8 invincibility timer (nonzero = invulnerable)
ADDR_HYPER = "0x80085709"      # u8 hyper mode flag
ADDR_AMMO = "0x80084832"       # u16 weapon ammo
ADDR_AMMO2 = "0x80084834"      # u16 ammo counter
ADDR_SCOREMULT = "0x80081326"  # u8 score multiplier
ADDR_HITS = "0x80085710"       # u8 hit counter per the decoded-address table

# Pad words are active-low (idle = 0xFFFF).
BTN = {
    "select": 0xFFFE, "l3": 0xFFFD, "r3": 0xFFFB, "start": 0xFFF7,
    "up": 0xFFEF, "right": 0xFFDF, "down": 0xFFBF, "left": 0xFF7F,
    "l2": 0xFEFF, "r2": 0xFDFF, "l1": 0xFBFF, "r1": 0xF7FF,
    "tri": 0xEFFF, "circle": 0xDFFF, "x": 0xBFFF, "square": 0x7FFF,
}


def btn_word(*names: str) -> int:
    w = 0xFFFF
    for n in names:
        w &= BTN[n]
    return w


class Robin(threading.Thread):
    """Configurable autoplay bot driven entirely through the debug server."""

    def __init__(self):
        super().__init__(daemon=True)
        self.name = "Robin"
        self.running = False
        self.autofire = True
        self.weave = True          # horizontal weave to hunt enemies / dodge
        self.dodge = True          # occasional vertical dodge
        self.revive = True         # push through continue / confirm dialogs
        self.invincible = False    # keep invincibility timer topped up (cheat)
        self.hull_guard = False    # preserve the last active craft at zero spare lives
        self.movement = "weave"
        self.fire_mode = "cross"
        self._lane_origin = None
        self._lane_last_frame = None
        self._vertical_direction = 1
        self._greif_anchor = None
        self._greif_hull_frame = None
        self._stage = None
        self.position = None
        self.tick = 0.15           # decision period (seconds)
        self.log = []
        self._lock = threading.Lock()
        self._halt = threading.Event()

    def note(self, msg: str) -> None:
        with self._lock:
            self.log.append({"t": round(time.time(), 1), "msg": msg})
            self.log = self.log[-80:]

    def status(self) -> dict:
        with self._lock:
            return {
                "name": self.name, "running": self.running,
                "autofire": self.autofire, "weave": self.weave,
                "dodge": self.dodge, "revive": self.revive,
                "invincible": self.invincible, "tick": self.tick,
                "movement": self.movement, "fire_mode": self.fire_mode,"hull_guard":self.hull_guard,
                "position": self.position,
                "thread_alive": self.is_alive(),
                "log": list(self.log),
            }

    def apply(self, cfg: dict) -> None:
        updates = {}
        if "tick" in cfg:
            tick = float(cfg["tick"])
            if not 1/30 <= tick <= 2:
                raise ValueError("Bot decision period must be between 1/30 and 2 seconds")
            updates["tick"] = tick
        for key in ("autofire", "weave", "dodge", "revive", "invincible","hull_guard"):
            if key in cfg:
                if not isinstance(cfg[key], bool):
                    raise ValueError(key + " must be a boolean")
                updates[key] = cfg[key]
        if "name" in cfg:
            updates["name"] = str(cfg["name"] or "Robin")[:24]
        for key, allowed in (("movement", ("weave", "left_lane", "upper_lane", "greif_lane", "stage_lane", "draw_lane")),
                             ("fire_mode", ("cross", "both"))):
            if key in cfg:
                if cfg[key] not in allowed:
                    raise ValueError(key + " must be one of " + ", ".join(allowed))
                updates[key] = cfg[key]
        for key, value in updates.items():
            setattr(self, key, value)
        if self.movement=='stage_lane':self._stage=robin_stage_policy.session()

    def _read(self, addr: str, n: int):
        r = cmd({"cmd": "read_ram", "addr": addr, "size": n}, timeout=1.5)
        if r.get("ok") and "data" in r:
            try:
                return bytes.fromhex(str(r["data"]))
            except (TypeError, ValueError):
                pass
        return None

    def _press(self, *names: str, frames: int = 8):
        if self.running:
            cmd({"cmd": "press", "buttons": btn_word(*names), "frames": frames}, timeout=1.5)

    def request_stop(self):
        self.running = False
        self._halt.set()

    def lane_buttons(self, frame: int):
        """Bounded pad movement timed by guest frames, independent of host stalls."""
        if self._lane_last_frame is not None and frame < self._lane_last_frame:
            self.request_stop()
            return []
        self._lane_last_frame = frame
        if self._lane_origin is None:
            self._lane_origin = frame
        elapsed = frame - self._lane_origin
        moves = ["left"] if self.weave and elapsed < 24 else []
        if self.dodge and elapsed >= 24:
            moves.append("down" if ((elapsed-24)//18) % 2 == 0 else "up")
        if self.autofire:
            moves.append("x")
            if self.fire_mode == "both":
                moves.append("square")
        return moves

    def greif_target(self,state):
        """Experimental pad-only sweep, anchored to actual source-draw frames.

        Burst windows are measured in robin-analysis/ROBIN-DEATHS.md. Their
        avoidance schedule remains a hypothesis until a live encounter passes.
        """
        frame,age=state.get('frame'),state.get('age_frames')
        if type(frame) is not int or type(age) is not int or frame<0 or not 0<=age<=12:
            raise ValueError('Fresh guest clock unavailable')
        if self._greif_hull_frame is not None:
            if frame<self._greif_hull_frame:raise ValueError('Guest clock reversed')
            if frame-self._greif_hull_frame>150:self._greif_anchor=None
        self._greif_hull_frame=frame;now=frame+age
        clock=state.get('greif_draw')
        if not isinstance(clock,dict) or type(clock.get('valid')) is not bool:
            raise ValueError('Greif source clock unavailable')
        if type(clock.get('age_frames')) is not int or clock['age_frames']<0:
            raise ValueError('Malformed Greif source age')
        if clock['valid']:
            first,last,stale=(clock.get(k) for k in ('first_frame','last_frame','age_frames'))
            if (not all(type(v) is int for v in (first,last,stale)) or
                not 0<=first<=last<=now or stale!=now-last or stale>12):
                raise ValueError('Malformed Greif source clock')
            self._greif_anchor=first
        elif self._greif_anchor is not None and clock.get('age_frames',0)>180:
            self._greif_anchor=None
        g=None if self._greif_anchor is None else now-self._greif_anchor
        target,tolerance,direction,label=14,2,None,'upper home'
        if g is not None and g>=400:
            if g<650:target=14+(g-400)*186/250;direction='down';label='Greif first volley'
            elif g<680:target=200;tolerance=10;label='Greif volley gap'
            elif g<900:target=200-(g-680)*186/220;direction='up';label='Greif second volley'
            else:
                leg,phase=divmod(g-900,250);down=leg%2==0
                target=(14+min(phase,200)*186/200) if down else (200-min(phase,200)*186/200)
                direction='down' if down else 'up';label='Greif later volley hypothesis'
            if direction:tolerance=10
        self.position['greif_policy']=dict(anchor=self._greif_anchor,elapsed=g,target_y=target,
            direction=direction,label=label,qualified=False)
        return target,tolerance,direction

    def draw_buttons(self, state: dict):
        """Screen-space feedback from a fresh, source-matched hull draw union."""
        if not state.get('ok') or not state.get('enabled') or not state.get('valid'):
            raise ValueError('Fresh hull draw unavailable')
        bounds,viewport=state.get('bounds'),state.get('viewport')
        if (not isinstance(bounds,list) or len(bounds)!=4 or
            not isinstance(viewport,list) or len(viewport)!=2 or
            not all(isinstance(v,int) for v in bounds+viewport)):
            raise ValueError('Malformed hull draw geometry')
        l,t,r,b=bounds;w,h=viewport
        if not (128<=w<=1024 and 128<=h<=512 and l<=r and t<=b and
                0<r-l<w//2 and 0<b-t<h//2 and r>=0 and l<w and b>=0 and t<h):
            raise ValueError('Hull geometry is outside the calibrated viewport')
        x,y=(l+r)/2,(t+b)/2
        self.position=dict(x=x,y=y,width=w,height=h,frame=state.get('frame'),
            age_frames=state.get('age_frames'),fresh=True,space=state.get('basis','hull draw geometry'))
        moves=[]
        if self.movement=='stage_lane':
            self.greif_target(state)  # Validate the actual source clock before using it.
            moves=self._stage.moves(state,x,y)
            if not self.weave:moves=[m for m in moves if m not in ('left','right')]
            if not self.dodge:moves=[m for m in moves if m not in ('up','down')]
            self.position['stage_policy']=dict(self._stage.last)
            return moves
        if self.movement in ('upper_lane','greif_lane'):
            # Finite pulses follow actual completed-frame geometry. Open-loop
            # alternating pulses drifted low in the first live upper-lane run.
            if self.weave:
                if x>32:moves.append('left')
                elif x<24:moves.append('right')
            if self.dodge:
                target,tolerance,direction=self.greif_target(state) if self.movement=='greif_lane' else (14,2,None)
                if y>target+tolerance and direction!='down':moves.append('up')
                elif y<target-tolerance and direction!='up':moves.append('down')
            return moves
        if self.weave:
            if x>w*.29:moves.append('left')
            elif x<w*.19:moves.append('right')
        if self.dodge:
            if y>=h*.64:self._vertical_direction=-1
            elif y<=h*.32:self._vertical_direction=1
            moves.append('down' if self._vertical_direction>0 else 'up')
        return moves

    def run(self) -> None:
        self.note(f"{self.name} online")
        phase, phase_len, dir_h, dir_v = 0, 0, "right", "down"
        failed_reads, previous_lives, missing_draws, respawn_grace = 0, None, 0, 0
        missing_since=None
        while self.running:
            try:
                lives = self._read(ADDR_LIVES, 1)
                # A disconnected game is not a continue screen. Never inject
                # revival input after a failed state read.
                if lives is None or len(lives) != 1:
                    cmd({"cmd": "clear_input"}, timeout=1)
                    failed_reads += 1
                    if failed_reads >= 3:
                        self.note("Game unavailable after three reads; bot stopped and input released.")
                        self.running = False
                        break
                    self.note("State read unavailable; input released while retrying.")
                    self._halt.wait(.25)
                    continue
                failed_reads = 0
                if self._stage is not None:self._stage.note_lives(lives[0])
                respawn_grace=max(0,respawn_grace-1)
                if previous_lives is not None and lives[0]<previous_lives:
                    respawn_grace=20
                    if self.movement=='upper_lane':self._lane_origin=None
                if previous_lives is not None and lives[0] > previous_lives:
                    self._lane_origin = None
                previous_lives = lives[0]
                dead_or_menu = lives[0] == 0
                draw_moves=None
                if self.movement in ('draw_lane','upper_lane','greif_lane','stage_lane') or self.hull_guard:
                    state=cmd({'cmd':'player_draw'},timeout=1.5)
                    if not state.get('ok') or not state.get('enabled'):
                        self.note('Hull draw tracking unavailable; bot stopped.')
                        self.request_stop();break
                    if state.get('valid'):
                        if self.movement in ('draw_lane','upper_lane','greif_lane','stage_lane'):
                            try:draw_moves=self.draw_buttons(state)
                            except ValueError as error:
                                self.note(str(error)+'; bot stopped.');self.request_stop();break
                        # The native lives counter can be zero while the last
                        # craft is still flying. A fresh hull is not Continue.
                        dead_or_menu=False
                        missing_draws=0
                        missing_since=None
                    elif self.movement in ('draw_lane','upper_lane','greif_lane','stage_lane') and not dead_or_menu:
                        if self._stage is not None and type(state.get('frame')) is int and type(state.get('age_frames')) is int:
                            self._stage.absent(state['frame']+state['age_frames'])
                        missing_draws+=1
                        if missing_since is None:missing_since=time.monotonic()
                        age=state.get('age_frames');draw_frame=state.get('frame')
                        known_clock=type(age) is int and type(draw_frame) is int and age>=0 and draw_frame>=0
                        # Measured native death-to-respawn gaps exceed the old
                        # forty-poll (~6s) limit. Release input while waiting,
                        # with both a guest-frame and host-time bound. Missing
                        # clock replies retain the original forty-poll stop.
                        if missing_draws>=40 and (not known_clock or age>720 or time.monotonic()-missing_since>15):
                            self.note('Hull geometry absent beyond bounded respawn wait; bot stopped.')
                            self.request_stop();break
                        if respawn_grace and self.position is not None and isinstance(age,int) and 12<age<=180:
                            # After an observed life loss, keep bounded fire
                            # through the respawn fly-in without guessing any
                            # movement. Zero lives still stops before Continue.
                            self.position=dict(self.position,fresh=False,age_frames=age)
                            draw_moves=[]
                        else:
                            cmd({'cmd':'clear_input'},timeout=1)
                            self._halt.wait(self.tick)
                            continue

                if self.invincible:
                    cmd({"cmd": "write_ram",
                         "addr": ADDR_INVINC, "val": "0xFF"}, timeout=1.5)

                if dead_or_menu:
                    if not self.revive:
                        self.note("No lives remain; revival disabled, bot stopped.")
                        self.request_stop()
                        break
                    self._press("x", frames=6)
                    self._halt.wait(0.5)
                    self._press("start", frames=6)
                    self._halt.wait(0.8)
                    continue

                moves = []
                if self.movement in ("draw_lane","upper_lane","greif_lane","stage_lane"):
                    moves=draw_moves
                    fire=["x"] if self.autofire else []
                    if self.autofire and self.fire_mode=="both":fire.append("square")
                    self._press(*(moves+fire),frames=6)
                    self._halt.wait(.10)
                    if fire:self._press(*fire,frames=max(12,int(self.tick*60)+12))
                    self._halt.wait(self.tick)
                    continue
                if self.movement == "left_lane":
                    state = cmd({"cmd": "get_registers"}, timeout=1.5)
                    if not state.get("ok") or not isinstance(state.get("frame"), int):
                        cmd({"cmd": "clear_input"}, timeout=1)
                        self._halt.wait(self.tick)
                        continue
                    moves = self.lane_buttons(state["frame"])
                    if moves:
                        self._press(*moves, frames=max(6, int(self.tick * 60)))
                    self._halt.wait(self.tick)
                    continue
                if self.weave:
                    phase_len += 1
                    if phase_len >= max(4, int(1.0 / self.tick)):
                        phase_len = 0
                        dir_h = "left" if dir_h == "right" else "right"
                        phase += 1
                        if phase % 3 == 0:
                            dir_v = "up" if dir_v == "down" else "down"
                    moves.append(dir_h)
                    if self.dodge and phase % 3 == 2:
                        moves.append(dir_v)
                if self.autofire:
                    moves.append("x")
                    if self.fire_mode == "both":
                        moves.append("square")
                if moves:
                    self._press(*moves, frames=max(6, int(self.tick * 60)))
            except Exception as e:  # noqa: BLE001
                self.note(f"err {e}")
                self._halt.wait(0.5)
            self._halt.wait(self.tick)
        cmd({"cmd": "clear_input"}, timeout=1)
        self.note(f"{self.name} stopped")


_bot_lock = threading.Lock()
BOT = Robin()
DEMO = {"state": "released", "message": "Native attract control is idle."}


def bot_start(cfg: dict) -> dict:
    global BOT
    with _bot_lock:
        if BOT.is_alive():
            BOT.request_stop()
            BOT.join(timeout=3)
            if BOT.is_alive():
                raise ValueError("Previous bot is still stopping; retry after it exits")
        BOT = Robin()
        BOT.apply(cfg)
        BOT.running = True
        BOT.start()
        DEMO.update(state="released", message="Robin controls input; native attract watch ended.")
        return BOT.status()


def bot_stop() -> dict:
    with _bot_lock:
        BOT.request_stop()
        if BOT.is_alive():
            BOT.join(timeout=3)
        cmd({"cmd": "clear_input"}, timeout=1)
        return BOT.status()


def native_demo(action: str) -> dict:
    """Release synthetic input so the game's own title/attract timer can run."""
    if action not in ("watch", "exit", "release"):
        return {"ok": False, "error": "Use watch, exit, or release."}
    if action in ("watch", "exit"):
        DEVTOOLS.stop("Native demo transition released all holds.")
    with _bot_lock:
        BOT.request_stop()
        if BOT.is_alive():
            BOT.join(timeout=3)
        if BOT.is_alive():
            DEMO.update(state="error", message="Robin is still stopping; retry after it stops.")
            return {"ok": False, "error": DEMO["message"]}
        result = cmd({"cmd": "clear_input"})
        if not result.get("ok"):
            DEMO.update(state="error", message=result.get("error", "Input release failed."))
            return result
        if action == "exit":
            result = cmd({"cmd": "press", "buttons": BTN["start"], "frames": 12})
            if not result.get("ok"):
                DEMO.update(state="error", message=result.get("error", "Exit command failed."))
                return result
            DEMO.update(state="exit_requested", message="Start sent to exit the native demo. Input expires after 12 frames.")
        elif action == "watch":
            DEMO.update(state="waiting", message="Input released. At the title screen, wait for the game's native demo. Return to title first if you are playing.")
        else:
            DEMO.update(state="released", message="All injected input released. Keyboard and controller are available.")
        return {"ok": True, "demo": dict(DEMO), "pad": cmd({"cmd": "pad_status"})}


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

DEVTOOLS = DevTools(ROOT, cmd)


def research_context():
    with DEVTOOLS.mutex:
        holds = [DEVTOOLS._public_lock(item) for item in DEVTOOLS.locks.values()]
    bot = BOT.status()
    bot.pop("log", None)
    return dict(holds=holds, bot=bot, scope="Local bridge assists only; external tools are not observable")


RESEARCH = ResearchService(ROOT, cmd, context=research_context)

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _local_host(self):
        try:
            host = urllib.parse.urlsplit("//" + self.headers.get("Host", ""))
            return host.hostname in ("127.0.0.1", "localhost") and (host.port or 80) == self.server.server_port
        except ValueError:
            return False

    def _json(self, code: int, obj) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        if n < 0 or n > 26 * 1024 * 1024:
            raise ValueError("Request body exceeds 26 MiB")
        value = json.loads(self.rfile.read(n) or b"{}")
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object")
        return value

    def do_POST(self):
        # Browser commands may mutate game RAM. Do not accept a remote web
        # page's cross-origin request merely because this service is local.
        origin = self.headers.get("Origin")
        if not self._local_host():
            return self._json(403, {"ok": False, "error": "Use the local bridge hostname and port"})
        if origin and origin != "http://" + self.headers.get("Host", ""):
            return self._json(403, {"ok": False, "error": "Cross-origin commands are forbidden"})
        try:
            return self._post()
        except (ValueError, TypeError, KeyError, OSError) as exc:
            return self._json(400, {"ok": False, "error": str(exc)})
        except RuntimeError as exc:
            return self._json(502, {"ok": False, "error": str(exc)})

    def _post(self):
        path = urllib.parse.urlparse(self.path).path
        operations = {"/dev/write": DEVTOOLS.write, "/dev/lock": DEVTOOLS.lock,
                      "/dev/undo": DEVTOOLS.undo, "/dev/skins": DEVTOOLS.skin_action,
                      "/dev/materials": DEVTOOLS.material_profiles.dispatch, "/dev/research": RESEARCH.dispatch}
        if path in operations:
            result = operations[path](self._body())
            return self._json(200 if result.get("ok") else 409, result)
        if path == "/dev/emergency":
            result = DEVTOOLS.stop("Emergency release from Development Center.")
            result["research"] = RESEARCH.shutdown(persist_disarm=True)
            result["bot"] = bot_stop()
            result["input"] = cmd({"cmd": "clear_input"}, timeout=1)
            return self._json(200, result)
        if path == "/cmd":
            raw = self._body().get("line", "")
            if not isinstance(raw, str):
                raise ValueError("line must be a JSON command string")
            raw = raw.strip()
            if not raw:
                return self._json(400, {"ok": False, "error": "empty body"})
            try:
                obj = json.loads(raw)
                if not isinstance(obj, dict):
                    raise ValueError("Command must be a JSON object")
                # clear_input releases the virtual controller override only.
                # Holds and research have separate, explicit lifecycle actions;
                # finite input pulses must not silently remove player assists.
                if obj.get("cmd") in ("savestate", "reset", "input_route_start"):
                    DEVTOOLS.stop("A state/input transition released all holds.")
                if obj.get("cmd") in ("savestate", "reset"):
                    stopped = RESEARCH.stop(reason="raw_state_transition")
                    if not stopped["ok"]:
                        return self._json(409, dict(ok=False, error="Research capture is still finalizing; the state transition was not sent", research=stopped))
                result = cmd(obj)
                return self._json(200 if result.get("ok") else 502,
                                  {"ok": bool(result.get("ok")), "data": result,
                                   "error": result.get("error")})
            except Exception as e:  # noqa: BLE001
                return self._json(502, {"ok": False, "error": str(e)})
        if path == "/bot":
            req = self._body()
            act = req.get("action")
            if act == "start":
                return self._json(200, {"ok": True, "bot": bot_start(req)})
            if act == "stop":
                return self._json(200, {"ok": True, "bot": bot_stop()})
            if act == "config":
                BOT.apply(req)
                return self._json(200, {"ok": True, "bot": BOT.status()})
            return self._json(400, {"ok": False, "error": "bad action"})
        if path == "/demo":
            result = native_demo(self._body().get("action"))
            return self._json(200 if result.get("ok") else 400, result)
        self._json(404, {"ok": False, "error": "unknown path"})

    def do_GET(self):
        if not self._local_host():
            return self._json(403, {"ok": False, "error": "Use the local bridge hostname and port"})
        try:
            return self._get()
        except (ValueError, OSError) as exc:
            return self._json(400, {"ok": False, "error": str(exc)})

    def _get(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/dev_menu.html"):
            target = os.path.join(TOOLS, "dev_menu.html")
        elif path == "/dev/catalog":
            return self._json(200, DEVTOOLS.catalog())
        elif path == "/dev/status":
            return self._json(200, DEVTOOLS.status())
        elif path == "/dev/skins":
            return self._json(200, DEVTOOLS.skins())
        elif path == "/dev/materials":
            return self._json(200, DEVTOOLS.material_profiles.catalog())
        elif path == "/dev/research":
            return self._json(200, RESEARCH.overview())
        elif path.startswith("/dev/skins/source/"):
            filename = urllib.parse.unquote(path[len("/dev/skins/source/"):])
            target = str(DEVTOOLS.source_image(filename))
        elif path == "/dev/evidence":
            return self._json(200, DEVTOOLS.evidence())
        elif path.startswith("/dev/evidence/files/"):
            relative = urllib.parse.unquote(path[len("/dev/evidence/files/"):])
            target = str(scoped_path(DEVTOOLS.evidence_root, relative))
            if Path(target).suffix.lower() not in (".png", ".jpg", ".jpeg", ".json"):
                return self._json(403, {"ok": False, "error": "Unsupported evidence format"})
        elif path == "/health":
            r = cmd({"cmd": "gpu_state"}, timeout=3)
            return self._json(200, {"ok": bool(r.get("ok")), "game": r})
        elif path == "/bot/status":
            return self._json(200, {"ok": True, "bot": BOT.status()})
        elif path == "/demo/status":
            return self._json(200, {"ok": True, "demo": dict(DEMO)})
        elif path.startswith("/files/"):
            rel = urllib.parse.unquote(path[len("/files/"):])
            target = str(scoped_path(Path(ROOT), rel))
        else:
            return self._json(404, {"ok": False, "error": "unknown path"})

        if not os.path.isfile(target):
            return self._json(404, {"ok": False, "error": "not found"})
        ctype = "text/plain"
        for ext, ct in ((".html", "text/html"), (".png", "image/png"),
                        (".jpg", "image/jpeg"), (".jpeg", "image/jpeg"),
                        (".json", "application/json"), (".js", "text/javascript"), (".toml", "text/plain")):
            if target.endswith(ext):
                ctype = ct
        with open(target, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    DEVTOOLS.start()
    RESEARCH.restore_arm()
    print(f"Einhander dev bridge: http://127.0.0.1:{port}")
    print(f"  dev menu : http://127.0.0.1:{port}/")
    print("  bot API  : GET /bot/status  POST /bot")
    try:
        srv.serve_forever()
    finally:
        BOT.request_stop()
        RESEARCH.shutdown()
        DEVTOOLS.stop("Bridge shutdown")
        DEVTOOLS._quit.set()
        srv.server_close()


if __name__ == "__main__":
    main()
