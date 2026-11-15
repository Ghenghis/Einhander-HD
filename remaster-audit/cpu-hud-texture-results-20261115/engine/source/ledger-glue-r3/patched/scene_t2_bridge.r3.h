#ifndef EINHD_SCENE_T2_BRIDGE_R3_H
#define EINHD_SCENE_T2_BRIDGE_R3_H
/* PRIVATE glue r3 bridge (claude-einhander, source-only proposal; root msg_b02d1bcc / msg_08008ad5 / msg_2fe98abb,
 * design 19db18ce). It carries the T2 r6 owned present lifecycle (remix_t2.r6.h 419dea94) over T2 r4 liveness
 * (eebb2c8f). scene_t2_bridge.r3.cpp is the only TU that includes the T2 closure.
 * NOTHING here suppresses native output. The consumer API only takes a published frame, evaluates the r6 gate
 * decision, and releases the frame. Composition, G4 material identity and any live suppression stay unqualified. */
#include <stdint.h>
#include "scene_ledger.r3.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Any thread: lock-free atomics, with r2 meaning unchanged. */
uint64_t scene_t2_arm_epoch(void);          /* r4 arm: BUMPS the epoch and so kills every r6 record. Glue r3 does not call it. */
void scene_t2_invalidate(void);             /* epoch bump */
void scene_t2_note_foreign(void);           /* owner_errors + epoch */
uint64_t scene_t2_epoch_now(void);
uint64_t scene_t2_owner_errors_now(void);
/* Emulation owner only: called by scene_runtime r3 after its guard. */
uint64_t scene_t2_capture_begin(int owner_healthy);           /* current epoch, no bump; 0 = refused */
void scene_t2_prime_scanout(const uint32_t s[8]);             /* first scanout observation, only if none yet */
void scene_t2_observe_scanout(const uint32_t s[8]);           /* every GP1 scanout write (r6 observe_scanout) */
void scene_t2_note_command(const uint32_t *words, int count, const SceneLedgerState *state);   /* every GP0 command */
/* Once per armed generation, after capture AND ledger sealed it. invalid != 0 means do not bind: bit 0 the capture
 * is incomplete, bit 1 the ledger is incomplete, bit 2 a GP0 body is open at the seal. Then every record is retired
 * and the epoch bumps. */
void scene_t2_on_seal(uint32_t invalid);
void scene_t2_retire_all(void);                               /* owner cancel / reset / savestate / refused ledger arm */
void scene_t2_set_reference(int on);                          /* 1: retire all, bind nothing until 0 */
#ifdef __cplusplus
}
namespace t2 { namespace r4 { class T2Liveness; } namespace r6 { struct T2FrameR6; struct CompletionR6; class PresentState; } }
/* C++ consumer API, any thread.
 *  - take(): the published frame, immutable while taken, or nullptr;
 *  - release(): returns a taken frame to the producer's private pool. Any other pointer is ignored;
 *  - gate(): ONLY the r6 decision (gate_allow_suppress). Nothing in glue r3 acts on it;
 *  - scanout_now(): a consistent scanout generation and state, used to stamp CompletionR6. */
const t2::r6::T2FrameR6 *scene_t2_take(void);
void scene_t2_release(const t2::r6::T2FrameR6 *frame);
bool scene_t2_gate(const t2::r6::T2FrameR6 *frame, uint64_t expected_overlay_hash, const t2::r6::CompletionR6 *c);
bool scene_t2_scanout_now(uint64_t *generation, uint32_t s[8]);
const t2::r4::T2Liveness &scene_t2_liveness();
const t2::r6::PresentState &scene_t2_present();
/* Emulation owner only: producer audit for diagnostics and fixtures. */
struct SceneT2Audit {
    uint64_t seals, invalid_seals, built, bound, published, busy, refused_scanout;
    uint32_t last_invalid, last_scan_reason, last_bind_reason;
};
const SceneT2Audit &scene_t2_audit();
#endif
#endif
