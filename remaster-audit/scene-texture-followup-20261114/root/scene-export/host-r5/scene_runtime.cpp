/* Private Windows adapter. Every entry is called on the emulation owner thread. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "scene_runtime.h"
#include <cstdlib>
#include <cstring>
namespace {
bool booted,enabled;
void boot() {
    if(booted)return;
    const char *v=std::getenv("PSXRECOMP_SCENE_CAPTURE");enabled=v&&std::strcmp(v,"1")==0;
    const SceneCaptureSource source{pgxp_get_precise_vertex_view,gte_rtp_ring_get_xform};
    if(scene_capture_init(GetCurrentThreadId(),enabled?1:0,&source)!=SCENE_OK)enabled=false;
    booted=true;
}
}
extern "C" void scene_runtime_command(uint32_t frame,const uint32_t *words,int count,const uint32_t *word_sources,const SceneDrawState *state) {
    boot();if(enabled)scene_capture_command(GetCurrentThreadId(),frame,words,count,word_sources,state);
}
extern "C" void scene_runtime_tick(uint32_t frame) {boot();if(enabled)scene_capture_tick(GetCurrentThreadId(),frame);}
extern "C" int scene_runtime_enabled(void) {boot();return enabled?1:0;}
extern "C" void scene_runtime_invalidate(void) {if(booted&&enabled)scene_capture_cancel(GetCurrentThreadId());}
extern "C" int scene_runtime_arm(uint32_t frame) {boot();return scene_capture_arm(GetCurrentThreadId(),frame);}
extern "C" int scene_runtime_cancel(void) {boot();return scene_capture_cancel(GetCurrentThreadId());}
extern "C" int scene_runtime_info(SceneCaptureInfo *out) {boot();return scene_capture_info(GetCurrentThreadId(),out);}
extern "C" int scene_runtime_json(uint32_t index,char *out,size_t capacity) {boot();return scene_capture_json(GetCurrentThreadId(),index,out,capacity);}
