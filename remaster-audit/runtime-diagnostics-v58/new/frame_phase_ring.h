/* Private per-vblank frame PHASE ring (diagnostic, opt-in PSX_FRAME_PHASE_RING exactly "1", read once).
 *
 * One row per sdl_vblank_present() cycle, holding raw QPC stamps at the cycle's actual ordered boundaries:
 *   FP_ENTER       literally the first statement of sdl_vblank_present_body(): before the NetplayVblankEpilogue
 *                  initialization, psx_scheduler_top_level_resume_clear() and the debug wait/poll/record/watchpoints
 *   FP_DEBUG_END   after debug_server_check_watchpoints()            (the frame id is committed here: s_frame_count
 *                                                                     AFTER debug_server_record_frame's increment)
 *   FP_PACE_BEGIN  immediately before the offline wall-clock pacer
 *   FP_PACE_END    immediately after it                              (the pacer runs BEFORE present/swap)
 *   FP_SWAP_BEGIN  immediately before SDL_GL_SwapWindow inside gl_swap_with_osd (exact; not the LAT_SWAP wrapper,
 *                  which also covers OSD/capture). For the software renderer: around SDL_RenderPresent.
 *   FP_SWAP_END    immediately after it
 *   FP_ALT_PACE_BEGIN/END  any other pacer (manual turbo, turbo-loads, netplay epilogue): stamped and flagged only
 *   FP_EXIT        every return of sdl_vblank_present()              (after the epilogue)
 * The server stores and returns raw stamps only (0 = absent). Segments are derived OFFLINE (derive_phases.py):
 *   outside_vblank = ENTER(n) - EXIT(n-1)   guest execution PLUS anything else between vblank callbacks. This is not
 *                                           pure emulation; post-load probes and destructors run inside the cycle.
 *   housekeeping   = DEBUG_END - ENTER      debug wait/poll/record/watchpoints
 *   pre_pace       = PACE_BEGIN - DEBUG_END
 *   pace           = PACE_END - PACE_BEGIN
 *   present_prep   = SWAP_BEGIN - (PACE_END or DEBUG_END)
 *   swap           = SWAP_END - SWAP_BEGIN  the exact SDL swap call
 *   post           = EXIT - (SWAP_END or the last earlier stamp)
 * QPC only: no GL calls, queries, fences or readbacks; no threads. A cycle that never reaches EXIT (longjmp paths) is
 * flagged UNCLOSED when the next one opens. Precise decomposition uses CLOSED rows without UNCLOSED, MULTI_SWAP or
 * MULTI_ALT. The query handler runs inside debug_server_poll (between FP_ENTER and FP_DEBUG_END), so the newest row is
 * the open current cycle (last_open 1 is expected): consumers exclude it.
 *
 * Thread scope (explicit, not generic). Only the thread bound by debug_server_frame_phase_init_owner() writes rows or
 * ring state. That call resolves the env gate and binds a cached thread-local flag on the main (vblank) thread, right
 * after debug_server_init and BEFORE the renderer swap hook is registered. mark() reads only that thread-local flag
 * first: a call from any other thread, or with the ring disabled, returns before any shared read or write and is not
 * counted. Owner-thread marks outside an open cycle count as "orphans". Supported measurement scope: offline play,
 * PSX_FRAME_INTERPOLATION=0, netplay off; ALT_PACE or MULTI_SWAP flags show a run that left that scope. */
#ifndef FRAME_PHASE_RING_H
#define FRAME_PHASE_RING_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#ifndef FRAME_PHASE_RING_CAP
#define FRAME_PHASE_RING_CAP 16384   /* about 4.5 min at 60 Hz: a whole 120 s pass plus boot */
#endif

enum {
    FP_ENTER = 0, FP_DEBUG_END, FP_PACE_BEGIN, FP_PACE_END, FP_SWAP_BEGIN, FP_SWAP_END,
    FP_ALT_PACE_BEGIN, FP_ALT_PACE_END, FP_EXIT, FP_COUNT
};
enum {
    FP_FLAG_CLOSED = 1, FP_FLAG_UNCLOSED = 2, FP_FLAG_MULTI_SWAP = 4, FP_FLAG_ALT_PACE = 8, FP_FLAG_MULTI_ALT = 16
};

typedef struct {
    uint64_t seq;            /* ring sequence (one per vblank cycle); NOT a guest frame */
    uint32_t frame;          /* s_frame_count after housekeeping (the id the present ring and get_registers report) */
    uint32_t frame_at_enter; /* s_frame_count at body entry, kept for audit */
    uint32_t frame_at_swap;  /* s_frame_count at the first swap of the cycle */
    uint16_t flags, swaps;
    uint64_t t[FP_COUNT];    /* raw QPC; 0 means absent */
} FramePhaseRecord;

void     debug_server_frame_phase_mark(int phase);   /* one thread-local read unless bound and enabled */
int      debug_server_frame_phase_enabled(void);
/* Call once on the vblank (main) thread before registering any hook: resolves the env gate and binds that thread as
 * the only row writer. Returns enabled. Without this call no rows are recorded (the query reports owner_bound 0). */
int      debug_server_frame_phase_init_owner(void);
uint64_t debug_server_frame_phase_total(void);
int      debug_server_frame_phase_get(uint64_t seq, FramePhaseRecord *out);
/* Renderer swap hook (set by main), so the GL renderer stays independent of the ring and the debug server. */
void     gl_renderer_set_swap_phase_hook(void (*hook)(int phase));

#ifdef __cplusplus
}
#endif

#endif /* FRAME_PHASE_RING_H */
