#ifndef EINHD_SCENE_LEDGER_R3_H
#define EINHD_SCENE_LEDGER_R3_H
/* Full ordered GP0 command ledger, source r0 (claude-einhander), per spec r1 48d7fbfd and root msg_00117d59.
 * r1 (claude-einhander, 2026-11-14): ADDITIVE revision. Only scene_ledger_display_hazard is new (declared after
 * scene_ledger_policy); every other byte is r0 220d1a5e except this note and the include guard. r0 is preserved.
 * r2 (claude-einhander, 2026-11-14): ADDITIVE revision of r1 f080658b. New: scene_ledger_footprint and
 * scene_ledger_draw_area (declared last); no existing type or declaration changes. r0 and r1 are preserved.
 * r3 (claude-einhander, 2026-11-15): CORRECTION of r2 9bcb4ea1 per root msg_2fe98abb: a pure footprint treats a
 * draw as mapped only when native_screen_mapping == 1 exactly (identity); every other value is unknown.
 * SOURCE ONLY: not compiled, not run, not linked into the native renderer. No live gate is enabled by it.
 *
 * Sibling of v66-r3 src/scene_capture.cpp 78c4158d (preserved unchanged). The ledger is meant to be called at
 * the same hook as scene_capture_command (gpu.c 3d8b5d3e gp0_execute_command, and the polyline header path),
 * with the same frame values, so both see the same sealed interval. It records EVERY fully collected command
 * of that interval, in order, with a half-open VRAM footprint, and fails closed (complete = 0) on anything it
 * cannot represent:
 *   - polyline bodies (the hook sees only the header word; gpu.c streams the vertices outside it);
 *   - draws while native_screen_mapping == 0 (widescreen / 2D / geometry transforms move the footprint);
 *   - malformed, unsupported or overflowing commands; an unknown display area;
 *   - a CPU->VRAM transfer or polyline body that may straddle the start of the interval;
 *   - any mutating call from a foreign thread, or an external VRAM write, between arm and read.
 * Transfer, rect-size, vertex, word-count, CLUT and page decodes are the native lines, extracted verbatim from
 * pinned sources into scene_ledger_native_unpack.inc by the fixture driver; nothing is retyped.
 *
 * A complete ledger proves ordering and coverage of commands only. It proves neither material content
 * identity (G4) nor that a 2D/3D composition is valid. */
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
enum { SCENE_LEDGER_CAPACITY = 4096, SCENE_LEDGER_MAX_PIECES = 4, SCENE_LEDGER_MAX_DISPLAY = 4 };
/* Same lifecycle as scene_capture: ARMED waits for the first frame transition, the next transition seals. */
enum { LEDGER_DISABLED, LEDGER_IDLE, LEDGER_ARMED, LEDGER_RECORDING, LEDGER_SEALED };
enum { LEDGER_OK, LEDGER_WRONG_THREAD, LEDGER_BAD_STATE, LEDGER_BAD_ARGUMENT };
/* Command classes. */
enum { LC_NOP, LC_STATE, LC_POLYGON, LC_LINE, LC_POLYLINE, LC_RECT, LC_FILL, LC_COPY, LC_WRITE, LC_READ, LC_OTHER };
/* Entry flags. */
enum {
    LF_TEXTURED_POLY = 1u << 0,     /* GP0 0x20-0x3F with bit 2: carries textured_index (capture ordinal rule) */
    LF_CAPTURED_TEXTURED = 1u << 1, /* textured polygon the capture records when well formed (n == native count) */
    LF_DRAW = 1u << 2,              /* rasterized: dst = drawing-area-clamped bbox */
    LF_MUTATES = 1u << 3,           /* fill / VRAM->VRAM dst / CPU->VRAM */
    LF_READS = 1u << 4,             /* VRAM->VRAM src / VRAM->CPU */
    LF_OVERSIZE = 1u << 5,          /* native would discard (dx > 1023 or dy > 511); footprint kept (superset) */
    LF_EMPTY = 1u << 6,             /* no footprint */
    LF_UNKNOWN_FOOTPRINT = 1u << 7, /* cannot be bounded: the ledger is incomplete */
    LF_MALFORMED = 1u << 8,
    LF_TEXTURED = 1u << 9           /* samples a texture page: polygon tpage word, or rect with state texpage */
};
/* Reasons a sealed ledger is incomplete (SceneLedgerHeader.incomplete_mask). complete iff sealed and 0. */
enum {
    LI_ARM_OPEN = 1u << 0,          /* GP0 was inside a CPU->VRAM transfer or polyline body when armed */
    LI_OPEN_AT_START = 1u << 1,     /* last command before the interval opened such a body */
    LI_FRAME_GAP = 1u << 2,         /* a transition skipped frames (start or seal) */
    LI_MALFORMED = 1u << 3,
    LI_OVERFLOW = 1u << 4,
    LI_UNSUPPORTED = 1u << 5,       /* native word count 0 (unknown) or 0x1F (native fatal halt) */
    LI_UNKNOWN_FOOTPRINT = 1u << 6, /* polyline body */
    LI_MAPPING = 1u << 7,           /* a draw with native_screen_mapping == 0 */
    LI_DISPLAY_UNKNOWN = 1u << 8,
    LI_DISPLAY_OVERFLOW = 1u << 9,
    LI_FOREIGN = 1u << 10,          /* a mutating call with a foreign token happened since arm */
    LI_EXTERNAL = 1u << 11          /* scene_ledger_note_external_vram_write since arm */
};
/* Half-open [x0,x1) x [y0,y1), int32. Empty iff x0 >= x1 or y0 >= y1. */
typedef struct LedgerRect { int32_t x0, y0, x1, y1; } LedgerRect;
/* Native values in force BEFORE dispatch of this command, filled by the runtime glue from gpu.c globals. */
typedef struct SceneLedgerState {
    uint32_t texture_window;
    int32_t draw_offset_x, draw_offset_y;
    uint16_t draw_left, draw_top, draw_right, draw_bottom;  /* inclusive drawing area (GP0 E3/E4) */
    uint16_t texpage;                                       /* gpu.c current_texpage() */
    uint8_t set_mask, check_mask;
    uint8_t native_screen_mapping;  /* exactly as SceneDrawState: 1 only when no ws / 2D / geometry transform */
    uint8_t display_known;          /* 1 when display_* is the native displayed framebuffer area */
    int32_t display_x, display_y, display_w, display_h;     /* VRAM halfwords, native */
} SceneLedgerState;
typedef struct SceneLedgerEntry {
    uint32_t global_index;          /* position in the interval */
    uint32_t textured_index;        /* LF_TEXTURED_POLY: capture ordinal (textured_seen - 1); else 0xFFFFFFFF */
    uint32_t state_hash;            /* FNV-1a of the SceneLedgerState in force; 0 when no state */
    LedgerRect bbox;                /* draws: clamped destination; transfers: union of dst pieces; else empty */
    LedgerRect dst[SCENE_LEDGER_MAX_PIECES], src[SCENE_LEDGER_MAX_PIECES];  /* wrap-split VRAM pieces */
    uint16_t flags, tpage, clut;    /* tpage/clut valid with LF_TEXTURED */
    uint8_t op, cls, dst_count, src_count;
} SceneLedgerEntry;
typedef struct SceneLedgerHeader {
    uint32_t mode, frame, generation, owner_token;
    uint32_t command_count;         /* commands observed in the interval, all classes */
    uint32_t entry_count;           /* stored entries (== command_count unless overflow) */
    uint32_t incomplete_mask;
    uint32_t malformed, overflow, unsupported, unknown_footprints, mapping_unknown, polylines, textured_seen;
    uint32_t display_count;
    LedgerRect display[SCENE_LEDGER_MAX_DISPLAY];  /* distinct displayed areas seen (raw, unwrapped) */
    uint32_t final_state_hash;      /* state hash of the last command that carried a state */
    uint64_t foreign_calls, external_writes;       /* deltas since arm, as last evaluated */
    uint8_t sealed, complete;
} SceneLedgerHeader;
/* Bind one immutable owner token (actual host thread id in the glue) once. enabled must be exactly 0/1. */
int scene_ledger_init(uint32_t token, int enabled);
/* capture_generation: the scene_capture generation of the same arm (nonzero, differs from the previous one).
 * gp0_open: exactly 0/1, 1 when gpu.c gp0_state is GP0_VRAM_WRITE or a polyline state at arm time. */
int scene_ledger_arm(uint32_t token, uint32_t current_frame, uint32_t capture_generation, int gp0_open);
int scene_ledger_cancel(uint32_t token);
int scene_ledger_tick(uint32_t token, uint32_t frame);
/* At EVERY fully collected GP0 command (and the polyline header, count 1, state may be NULL), before dispatch. */
int scene_ledger_command(uint32_t token, uint32_t frame, const uint32_t *words, int count,
                         const SceneLedgerState *state);
/* Any thread, no token: savestate load, debug VRAM poke, anything that writes VRAM outside GP0. */
void scene_ledger_note_external_vram_write(void);
/* Owner only. Re-evaluates the foreign/external counters at every read (any such call since arm => incomplete). */
int scene_ledger_header(uint32_t token, SceneLedgerHeader *out);
/* Copy one entry of a sealed, complete ledger of the given generation; failure zeroes *out. */
int scene_ledger_get(uint32_t token, uint32_t index, uint32_t generation, SceneLedgerEntry *out);

/* VRAM hazard policy for a proposed transported set (pilot rules; whole frame native on any hit). */
enum {
    LP_TRANSPORT_OK = 0,
    LP_NATIVE_INCOMPLETE,   /* not sealed, not complete, or another generation */
    LP_NATIVE_BAD_REF,      /* a transported index is absent, not captured, or repeated */
    LP_NATIVE_MUTATION,     /* a fill/copy/write dst touches a transported page or CLUT (any time in the frame) */
    LP_NATIVE_FB_MUTATION,  /* a fill/copy/write dst touches a displayed framebuffer area */
    LP_NATIVE_DRAW_DEST,    /* any draw destination touches a transported page or CLUT (feedback) */
    LP_NATIVE_DISPLAY,      /* a transported page or CLUT touches a displayed framebuffer area */
    LP_NATIVE_READBACK      /* after a transported polygon, a VRAM read or textured sample touches its dst */
};
typedef struct SceneLedgerVerdict { uint32_t verdict, entry, ref; } SceneLedgerVerdict;
/* transported: capture ordinals (ScenePrimitive.ordinal) of the polygons the caller proposes to transport. */
int scene_ledger_policy(uint32_t token, uint32_t generation, const uint32_t *transported, uint32_t count,
                        SceneLedgerVerdict *out);
/* r1 (additive): display hazard of an EXPLICIT target rect (x, y, w, h in VRAM halfwords; w, h > 0; wrap-split
 * like every native area) for the proposed transported set of a sealed, complete ledger of `generation`. This is
 * the T2 r5/r6 DisplayHazardHook: the glue passes the frame's target (the buffer that the expected flip will
 * display) and the exact transported ordinal set. Verdicts:
 *   LP_NATIVE_INCOMPLETE  not sealed, not complete, or another generation (the default)
 *   LP_NATIVE_BAD_REF     a transported index is absent, not captured, repeated, or count > capacity
 *   LP_NATIVE_DISPLAY     entry == ref == 0xFFFFFFFF: the target overlaps an area displayed DURING the interval
 *                         (the frame did not draw into a hidden buffer); otherwise (entry, ref): a transported
 *                         page or CLUT overlaps the target (its texels would be the suppressed displayed image)
 *   LP_TRANSPORT_OK       otherwise.
 * It does NOT replace scene_ledger_policy: T2 r4 still requires that policy to be LP_TRANSPORT_OK as well. */
int scene_ledger_display_hazard(uint32_t token, uint32_t generation, const uint32_t *transported, uint32_t count,
                                const int32_t rect[4], SceneLedgerVerdict *out);
/* r2 (additive): stateless VRAM WRITE footprint of ONE fully collected GP0 command, valid in every ledger mode
 * (ARMED, RECORDING, SEALED, IDLE) and from any thread: no token, no ledger state read or written. It uses the same
 * decode and clamp as a RECORDING entry's dst (equality fixture: build_scene_ledger_fixture.r2.py).
 *   *known = 0  the write cannot be bounded: an unsupported command (LC_OTHER), a polyline header (its body streams
 *               outside the hook), malformed input (null or empty words, or a word count other than the native one),
 *               no state, or a draw with native_screen_mapping != 1 (r3: identity is exactly 1);
 *   *known = 1  dst[0 .. *dst_count) are the wrap-split half-open pieces the command writes: draws (drawing-area
 *               clamped bbox), fills (NOT clamped), the VRAM->VRAM copy destination, the CPU->VRAM rect; 0 pieces for
 *               state, NOP, VRAM->CPU reads and zero-size draws.
 * Returns LEDGER_BAD_ARGUMENT for null outputs, else LEDGER_OK. */
int scene_ledger_footprint(const uint32_t *words, int count, const SceneLedgerState *state,
                           LedgerRect dst[SCENE_LEDGER_MAX_PIECES], uint32_t *dst_count, uint32_t *known);
/* r2 (additive): drawing-area constancy of the SEALED, COMPLETE interval of `generation` (owner token). A separate
 * query: SceneLedgerHeader is unchanged. *constant = 1 and area = {left, top, right, bottom} (inclusive, native) only
 * when at least one recorded command carried a state and every such state had that same drawing area; otherwise
 * (also for an empty interval, no observed state, not sealed, not complete, another generation) *constant = 0 and
 * area is zeroed. Returns LEDGER_WRONG_THREAD / LEDGER_BAD_STATE (unbound) / LEDGER_BAD_ARGUMENT, else LEDGER_OK. */
int scene_ledger_draw_area(uint32_t token, uint32_t generation, uint32_t *constant, uint16_t area[4]);
#ifdef __cplusplus
}
#endif
#endif
