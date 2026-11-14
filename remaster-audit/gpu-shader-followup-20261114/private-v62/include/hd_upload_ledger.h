/* Private HD replacement upload ledger (diagnostic, opt-in PSXRECOMP_HD_UPLOAD_LEDGER=1).
 *
 * One fixed-ring entry per replacement glTexImage2D issued by hd_tex_object() in
 * gpu_gl_renderer.c. The entry holds the guest frame, the key, the dimensions and bytes, the
 * CPU-side QPC ticks of the upload call, and the slot it displaced. The debug command
 * "hd_upload_ledger" reads it AFTER timing.
 *
 * The ledger does no readback, file IO, GL query, glFinish, decode wait or rendering change. When it
 * is disabled, each hd_tex_object call costs one cached branch. Every tick field brackets CPU-side calls
 * only: the driver may defer the copy or allocation to a later point (often the swap), so a small value
 * does not prove a cheap upload and the GPU cost is NOT measured.
 * Producer (renderer) and reader (debug command) both run on the main thread.
 *
 * Kept separate from GlHdCpuProfile so that profile's ABI does not change. */
#ifndef HD_UPLOAD_LEDGER_H
#define HD_UPLOAD_LEDGER_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GL_HD_UPLOAD_LEDGER_CAP 2048 /* about 1,000 uploads by frame 9600 in v54, so this keeps boot through boss end */

enum {
    GL_HD_UPLOAD_EVICTED_LIVE_SLOT    = 1, /* the LRU slot reused for this upload held a live texture */
    GL_HD_UPLOAD_FACADE_SLOT_RECYCLED = 2, /* facade-mip slot was released and regenerated */
    GL_HD_UPLOAD_SAME_KEY_REUPLOAD    = 4  /* key already had a slot; pixels pointer or size changed */
};

typedef struct {
    uint32_t frame;                 /* renderer s_frame_count at the upload */
    uint32_t texture_hash, palette_hash;
    uint32_t evicted_texture_hash;  /* valid when flags & GL_HD_UPLOAD_EVICTED_LIVE_SLOT */
    uint32_t evicted_palette_hash;
    uint32_t bytes;                 /* width * height * 4 (RGBA8 level 0) */
    uint32_t emissive_bytes;        /* R8 mask bytes uploaded with it, 0 if none */
    uint64_t upload_ticks;          /* SDL_GetPerformanceCounter delta around the RGBA glTexImage2D */
    uint64_t emissive_ticks;        /* same around the R8 emissive glTexImage2D, 0 if none */
    uint64_t total_ticks;           /* whole hd_tex_object(): entry (before flush_hd_batch) to just before return,
                                       covering batch flush, slot delete/gen, both uploads and parameter state */
    uint16_t width, height, slot;
    uint8_t  flags, reserved;
} GlHdUploadEvent;

unsigned gl_renderer_hd_gpu_cache_slots(void);
uint64_t gl_renderer_hd_gpu_cache_budget(void);
uint64_t gl_renderer_hd_gpu_cache_bytes(void);
int      gl_renderer_hd_upload_ledger_enabled(void);
uint64_t gl_renderer_hd_upload_total(void);
uint64_t gl_renderer_hd_upload_qpc_frequency(void);
int      gl_renderer_hd_upload_get(uint64_t seq, GlHdUploadEvent *out);

#ifdef __cplusplus
}
#endif

#endif /* HD_UPLOAD_LEDGER_H */
