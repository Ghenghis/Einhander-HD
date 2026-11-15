#ifndef EINHD_SCENE_CAPTURE_H
#define EINHD_SCENE_CAPTURE_H
/* Diagnostic CPU snapshot only. No SDK calls, file I/O or guest state writes. */
#include "pgxp.h"
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
enum { SCENE_CAPACITY = 1024, SCENE_WORDS = 12 };
enum { SCENE_DISABLED, SCENE_IDLE, SCENE_ARMED, SCENE_RECORDING, SCENE_SEALED };
enum { SCENE_OK, SCENE_WRONG_THREAD, SCENE_BAD_STATE, SCENE_BAD_ARGUMENT };
enum { SCENE_VERTEX_OK, SCENE_IMMEDIATE, SCENE_LOOKUP_MISS, SCENE_WORD_MISMATCH,
       SCENE_STALE, SCENE_UNCOMMITTED, SCENE_DIVERGED, SCENE_COMMAND,
       SCENE_TRANSFORM_MISSING, SCENE_TRANSFORM_FRAME, SCENE_TRANSFORM_HASH,
       SCENE_MAC_MISMATCH, SCENE_MIXED_TRANSFORM, SCENE_INVALID_ADDRESS };
typedef struct SceneDrawState {
    uint32_t texture_window;
    int32_t draw_offset_x, draw_offset_y;
    uint16_t draw_left, draw_top, draw_right, draw_bottom;
    uint8_t set_mask, check_mask;
} SceneDrawState;
typedef struct SceneVertex {
    PgxpView view;
    int16_t rt[9];
    int32_t tr[3];
    uint32_t address, packet_word, rgb, caller_ra;
    uint8_t u, v, reason, lag;
} SceneVertex;
typedef struct ScenePrimitive {
    SceneDrawState state;
    SceneVertex vertex[4];
    uint32_t words[SCENE_WORDS], word_sources[SCENE_WORDS], source_address, frame, ordinal;
    uint16_t clut, tpage;
    uint8_t word_count, nverts, opcode, depth, blend_mode, raw_texture, semi_trans, qualified;
    uint8_t triangle_count, indices[6]; /* native quad: 0,1,2, 2,1,3 */
} ScenePrimitive;
typedef struct SceneCaptureInfo {
    uint32_t mode, frame, count, capacity, textured_seen, malformed, overflow;
    uint32_t qualified, missing_vertices, other_commands;
    uint8_t complete; /* complete command stream interval, NOT full renderer coverage */
} SceneCaptureInfo;
typedef struct SceneCaptureSource {
    int (*lookup)(uint32_t, uint32_t, PgxpView *);
    int (*transform)(uint64_t, int16_t[9], int32_t[3], uint32_t *, uint32_t *);
} SceneCaptureSource;
/* Bind one immutable owner thread and source once. token must be actual host
 * thread ID in runtime glue. Wrong-thread callers touch no non-atomic state.
 * enabled must be exactly 0/1. A disabled capture has no per-command work. */
int scene_capture_init(uint32_t token, int enabled, const SceneCaptureSource *source);
int scene_capture_arm(uint32_t token, uint32_t current_frame);
int scene_capture_cancel(uint32_t token);
/* Called at EVERY fully collected GP0 command, before dispatch. Arm waits for
 * the first observed frame transition; the following transition seals it.
 * Empty frames need explicit tick calls from the same emulation owner thread. */
int scene_capture_tick(uint32_t token, uint32_t frame);
int scene_capture_command(uint32_t token, uint32_t frame, const uint32_t *words,
                          int count, const uint32_t *word_sources, const SceneDrawState *state);
int scene_capture_info(uint32_t token, SceneCaptureInfo *out);
/* Copy only a sealed record; never expose mutable internal pointers. */
int scene_capture_get(uint32_t token, uint32_t index, ScenePrimitive *out);
/* Read-side, one bounded JSON record. Failure empties caller output. */
int scene_capture_json(uint32_t token, uint32_t index, char *out, size_t capacity);
#ifdef __cplusplus
}
#endif
#endif
