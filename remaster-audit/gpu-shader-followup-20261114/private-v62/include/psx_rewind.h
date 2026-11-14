#ifndef PSX_REWIND_H
#define PSX_REWIND_H

/*
 * Local rewind ring + bottom filmstrip overlay (host only).
 *
 * Uses retcomm-rbengine snap_ring + boot_state blobs. Separate from netplay
 * g_snaps. Disabled while psx_netplay_active().
 *
 * Keyboard: F8 (config.ini [KeyMap] Rewind). Controller: View/Back or L3.
 * While open: D-pad / left-stick Left/Right, Cross load, Circle/Back close.
 *
 * Env: PSX_REWIND=0 disables; PSX_REWIND_INTERVAL (1/4/8/12/15, default 15);
 *      PSX_REWIND_FMV_INTERVAL (frames while an MDEC movie plays, default 4;
 *      never sparser than the user interval);
 *      PSX_REWIND_FMV_LEGACY=1 (A/B only: old depth24/MDEC/XA media rule);
 *      PSX_REWIND_DEPTH (50/100/150/200, default 50, max 200).
 * settings.toml [video] rewind_depth / rewind_interval (env still wins).
 */

#include <stdint.h>
#include "cpu_state.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Snap count kept in the local rewind ring. UI values: 25 / 50 / 75 / 100. */
void psx_rewind_set_depth(uint32_t depth);
void psx_rewind_set_interval(uint32_t interval);

void psx_rewind_configure(uint32_t bios_checksum, uint32_t entry_pc);
void psx_rewind_shutdown(void);

int  psx_rewind_enabled(void);
int  psx_rewind_is_open(void);
/* 1 while open or slide animation still visible. */
int  psx_rewind_needs_present(void);

/* Guest vblank: bump frame counter / schedule capture when not paused. */
void psx_rewind_note_frame(void);

/* Safe BB-edge (beside savestate_poll): capture due snap / apply load. */
void psx_rewind_poll(CPUState *cpu, uint32_t resume_pc);

int  psx_rewind_toggle(void);          /* open/close; 1 if state changed */
int  psx_rewind_cancel(void);          /* close without load */
int  psx_rewind_accept(void);          /* stage load of selected snap */
void psx_rewind_move(int delta);       /* -1 / +1 selection */

/* Edge-triggered nav with repeat. *_down is 1 while held. */
void psx_rewind_nav_held(int left_down, int right_down, int accept_down,
                         int cancel_down, uint32_t now_ms);

void psx_rewind_present_tick(uint32_t now_ms);

/* Bottom-panel ARGB8888 (little-endian). Valid until next rewind call. */
int  psx_rewind_overlay_image(const uint32_t **pixels, int *w, int *h);
/* 0..1 slide (0 = off-screen below, 1 = docked). */
float psx_rewind_slide(void);

/* Host-only capture diagnostics (debug server "rewind_stats"). Cumulative
 * since process start or the last reset; never serialized, never digested.
 * A capture request is a sticky flag: once due it is retried at every
 * rewind poll until one succeeds, so `attempts` counts polls, not requests. */
typedef struct PsxRewindStats {
    int      enabled;            /* psx_rewind_enabled() */
    int      media_now;          /* movie classification at query time */
    int      capture_due;        /* a capture is pending right now */
    uint32_t interval;           /* user interval (frames) */
    uint32_t fmv_interval;       /* movie interval (frames) */
    uint32_t effective_interval; /* interval in force at query time */
    uint32_t depth, count;       /* ring depth / snaps held now */
    uint32_t frame, last_capture_frame;
    uint64_t frames;             /* vblanks counted by note_frame */
    uint64_t media_frames;       /* ...of which classified as movie */
    uint64_t due_edges;          /* capture requests raised (0 -> 1) */
    uint64_t due_frames;         /* vblanks that ended with a request pending */
    uint64_t attempts;           /* do_capture entries (one per due poll) */
    uint64_t skip_no_ring;       /* no CPU / ring */
    uint64_t skip_unsafe;        /* dirty-RAM pump site: not snapshot-safe */
    uint64_t skip_pc;            /* no dispatchable resume PC */
    uint64_t skip_save;          /* boot_state_save_buffer_raw failed */
    uint64_t skip_store;         /* rbe_snap_ring_store failed */
    uint64_t taken;              /* captures stored */
    uint64_t taken_media;        /* ...while classified as movie */
    uint64_t save_us_total, save_us_max;       /* boot_state_save_buffer_raw
                                                  (includes the GPU->CPU VRAM sync) */
    uint64_t capture_us_total, capture_us_max; /* whole successful do_capture */
    uint64_t last_blob_bytes;
    uint64_t latency_frames_total, latency_frames_max; /* request -> stored */
} PsxRewindStats;

void psx_rewind_stats_get(PsxRewindStats *out);
void psx_rewind_stats_reset(void);

#ifdef __cplusplus
}
#endif

#endif /* PSX_REWIND_H */
