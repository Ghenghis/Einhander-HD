/* Synthetic overlay shard for the exact-entry-unmask regression test.
 *
 * Built twice by test_overlay_exact_unmask_runtime.py:
 *   H bundle: -DTEST_FUNC0=func_800262B0 -DTEST_FUNC1=func_8002673C
 *             (the broad CPS owner whose single range covers 0x80026714, plus a
 *             sibling root that is used to publish the bundle without ever
 *             calling or validating 0x800262B0 itself)
 *   E shard:  -DTEST_FUNC0=func_80026714
 *             (the isolated orphan fragment that the owner masks)
 *
 * Every export mirrors the real shard contract the loader checks: overlay_abi,
 * overlay_pair_id (matches the manifest P record), overlay_init and the ABI-v11
 * overlay_flush_cycles. The function body has one deterministic architectural
 * effect that the harness's interpreter stub reproduces exactly, so a same-state
 * shadow diff of these functions is clean (diff_passes climbs to the budget):
 *     $v0 = TEST_RESULT_SEED ^ phys(pc at entry);  pc = $ra
 * The pc at entry is the dispatched PC, so a CPS continuation re-entry of H at
 * 0x80026714 is distinguishable from a root call (test_last_pc). */
#include "overlay_api.h"

#include <stdint.h>

#ifdef _WIN32
#define TEST_EXPORT __declspec(dllexport)
#else
#define TEST_EXPORT __attribute__((visibility("default")))
#endif

#ifndef TEST_PAIR_ID
#error "TEST_PAIR_ID is required (must equal the manifest P record)"
#endif
#ifndef TEST_FUNC0
#error "TEST_FUNC0 is required (func_XXXXXXXX export of the first F record)"
#endif

#define TEST_RESULT_SEED 0xC0DE0000u

static int s_init_count;
static int s_flush_count;
static int s_calls[2];
static uint32_t s_last_pc[2];

TEST_EXPORT int overlay_abi(void) { return PSX_OVERLAY_ABI_TAG; }
TEST_EXPORT uint64_t overlay_pair_id(void) { return (uint64_t)TEST_PAIR_ID; }

TEST_EXPORT void overlay_init(const OverlayCallbacks *callbacks) {
    (void)callbacks;
    s_init_count++;
}

TEST_EXPORT void overlay_flush_cycles(void) { s_flush_count++; }

TEST_EXPORT int test_init_count(void) { return s_init_count; }
TEST_EXPORT int test_flush_count(void) { return s_flush_count; }
TEST_EXPORT int test_calls(int index) {
    return (index >= 0 && index < 2) ? s_calls[index] : -1;
}
TEST_EXPORT uint32_t test_last_pc(int index) {
    return (index >= 0 && index < 2) ? s_last_pc[index] : 0u;
}

static void body(CPUState *cpu, int index) {
    s_calls[index]++;
    s_last_pc[index] = cpu->pc;
    cpu->gpr[2] = TEST_RESULT_SEED ^ (cpu->pc & 0x1FFFFFFFu);
    cpu->pc = cpu->gpr[31];
}

TEST_EXPORT void TEST_FUNC0(CPUState *cpu) { body(cpu, 0); }
#ifdef TEST_FUNC1
TEST_EXPORT void TEST_FUNC1(CPUState *cpu) { body(cpu, 1); }
#endif
