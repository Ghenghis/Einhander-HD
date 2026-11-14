#ifndef EINHD_SCENE_RUNTIME_H
#define EINHD_SCENE_RUNTIME_H
#include "scene_capture.h"
#ifdef __cplusplus
extern "C" {
#endif
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
