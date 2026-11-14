/* Private Windows adapter. Only GPU command/frame paths initialize it.
 * RPC entry points cannot claim ownership or race mutable initialization. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "scene_runtime.h"
#include <atomic>
#include <mutex>
#include <cstdlib>
#include <cstring>
namespace {
std::once_flag once;
std::atomic<uint32_t> owner{0},owner_errors{0};
bool enabled;
void initialize_emu() {
    std::call_once(once,[]{
        const char *v=std::getenv("PSXRECOMP_SCENE_CAPTURE");
        const bool requested=v&&std::strcmp(v,"1")==0;
        const SceneCaptureSource source{pgxp_get_precise_vertex_view,gte_rtp_ring_get_xform};
        enabled=scene_capture_init(GetCurrentThreadId(),requested?1:0,&source)==SCENE_OK&&requested;
        owner.store(GetCurrentThreadId(),std::memory_order_release);
    });
}
int guard() {
    const uint32_t bound=owner.load(std::memory_order_acquire);
    if(!bound)return SCENE_BAD_STATE;
    if(bound!=GetCurrentThreadId()){owner_errors.fetch_add(1,std::memory_order_relaxed);return SCENE_WRONG_THREAD;}
    return SCENE_OK;
}
}
extern "C" void scene_runtime_command(uint32_t frame,const uint32_t *words,int count,const uint32_t *word_sources,const SceneDrawState *state) {
    initialize_emu();if(guard()==SCENE_OK&&enabled)scene_capture_command(GetCurrentThreadId(),frame,words,count,word_sources,state);
}
extern "C" void scene_runtime_tick(uint32_t frame) {initialize_emu();if(guard()==SCENE_OK&&enabled)scene_capture_tick(GetCurrentThreadId(),frame);}
/* Called exclusively from gpu.c's emulation path, before collecting a word. */
extern "C" int scene_runtime_enabled(void) {initialize_emu();return guard()==SCENE_OK&&enabled?1:0;}
extern "C" void scene_runtime_invalidate(void) {if(guard()==SCENE_OK&&enabled)scene_capture_cancel(GetCurrentThreadId());}
extern "C" int scene_runtime_arm(uint32_t frame) {
    if(int e=guard())return e;
    if(!enabled)return SCENE_BAD_STATE;
    if(!pgxp_enabled()||!pgxp_view_payload())return SCENE_PROVENANCE_UNAVAILABLE;
    return scene_capture_arm(GetCurrentThreadId(),frame);
}
extern "C" int scene_runtime_cancel(void) {if(int e=guard())return e;return scene_capture_cancel(GetCurrentThreadId());}
extern "C" int scene_runtime_info(SceneCaptureInfo *out) {
    if(int e=guard())return e;int rc=scene_capture_info(GetCurrentThreadId(),out);
    if(rc==SCENE_OK)out->owner_errors=owner_errors.load(std::memory_order_relaxed);return rc;
}
extern "C" int scene_runtime_json(uint32_t index,uint32_t generation,char *out,size_t capacity) {
    if(int e=guard())return e;return scene_capture_json(GetCurrentThreadId(),index,generation,out,capacity);
}
