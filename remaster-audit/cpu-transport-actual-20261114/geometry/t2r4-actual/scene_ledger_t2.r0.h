// Export of a sealed, complete scene_ledger r0 into T2 r3's LedgerHeader / LedgerEntry (claude-einhander).
// SOURCE ONLY. Include after scene_capture.h, the T2 r3 prerequisites, remix_t2.r3.h (8baba81c, namespace t2)
// and scene_ledger.r0.h. T2 r3 itself is unchanged; its ledger checks (header binding, captured-textured order,
// interleave) consume this export exactly as they are written.
//
// Mapping:
//   LedgerHeader.frame/generation/command_count/complete <- the sealed ledger header (complete only when the ledger
//     is complete and every observed command has an entry);
//   LedgerEntry box: half-open int32 -> T2 inclusive int16, converted once here: [x0,x1) -> x0..x1-1;
//   an entry without a footprint (state, NOP, VRAM->CPU read, empty or clamped-out draw) gets the sentinel
//     x0 = y0 = INT16_MAX, x1 = y1 = INT16_MIN, which T2's inclusive overlap() never matches against any real box
//     whose coordinates lie in [-32767, 32766] (enforced below), nor against another sentinel;
//   fills, VRAM->VRAM and CPU->VRAM writes export the union of their destination pieces (conservative).
// Consequence under T2 r3's pilot interleave rule: a back-buffer clear (fill) or any earlier draw that overlaps a
// later transported polygon makes the frame F_INTERLEAVED. This export does not relax that; it is a composition
// decision outside the ledger.
#ifndef EINHD_SCENE_LEDGER_T2_R0_H
#define EINHD_SCENE_LEDGER_T2_R0_H
#include <stdint.h>
#include <string.h>

inline bool scene_ledger_export_t2(uint32_t token, uint32_t generation, t2::LedgerHeader *lh, t2::LedgerEntry *out,
                                   uint32_t capacity, uint32_t *count) {
    if (!lh || !out || !count) return false;
    *count = 0;
    memset(lh, 0, sizeof *lh);
    SceneLedgerHeader h;
    if (scene_ledger_header(token, &h) != LEDGER_OK || !h.complete || h.generation != generation ||
        h.entry_count != h.command_count || h.entry_count > capacity || h.entry_count > t2::kMaxLedger)
        return false;
    for (uint32_t i = 0; i < h.entry_count; ++i) {
        SceneLedgerEntry e;
        if (scene_ledger_get(token, i, generation, &e) != LEDGER_OK) return false;
        t2::LedgerEntry &o = out[i];
        memset(&o, 0, sizeof o);
        if (e.bbox.x0 >= e.bbox.x1 || e.bbox.y0 >= e.bbox.y1) {
            o.x0 = o.y0 = INT16_MAX;
            o.x1 = o.y1 = INT16_MIN;
        } else {
            if (e.bbox.x0 < -32767 || e.bbox.y0 < -32767 || e.bbox.x1 > 32767 || e.bbox.y1 > 32767) return false;
            o.x0 = int16_t(e.bbox.x0);
            o.y0 = int16_t(e.bbox.y0);
            o.x1 = int16_t(e.bbox.x1 - 1);
            o.y1 = int16_t(e.bbox.y1 - 1);
        }
        o.textured_index = e.textured_index;
        o.captured_textured = (e.flags & LF_CAPTURED_TEXTURED) ? 1 : 0;
    }
    lh->frame = h.frame;
    lh->generation = h.generation;
    lh->command_count = h.command_count;
    lh->complete = 1;
    *count = h.entry_count;
    return true;
}
#endif
