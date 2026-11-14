/* Private native VRAM upload ledger and PBO-stream status (opt-in; see native-upload-stream/DESIGN.md).
 *   PSXRECOMP_NATIVE_UPLOAD_LEDGER=1  per-rect CPU-side QPC totals plus a ring of SLOW rects (total > 1 ms)
 *   PSXRECOMP_GL_UPLOAD_PBO=1         flush_cpu_upload() streams each rect through an orphaned PIXEL_UNPACK buffer
 * Both are exact "1", read once. Ticks are CPU-side SDL_GetPerformanceCounter deltas only; deferred GPU work is not
 * measured. Producer (renderer) and readers (debug commands) run on the main thread.
 * This is a separate ABI: GlHdCpuProfile, the hd upload ledger and the runtime-perf up[6] counters are unchanged. */
#ifndef NATIVE_UPLOAD_LEDGER_H
#define NATIVE_UPLOAD_LEDGER_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GL_NATIVE_UPLOAD_LEDGER_CAP 2048

enum { GL_NATIVE_UPLOAD_MODE_CLIENT = 0, GL_NATIVE_UPLOAD_MODE_PBO = 1, GL_NATIVE_UPLOAD_MODE_FALLBACK = 2 };

typedef struct {
    uint32_t frame;            /* renderer s_frame_count */
    uint32_t flush_seq;        /* flush_cpu_upload call number (0 = self-test) */
    uint16_t x, y, w, h;
    uint16_t rect_index, rects_in_flush;
    uint8_t  mode, reserved[3];
    uint64_t staging_ticks;      /* ON only: tight R16 copy + BufferData(orphan) + 2x BufferSubData */
    uint64_t state_ticks;        /* every glBindTexture / glPixelStorei / PIXEL_UNPACK bind+unbind in the helper */
    uint64_t rgba_upload_ticks;  /* the RGBA8 glTexSubImage2D call alone */
    uint64_t raw_upload_ticks;   /* the R16UI glTexSubImage2D call alone */
    uint64_t total_ticks;        /* whole native_upload_rect() */
} GlNativeUploadEvent;

typedef struct {
    uint64_t rects, pbo_rects, fallback_rects, slow_events;
    uint64_t staging_ticks, state_ticks, rgba_upload_ticks, raw_upload_ticks, total_ticks;
    uint64_t max_total_ticks;
    uint32_t max_total_frame;
} GlNativeUploadTotals;

int         gl_renderer_native_upload_ledger_enabled(void);
int         gl_renderer_native_upload_pbo_requested(void);
int         gl_renderer_native_upload_pbo_state(const char **reason); /* 0 not tried, 1 ready, -1 unavailable */
uint64_t    gl_renderer_native_upload_slow_total(void);
int         gl_renderer_native_upload_slow_get(uint64_t seq, GlNativeUploadEvent *out);
void        gl_renderer_native_upload_totals(GlNativeUploadTotals *out);
/* GPU self-test on private textures; writes JSON object members (no braces) into out. Returns 1 when ok. */
int         gl_renderer_native_upload_selftest(char *out, size_t cap);

#ifdef __cplusplus
}
#endif

#endif /* NATIVE_UPLOAD_LEDGER_H */
