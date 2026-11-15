#ifndef EINHD_SCENE_RUNTIME_H
#define EINHD_SCENE_RUNTIME_H
#include "scene_capture.h"
#include "scene_ledger.r3.h"   /* PRIVATE glue r3 (claude-einhander), source only: ledger r3 = r0 + r1 + r2 + correction */
#ifdef __cplusplus
extern "C" {
#endif
/* Ledger r0: same hook and frames as scene_runtime_command; state may be NULL only for the polyline header. */
void scene_runtime_ledger_command(uint32_t frame,const uint32_t *words,int count,const SceneLedgerState *state);
int scene_runtime_ledger_header(SceneLedgerHeader *out);
int scene_runtime_ledger_get(uint32_t index,uint32_t generation,SceneLedgerEntry *out);
/* gpu.c: 1 while a CPU->VRAM payload or a polyline body is being consumed (gp0_state). */
int gpu_scene_gp0_open(void);
/* Glue r1 (T2 r4 liveness duties). Owner-only unless stated. */
int scene_runtime_ledger_policy(uint32_t generation,const uint32_t *ordinals,uint32_t count,SceneLedgerVerdict *out);
uint64_t scene_runtime_armed_epoch(void);                 /* 0 = no generation bound */
void scene_runtime_note_external_vram_write(void);        /* any thread */
/* Glue r2: complete raw GP1 scanout state: display start x/y, h range x1/x2, v range y1/y2, packed mode bits
 * (hres1, hres2, vres, video mode, depth, interlace, reverse), disable. */
enum { SCENE_SCANOUT_WORDS = 8 };
void gpu_scene_scanout_state(uint32_t s[SCENE_SCANOUT_WORDS]);   /* gpu.c, emulation owner */
/* gpu.c GP1(03/05/06/07/08), emulation owner. Glue r3: T2 r6 PresentState::observe_scanout; every change except
 * the bound candidate's exact expected flip (and every first observation) bumps the epoch. */
void scene_runtime_scanout_changed(const uint32_t s[SCENE_SCANOUT_WORDS]);
/* Glue r3, owner only: ledger r1 display hazard and ledger r2 drawing-area constancy of the sealed generation. */
int scene_runtime_ledger_display_hazard(uint32_t generation,const uint32_t *ordinals,uint32_t count,const int32_t rect[4],
                                        SceneLedgerVerdict *out);
int scene_runtime_ledger_draw_area(uint32_t generation,uint32_t *constant,uint16_t area[4]);
/* Owner-only copy of one record of the SEALED, complete capture generation (scene_capture_get). */
int scene_runtime_capture_get(uint32_t index,uint32_t generation,ScenePrimitive *out);
void scene_runtime_command(uint32_t frame,const uint32_t *words,int count,const uint32_t *word_sources,const SceneDrawState *state);
void scene_runtime_tick(uint32_t frame);
int scene_runtime_enabled(void);
void scene_runtime_invalidate(void);
int scene_runtime_arm(uint32_t frame);
int scene_runtime_cancel(void);
int scene_runtime_info(SceneCaptureInfo *out);
int scene_runtime_json(uint32_t index,uint32_t generation,char *out,size_t capacity);
#ifdef __cplusplus
}
#endif
#endif
