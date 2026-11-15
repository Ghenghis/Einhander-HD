#!/usr/bin/env python3
"""Build the private v58 frame-phase-ring patch (claude-einhander). No compile, no game.

Bases (read-only, hash-asserted):
  main.cpp          C:/github/Einhander-wt/upload-index-hitch/.../runtime/src/main.cpp   f4ecc89c... (the v57 runtime-main source)
  gpu_gl_renderer.c remaster-audit/runtime-review/native-upload-stream/new/                 4a19590b... (v57)
  debug_server.c    remaster-audit/runtime-review/native-upload-stream/new/                 5365caa1... (v57)
latency_ring.c is NOT modified. Outputs go to ./new and ./diffs, plus patch-receipt.json. See frame_phase_ring.h.
"""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = Path("C:/github/Einhander-wt/upload-index-hitch/windows-x64/psxrecomp/runtime/src")
V57 = Path("C:/github/Einhander/remaster-audit/runtime-review/native-upload-stream/new")
BASES = {"main.cpp": (WT / "main.cpp", "f4ecc89c69b394ca3c334fdfd54958bf496f5573c03a54c5c79cb96892c67b9c"),
         "gpu_gl_renderer.c": (V57 / "gpu_gl_renderer.c", "4a19590b0a80e9431eb116af321367e9eef1532e2fadea12f9e5e6bcd1e7dbc8"),
         "debug_server.c": (V57 / "debug_server.c", "5365caa1d464d99183d10e6fb971ac07a201e0c0c9280789559dcc81d66e4640")}
REL = "windows-x64/psxrecomp/runtime/src/"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def once(text, old, name):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{name}: anchor found {n} times (need exactly 1):\n{old[:240]}")


def apply(text, edits, name):
    for i, e in enumerate(edits):
        if e[0] == "fn":   # transform the unique span [start, end-of-end-anchor) with a function
            _, start, end, fn = e
            once(text, start, f"{name} fn {i} start")
            a = text.index(start)
            b = text.find(end, a)
            if b < 0 or b - a > 4000:
                raise SystemExit(f"{name} fn {i}: end anchor not within 4000 chars")
            b += len(end)
            text = text[:a] + fn(text[a:b]) + text[b:]
        else:
            old, new = e
            once(text, old, f"{name} edit {i}")
            text = text.replace(old, new)
    return text


# ---------------------------------------------------------------- main.cpp
def vblank_present(span):
    """sdl_vblank_present(): stamp FP_EXIT before EVERY return and at the end (explicit calls, no RAII: longjmp paths);
    wrap the netplay-epilogue pacer as ALT pacing."""
    returns = span.count("\n        return;\n")
    if returns != 4:
        raise SystemExit(f"sdl_vblank_present: expected 4 early returns, found {returns}")
    out = span.replace("\n        return;\n", "\n        { FRAME_PHASE_MARK(FP_EXIT); return; }\n")
    pace = "    if (present_should_wall_pace())\n        frame_pacer_wait(&s_frame_pacer, g_frame_period_ms);\n"
    if out.count(pace) != 1:
        raise SystemExit("sdl_vblank_present: epilogue pacer anchor")
    out = out.replace(pace, "    FRAME_PHASE_MARK(FP_ALT_PACE_BEGIN);   /* netplay epilogue pacer (after swap) */\n" + pace +
                      "    FRAME_PHASE_MARK(FP_ALT_PACE_END);\n")
    tail = "    latency_ring_mark(LAT_PACED);\n}\n"
    if not out.endswith(tail):
        raise SystemExit("sdl_vblank_present: tail anchor")
    return out[: -len(tail)] + "    latency_ring_mark(LAT_PACED);\n    FRAME_PHASE_MARK(FP_EXIT);\n}\n"


MAIN_EDITS = [
    ('#include "latency_ring.h"\n',
     '#include "latency_ring.h"\n#include "frame_phase_ring.h"   /* private v58 phase ring (opt-in PSX_FRAME_PHASE_RING=1) */\n'
     '#ifndef PSX_NO_DEBUG_TOOLS\n#define FRAME_PHASE_MARK(p) debug_server_frame_phase_mark(p)\n#else\n#define FRAME_PHASE_MARK(p) ((void)0)\n#endif\n'),
    ('static NetplayVblankEpilogue sdl_vblank_present_body(void) {\n    NetplayVblankEpilogue ep{};\n',
     'static NetplayVblankEpilogue sdl_vblank_present_body(void) {\n'
     '    FRAME_PHASE_MARK(FP_ENTER);   /* literally first: before ep init, scheduler resume clear, debug housekeeping */\n'
     '    NetplayVblankEpilogue ep{};\n'),
    ('    debug_server_check_watchpoints();\n\n    /* Check debug server input override. */\n',
     '    debug_server_check_watchpoints();\n'
     '    FRAME_PHASE_MARK(FP_DEBUG_END);   /* frame id committed here: s_frame_count after record_frame */\n\n'
     '    /* Check debug server input override. */\n'),
    ('                frame_pacer_wait(&s_frame_pacer,\n                                 g_frame_period_ms / (double)mult);\n',
     '                FRAME_PHASE_MARK(FP_ALT_PACE_BEGIN);   /* manual turbo pacer */\n'
     '                frame_pacer_wait(&s_frame_pacer,\n                                 g_frame_period_ms / (double)mult);\n'
     '                FRAME_PHASE_MARK(FP_ALT_PACE_END);\n'),
    ('            frame_pacer_wait(\n                &s_frame_pacer,\n                g_frame_period_ms / (double)g_turbo_load_wall_multiplier);\n',
     '            FRAME_PHASE_MARK(FP_ALT_PACE_BEGIN);   /* turbo-loads pacer */\n'
     '            frame_pacer_wait(\n                &s_frame_pacer,\n                g_frame_period_ms / (double)g_turbo_load_wall_multiplier);\n'
     '            FRAME_PHASE_MARK(FP_ALT_PACE_END);\n'),
    ('        if (!manual_turbo_active && !turbo_load_paced && present_should_wall_pace())\n'
     '            frame_pacer_wait(&s_frame_pacer, g_frame_period_ms);\n',
     '        FRAME_PHASE_MARK(FP_PACE_BEGIN);   /* offline wall-clock pacer: runs BEFORE present/swap */\n'
     '        if (!manual_turbo_active && !turbo_load_paced && present_should_wall_pace())\n'
     '            frame_pacer_wait(&s_frame_pacer, g_frame_period_ms);\n'
     '        FRAME_PHASE_MARK(FP_PACE_END);\n'),
    ('        const Uint64 t0 = SDL_GetPerformanceCounter();\n        SDL_RenderPresent(sdl_renderer);\n'
     '        const Uint64 t1 = SDL_GetPerformanceCounter();\n',
     '        const Uint64 t0 = SDL_GetPerformanceCounter();\n'
     '        FRAME_PHASE_MARK(FP_SWAP_BEGIN);   /* software renderer: exact present */\n'
     '        SDL_RenderPresent(sdl_renderer);\n        FRAME_PHASE_MARK(FP_SWAP_END);\n'
     '        const Uint64 t1 = SDL_GetPerformanceCounter();\n'),
    ('                        host_osd_draw_sdl(sdl_renderer);\n                        SDL_RenderPresent(sdl_renderer);\n',
     '                        host_osd_draw_sdl(sdl_renderer);\n'
     '                        FRAME_PHASE_MARK(FP_SWAP_BEGIN);   /* software renderer: blank-display present */\n'
     '                        SDL_RenderPresent(sdl_renderer);\n'
     '                        FRAME_PHASE_MARK(FP_SWAP_END);\n'),
    ("fn", "static void sdl_vblank_present(void) {\n", "    latency_ring_mark(LAT_PACED);\n}\n", vblank_present),
    ('        debug_server_init(debug_port);\n',
     '        debug_server_init(debug_port);\n'
     '        /* Private phase ring: bind this (vblank) thread as the only row writer; hook the exact GL swap only when\n'
     '         * PSX_FRAME_PHASE_RING=1, so the default build keeps a NULL hook. */\n'
     '        if (debug_server_frame_phase_init_owner())\n'
     '            gl_renderer_set_swap_phase_hook(debug_server_frame_phase_mark);\n'),
]

# ---------------------------------------------------------------- gpu_gl_renderer.c
RENDERER_EDITS = [
    ('#include "native_upload_ledger.h"\n', '#include "native_upload_ledger.h"\n#include "frame_phase_ring.h"\n'),
    ('static void gl_swap_with_osd(void) {\n    if(s_hd_research.active)',
     '/* Private v58 frame phase ring: exact SDL_GL_SwapWindow stamps through a hook set by main (NULL = nothing), so\n'
     ' * this renderer stays independent of the ring and of the debug server. */\n'
     'static void (*s_swap_phase_hook)(int) = NULL;\n'
     'void gl_renderer_set_swap_phase_hook(void (*hook)(int phase)) { s_swap_phase_hook = hook; }\n\n'
     'static void gl_swap_with_osd(void) {\n    if(s_hd_research.active)'),
    ('    SDL_GL_SwapWindow(s_win);\n}\n',
     '    if (s_swap_phase_hook) s_swap_phase_hook(FP_SWAP_BEGIN);   /* exact swap, after OSD/capture work */\n'
     '    SDL_GL_SwapWindow(s_win);\n'
     '    if (s_swap_phase_hook) s_swap_phase_hook(FP_SWAP_END);\n}\n'),
]

# ---------------------------------------------------------------- debug_server.c
RING = r'''/* FRAME_PHASE_RING BEGIN --------------------------------------------------------------------------
 * Private v58 per-vblank phase ring (opt-in PSX_FRAME_PHASE_RING=1); see frame_phase_ring.h. QPC only. Exactly one
 * row-writer thread, bound once by debug_server_frame_phase_init_owner() (a cached thread-local flag, set only when
 * enabled). mark() reads that flag FIRST: a call from any other thread, or with the ring disabled, returns before any
 * shared read or write and is not counted. All other state below is touched by the owner thread only. */
static PSX_BSS FramePhaseRecord s_fpr_ring[FRAME_PHASE_RING_CAP];   /* ~1.5 MiB, RAM-only (house rule for large rings) */
static uint64_t s_fpr_seq, s_fpr_orphans, s_fpr_unclosed;
static int s_fpr_open, s_fpr_enabled = -1, s_fpr_owner_bound;
static _Thread_local int s_fpr_is_owner;

int debug_server_frame_phase_enabled(void) {
    if (s_fpr_enabled < 0) {
        const char *v = getenv("PSX_FRAME_PHASE_RING");
        s_fpr_enabled = v && strcmp(v, "1") == 0;
    }
    return s_fpr_enabled;
}

int debug_server_frame_phase_init_owner(void) {
    if (!debug_server_frame_phase_enabled()) return 0;
    if (!s_fpr_owner_bound) { s_fpr_is_owner = 1; s_fpr_owner_bound = 1; }   /* first binder wins; later calls no-op */
    return 1;
}

void debug_server_frame_phase_mark(int phase) {
    if (!s_fpr_is_owner) return;   /* disabled, unbound, or a foreign thread: thread-local read only */
    if (phase < 0 || phase >= FP_COUNT) { s_fpr_orphans++; return; }
    const uint64_t now = SDL_GetPerformanceCounter();
    if (phase == FP_ENTER) {
        if (s_fpr_open) {   /* the previous cycle never reached EXIT (for example a longjmp path) */
            s_fpr_ring[(s_fpr_seq - 1) % FRAME_PHASE_RING_CAP].flags |= FP_FLAG_UNCLOSED;
            s_fpr_unclosed++;
        }
        FramePhaseRecord *r = &s_fpr_ring[s_fpr_seq % FRAME_PHASE_RING_CAP];
        memset(r, 0, sizeof *r);
        r->seq = s_fpr_seq;
        r->frame_at_enter = (uint32_t)s_frame_count;
        r->frame = r->frame_at_enter;
        r->t[FP_ENTER] = now;
        s_fpr_seq++;
        s_fpr_open = 1;
        return;
    }
    if (!s_fpr_open) { s_fpr_orphans++; return; }
    FramePhaseRecord *r = &s_fpr_ring[(s_fpr_seq - 1) % FRAME_PHASE_RING_CAP];
    switch (phase) {
    case FP_DEBUG_END:
        if (!r->t[phase]) { r->t[phase] = now; r->frame = (uint32_t)s_frame_count; }
        break;
    case FP_SWAP_BEGIN:
        if (r->swaps++ == 0) { r->t[phase] = now; r->frame_at_swap = (uint32_t)s_frame_count; }
        else r->flags |= FP_FLAG_MULTI_SWAP;
        break;
    case FP_ALT_PACE_BEGIN:
        if (!r->t[phase]) { r->t[phase] = now; r->flags |= FP_FLAG_ALT_PACE; }
        else r->flags |= FP_FLAG_MULTI_ALT;
        break;
    case FP_EXIT:
        r->t[phase] = now;
        r->flags |= FP_FLAG_CLOSED;
        s_fpr_open = 0;
        break;
    default:   /* first stamp wins: PACE_BEGIN/END, SWAP_END, ALT_PACE_END */
        if (!r->t[phase]) r->t[phase] = now;
        break;
    }
}

uint64_t debug_server_frame_phase_total(void) { return s_fpr_seq; }

int debug_server_frame_phase_get(uint64_t seq, FramePhaseRecord *out) {
    if (seq >= s_fpr_seq || s_fpr_seq - seq > FRAME_PHASE_RING_CAP) return 0;
    *out = s_fpr_ring[seq % FRAME_PHASE_RING_CAP];
    return 1;
}

/* FRAME_PHASE_RING END */

/* {"cmd":"frame_phase_ring","from_seq":S,"from_frame":F0,"to_frame":F1,"n":N}   n 1..2048; query AFTER timing.
 * -> {"id","ok","enabled","owner_bound","capacity","total","retained","first_seq","last_seq","last_open",
 *     "orphans","unclosed","qpc_frequency","from_frame","to_frame","scanned","returned","truncated","next_seq",
 *     "fields":[...],"rows":[[seq,frame,frame_at_enter,frame_at_swap,flags,swaps,enter,debug_end,pace_begin,
 *                             pace_end,swap_begin,swap_end,alt_pace_begin,alt_pace_end,exit],...]}
 * Raw QPC stamps (0 = absent); segments are derived offline (derive_phases.py), never here. Ring seq is not a guest
 * frame: use "frame" (s_frame_count after housekeeping). next_seq = first seq not yet scanned: pass it as from_seq.
 * The query runs inside debug_server_poll (between FP_ENTER and FP_DEBUG_END), so the newest row is the open current
 * cycle and last_open 1 is EXPECTED: consumers exclude that row; every timed row must be CLOSED. */
static void handle_frame_phase_ring(int id, const char *json)
{
    int n = json_get_int(json, "n", 1024);
    if (n < 1) n = 1;
    if (n > 2048) n = 2048;
    const int from_frame = json_get_int(json, "from_frame", 0);
    const int to_frame = json_get_int(json, "to_frame", -1);
    const int from_seq = json_get_int(json, "from_seq", -1);
    const uint64_t total = debug_server_frame_phase_total();
    const uint64_t first = total > FRAME_PHASE_RING_CAP ? total - FRAME_PHASE_RING_CAP : 0;
    uint64_t seq = (from_seq >= 0 && (uint64_t)from_seq > first) ? (uint64_t)from_seq : first;
    const int rowsz = 64 + n * 384;
    char *rows = (char *)malloc((size_t)rowsz);
    if (!rows) { send_err(id, "alloc failed"); return; }
    int pos = 0, returned = 0, truncated = 0;
    uint64_t scanned = 0;
    rows[0] = 0;
    for (; seq < total; seq++) {
        FramePhaseRecord r;
        if (!debug_server_frame_phase_get(seq, &r)) continue;
        if ((from_frame > 0 && r.frame < (uint32_t)from_frame) ||
            (to_frame >= 0 && r.frame > (uint32_t)to_frame)) { scanned++; continue; }
        if (returned == n) { truncated = 1; break; }
        scanned++;
        const int room = rowsz - pos;
        const int w = snprintf(rows + pos, (size_t)room,
                               "%s[%llu,%u,%u,%u,%u,%u,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu]",
                               returned ? "," : "", (unsigned long long)r.seq, r.frame, r.frame_at_enter,
                               r.frame_at_swap, r.flags, r.swaps,
                               (unsigned long long)r.t[FP_ENTER], (unsigned long long)r.t[FP_DEBUG_END],
                               (unsigned long long)r.t[FP_PACE_BEGIN], (unsigned long long)r.t[FP_PACE_END],
                               (unsigned long long)r.t[FP_SWAP_BEGIN], (unsigned long long)r.t[FP_SWAP_END],
                               (unsigned long long)r.t[FP_ALT_PACE_BEGIN], (unsigned long long)r.t[FP_ALT_PACE_END],
                               (unsigned long long)r.t[FP_EXIT]);
        if (w < 0 || w >= room) { free(rows); send_err(id, "frame_phase_ring: row buffer overflow"); return; }
        pos += w;
        returned++;
    }
    FramePhaseRecord last;
    const int last_open = total && debug_server_frame_phase_get(total - 1, &last) && !(last.flags & FP_FLAG_CLOSED);
    send_fmt("{\"id\":%d,\"ok\":true,\"enabled\":%d,\"owner_bound\":%d,\"capacity\":%d,"
             "\"total\":%llu,\"retained\":%llu,\"first_seq\":%llu,\"last_seq\":%lld,\"last_open\":%d,"
             "\"orphans\":%llu,\"unclosed\":%llu,\"qpc_frequency\":%llu,\"from_frame\":%d,\"to_frame\":%d,"
             "\"scanned\":%llu,\"returned\":%d,\"truncated\":%d,\"next_seq\":%llu,"
             "\"fields\":[\"seq\",\"frame\",\"frame_at_enter\",\"frame_at_swap\",\"flags\",\"swaps\",\"enter\","
             "\"debug_end\",\"pace_begin\",\"pace_end\",\"swap_begin\",\"swap_end\",\"alt_pace_begin\","
             "\"alt_pace_end\",\"exit\"],\"rows\":[%s]}",
             id, debug_server_frame_phase_enabled(), s_fpr_owner_bound, FRAME_PHASE_RING_CAP,
             (unsigned long long)total, (unsigned long long)(total - first), (unsigned long long)first,
             total ? (long long)(total - 1) : -1LL, last_open, (unsigned long long)s_fpr_orphans,
             (unsigned long long)s_fpr_unclosed, (unsigned long long)SDL_GetPerformanceFrequency(), from_frame,
             to_frame, (unsigned long long)scanned, returned, truncated, (unsigned long long)seq, rows);
    free(rows);
}

'''

DEBUG_EDITS = [
    ('#include "native_upload_ledger.h"\n', '#include "native_upload_ledger.h"\n#include "frame_phase_ring.h"\n'),
    ('/* Present-classification ring (all backends; see present_ring.h): how each\n',
     RING + '/* Present-classification ring (all backends; see present_ring.h): how each\n'),
    ('    { "native_upload_selftest", handle_native_upload_selftest },\n',
     '    { "native_upload_selftest", handle_native_upload_selftest },\n'
     '    { "frame_phase_ring",  handle_frame_phase_ring },\n'),
]


def main():
    out, diffs = HERE / "new", HERE / "diffs"
    out.mkdir(exist_ok=True)
    diffs.mkdir(exist_ok=True)
    receipt = {}
    for name, edits in (("main.cpp", MAIN_EDITS), ("gpu_gl_renderer.c", RENDERER_EDITS), ("debug_server.c", DEBUG_EDITS)):
        base, want = BASES[name]
        raw = base.read_bytes()
        if sha(raw) != want:
            raise SystemExit(f"{name}: base hash {sha(raw)} != pinned {want}")
        text = raw.decode("utf-8")
        crlf = "\r\n" in text
        norm = text.replace("\r\n", "\n")
        new = apply(norm, edits, name)
        (out / name).write_bytes((new.replace("\n", "\r\n") if crlf else new).encode("utf-8"))
        d = "".join(difflib.unified_diff(norm.splitlines(keepends=True), new.splitlines(keepends=True),
                                         fromfile="a/" + REL + name, tofile="b/" + REL + name))
        (diffs / (name + ".diff")).write_text(d, encoding="utf-8", newline="\n")
        receipt[name] = dict(base=str(base), base_sha256=want, base_crlf=crlf, new_sha256=sha((out / name).read_bytes()),
                             diff_sha256=sha(d.encode("utf-8")), edits=len(edits))
    for hdr in ("frame_phase_ring.h",):
        b = (HERE / hdr).read_bytes()
        (out / hdr).write_bytes(b)
        receipt[hdr] = dict(new_sha256=sha(b), new_file=True, target=REL + hdr)
    for dep in ("native_upload_ledger.h",):
        b = (V57 / dep).read_bytes()
        (out / dep).write_bytes(b)
        receipt[dep + " (unchanged v57 dependency, copied for include resolution)"] = dict(sha256=sha(b))
    (HERE / "patch-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
