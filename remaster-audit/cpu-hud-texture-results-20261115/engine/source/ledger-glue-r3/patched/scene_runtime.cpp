/* Private Windows adapter. Only GPU command/frame paths initialize it.
 * RPC entry points cannot claim ownership or race mutable initialization. */
/* PRIVATE ledger glue r3 (claude-einhander, source-only proposal; root msg_b02d1bcc / msg_08008ad5, design 19db18ce):
 * glue r2 (3bbc6821) wired to the T2 r6 owned present lifecycle (419dea94) through bridge r3, with ledger r2:
 *  - arm: the first scanout observation if none yet (that bumps), then capture_begin, which does NOT bump: an
 *    ordinary N+1 capture leaves the owned pending/displayed frame alive. Reference mode while PGXP payload or the
 *    ledger is unavailable (recovery never revives a retired record: eligibility needs a new sealed frame);
 *  - GP1: PresentState::observe_scanout replaces r2's blanket invalidation; only the bound candidate's exact
 *    expected flip skips the epoch bump (r2's raw-state snapshot fields are gone: the PresentState owns them);
 *  - every collected GP0 command, in any ledger mode: after the ledger hook (and the seal hand-off it may trigger),
 *    its pure ledger r2 footprint retires overlapped present records; an unknown footprint retires all;
 *  - seal: once capture AND ledger sealed the armed generation, the producer runs once (boundary, build, bind,
 *    publish); an incomplete seal retires everything and bumps the epoch (root decision 3);
 *  - cancel, owner reset, savestate: retire all + epoch; a foreign thread: epoch only (owner retires at boundary).
 * gpu.c is unchanged from glue r2 (de9dfd77): capture hook (:5160) then ledger hook (:5162) per GP0 command.
 * Glue r2 notes follow.
 * PRIVATE ledger glue r2 (claude-einhander, source-only proposal; r1 + root msg_25d45f15 fixes: complete raw
 * scanout state with an arm-time snapshot, owner-only sealed record getter for the producer).
 * Glue r1 on top of glue r0, for T2 r4 (eebb2c8f):
 *  - every guard failure, on ANY entry point and ANY foreign thread, is reported to the ledger's atomic counter
 *    and to the T2 liveness (note_foreign), not only on enabled/tick (root msg_fb74eece);
 *  - reset/savestate invalidate always bumps the T2 epoch and marks the ledger external, whatever the thread;
 *  - a successful capture+ledger arm binds a fresh T2 epoch; cancel and a refused ledger arm invalidate;
 *  - explicit entry points for external VRAM writes and native displayed-area changes;
 *  - owner-only pass-throughs used by the T2 producer bridge (epoch, ledger policy). */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "scene_runtime.h"
#include "scene_t2_bridge.r3.h"
#include <atomic>
#include <mutex>
#include <cstdlib>
#include <cstring>
namespace {
std::once_flag once;
std::atomic<uint32_t> owner{0},owner_errors{0};
bool enabled, ledger_enabled;   /* both written before owner's release store, read only after its acquire */
uint64_t armed_epoch;           /* owner thread only: T2 epoch bound to the current capture generation, 0 = none */
uint32_t armed_generation;      /* owner only (r3): capture generation armed with a bound epoch, 0 = none */
uint32_t built_generation;      /* owner only (r3): last generation handed to the producer */
void initialize_emu() {
    std::call_once(once,[]{
        const char *v=std::getenv("PSXRECOMP_SCENE_CAPTURE");
        const bool requested=v&&std::strcmp(v,"1")==0;
        const SceneCaptureSource source{pgxp_get_precise_vertex_view,gte_rtp_ring_get_xform,pgxp_get_precise_vertex_view_ex};
        enabled=scene_capture_init(GetCurrentThreadId(),requested?1:0,&source)==SCENE_OK&&requested;
        ledger_enabled=enabled&&scene_ledger_init(GetCurrentThreadId(),1)==LEDGER_OK;   /* no work when capture is off */
        owner.store(GetCurrentThreadId(),std::memory_order_release);
    });
}
/* Every entry point. A foreign thread is reported three ways, all atomic and lock-free: the runtime's own
 * owner_errors (read by scene_runtime_info, required 0 by T2 r4), the ledger's foreign counter (a call with a
 * foreign token touches nothing else) and the T2 liveness (owner_errors + epoch). No owner state is touched. */
int guard() {
    const uint32_t bound=owner.load(std::memory_order_acquire);
    if(!bound)return SCENE_BAD_STATE;
    if(bound!=GetCurrentThreadId()){
        owner_errors.fetch_add(1,std::memory_order_relaxed);
        scene_ledger_command(GetCurrentThreadId(),0,nullptr,0,nullptr);
        scene_t2_note_foreign();
        return SCENE_WRONG_THREAD;
    }
    return SCENE_OK;
}
/* r3, owner only: hand the armed generation to the producer exactly once, after BOTH capture and ledger sealed it.
 * gpu.c calls the capture hook before the ledger hook for each command, so the hand-off happens in the ledger
 * hook (or the tick), before that command's own footprint is applied to the newly bound record. */
void check_seal() {
    if(!armed_generation||armed_generation==built_generation)return;
    const uint32_t tid=GetCurrentThreadId();
    SceneCaptureInfo i;
    std::memset(&i,0,sizeof i);
    if(scene_capture_info(tid,&i)!=SCENE_OK||i.generation!=armed_generation||i.mode!=SCENE_SEALED)return;
    SceneLedgerHeader h;
    std::memset(&h,0,sizeof h);
    if(scene_ledger_header(tid,&h)!=LEDGER_OK||h.generation!=i.generation||h.mode!=LEDGER_SEALED)return;
    built_generation=armed_generation;
    /* root msg_2fe98abb: a CPU->VRAM or polyline body still open AT SEAL keeps streaming VRAM writes with no further
     * hook, so the generation must not bind: the producer treats it as an incomplete capture (retire all + epoch). */
    const uint32_t invalid=(i.complete?0u:1u)|(h.complete?0u:2u)|(gpu_scene_gp0_open()?4u:0u);
    scene_t2_on_seal(invalid);                         /* the bridge keeps the reason bits in its audit */
}
}
extern "C" void scene_runtime_command(uint32_t frame,const uint32_t *words,int count,const uint32_t *word_sources,const SceneDrawState *state) {
    initialize_emu();if(guard()==SCENE_OK&&enabled)scene_capture_command(GetCurrentThreadId(),frame,words,count,word_sources,state);
}
extern "C" void scene_runtime_tick(uint32_t frame) {
    initialize_emu();
    if(guard()==SCENE_OK&&enabled){
        scene_capture_tick(GetCurrentThreadId(),frame);
        if(ledger_enabled)scene_ledger_tick(GetCurrentThreadId(),frame);
        check_seal();                                  /* r3 */
    }
}
/* Called exclusively from gpu.c's emulation path, before collecting a word. */
extern "C" int scene_runtime_enabled(void) {initialize_emu();return guard()==SCENE_OK&&enabled?1:0;}
/* gpu_reset_state and savestate parse (gpu.c :2616, :5796). The T2 epoch and the ledger's external counter are
 * bumped FIRST and on any thread, so a foreign reset or savestate still kills every exported frame. */
extern "C" void scene_runtime_invalidate(void) {
    scene_t2_invalidate();
    scene_ledger_note_external_vram_write();
    if(guard()==SCENE_OK&&enabled){
        armed_epoch=0;
        armed_generation=0;                            /* r3 */
        scene_t2_retire_all();                         /* r3: owner side of the epoch bump above */
        scene_capture_cancel(GetCurrentThreadId());
        if(ledger_enabled)scene_ledger_cancel(GetCurrentThreadId());
    }
}
extern "C" int scene_runtime_arm(uint32_t frame) {
    if(int e=guard())return e;
    if(!enabled)return SCENE_BAD_STATE;
    if(!pgxp_enabled()||!pgxp_view_payload()){scene_t2_set_reference(1);return SCENE_PROVENANCE_UNAVAILABLE;}   /* r3 */
    const uint32_t tid=GetCurrentThreadId();
    const int rc=scene_capture_arm(tid,frame);
    if(rc==SCENE_OK){
        /* The ledger takes the capture's new generation; the T2 epoch is bound only when both armed. A refused
         * ledger arm leaves no complete ledger and no epoch: the frame stays native. */
        bool ledger_ok=false;
        SceneCaptureInfo i;
        std::memset(&i,0,sizeof i);
        if(ledger_enabled&&scene_capture_info(tid,&i)==SCENE_OK)
            ledger_ok=scene_ledger_arm(tid,frame,i.generation,gpu_scene_gp0_open())==LEDGER_OK;
        if(ledger_ok){
            /* r3: reference mode off (all three inputs healthy); the first scanout observation if the PresentState
             * has none yet (bumps the epoch); then capture_begin reads the CURRENT epoch without a bump. */
            uint32_t s[SCENE_SCANOUT_WORDS];
            gpu_scene_scanout_state(s);
            scene_t2_set_reference(0);
            scene_t2_prime_scanout(s);
            armed_epoch=scene_t2_capture_begin(owner_errors.load(std::memory_order_relaxed)==0?1:0);
            armed_generation=armed_epoch?i.generation:0;
        }
        else{
            armed_epoch=0;
            armed_generation=0;
            if(!ledger_enabled)scene_t2_set_reference(1);   /* r3 */
            scene_t2_retire_all();                         /* r3 */
            scene_t2_invalidate();
        }
    }
    return rc;
}
extern "C" int scene_runtime_cancel(void) {
    if(int e=guard())return e;
    armed_epoch=0;
    armed_generation=0;                                /* r3 */
    scene_t2_retire_all();                             /* r3 */
    scene_t2_invalidate();
    if(ledger_enabled)scene_ledger_cancel(GetCurrentThreadId());
    return scene_capture_cancel(GetCurrentThreadId());
}
extern "C" void scene_runtime_ledger_command(uint32_t frame,const uint32_t *words,int count,const SceneLedgerState *state) {
    initialize_emu();
    if(guard()!=SCENE_OK)return;
    if(ledger_enabled)scene_ledger_command(GetCurrentThreadId(),frame,words,count,state);
    if(enabled){                                       /* r3: in every ledger mode */
        check_seal();                                  /* first: a seal by this command binds frame N ... */
        scene_t2_note_command(words,count,state);      /* ... then this command's own write is checked */
    }
}
extern "C" int scene_runtime_ledger_header(SceneLedgerHeader *out) {
    if(int e=guard())return e;
    if(!ledger_enabled)return SCENE_BAD_STATE;
    return scene_ledger_header(GetCurrentThreadId(),out);
}
extern "C" int scene_runtime_ledger_get(uint32_t index,uint32_t generation,SceneLedgerEntry *out) {
    if(int e=guard())return e;
    if(!ledger_enabled)return SCENE_BAD_STATE;
    return scene_ledger_get(GetCurrentThreadId(),index,generation,out);
}
extern "C" int scene_runtime_ledger_policy(uint32_t generation,const uint32_t *ordinals,uint32_t count,SceneLedgerVerdict *out) {
    if(int e=guard())return e;
    if(!ledger_enabled)return SCENE_BAD_STATE;
    return scene_ledger_policy(GetCurrentThreadId(),generation,ordinals,count,out);
}
/* Owner thread only; 0 when no generation is bound (never armed, cancelled, invalidated, or ledger refused). */
extern "C" uint64_t scene_runtime_armed_epoch(void) {
    if(guard()!=SCENE_OK)return 0;
    return armed_epoch;
}
/* Any thread: a VRAM write outside GP0 (debug poke, external upload). */
extern "C" void scene_runtime_note_external_vram_write(void) {
    scene_ledger_note_external_vram_write();
    scene_t2_invalidate();
}
/* gpu.c GP1(03/05/06/07/08), emulation owner. r3: the T2 r6 PresentState decides. A same-value rewrite is no
 * change; the bound candidate's exact target as the first change after its boundary is the expected flip (no
 * bump); every other change, and every first observation, retires all records and bumps the epoch. */
extern "C" void scene_runtime_scanout_changed(const uint32_t s[SCENE_SCANOUT_WORDS]) {
    if(guard()!=SCENE_OK||!enabled||!s)return;
    scene_t2_observe_scanout(s);
}
/* r3, owner only: ledger r1 / r2 pass-throughs for the bridge's display-hazard hook and SealedScanout. */
extern "C" int scene_runtime_ledger_display_hazard(uint32_t generation,const uint32_t *ordinals,uint32_t count,
                                                   const int32_t rect[4],SceneLedgerVerdict *out) {
    if(int e=guard())return e;
    if(!ledger_enabled)return SCENE_BAD_STATE;
    return scene_ledger_display_hazard(GetCurrentThreadId(),generation,ordinals,count,rect,out);
}
extern "C" int scene_runtime_ledger_draw_area(uint32_t generation,uint32_t *constant,uint16_t area[4]) {
    if(int e=guard())return e;
    if(!ledger_enabled)return SCENE_BAD_STATE;
    return scene_ledger_draw_area(GetCurrentThreadId(),generation,constant,area);
}
extern "C" int scene_runtime_capture_get(uint32_t index,uint32_t generation,ScenePrimitive *out) {
    if(int e=guard())return e;
    if(!enabled)return SCENE_BAD_STATE;
    return scene_capture_get(GetCurrentThreadId(),index,generation,out);
}
extern "C" int scene_runtime_info(SceneCaptureInfo *out) {
    if(int e=guard())return e;int rc=scene_capture_info(GetCurrentThreadId(),out);
    if(rc==SCENE_OK)out->owner_errors=owner_errors.load(std::memory_order_relaxed);return rc;
}
extern "C" int scene_runtime_json(uint32_t index,uint32_t generation,char *out,size_t capacity) {
    if(int e=guard())return e;return scene_capture_json(GetCurrentThreadId(),index,generation,out,capacity);
}
