/* s67 PROPOSAL r1 (not integrated, not compiled): per-target skin catalog + binding for ein-material-v3.
 * r0 (skin-targets/hd_skin_targets.h 666daa59) is kept unchanged; this r1 applies main's msg_bea1f8ba.
 * A NEW header beside hd_skin_material.h / hd_skin_detail.h, which stay unchanged (profiles, allowlists,
 * channels, GLSL). It decides WHICH existing profile, if any, a draw of an exact TEX-CLUT key gets, per
 * named target. It is a palette tint of existing HD atlases, NOT authored PBR / realistic 4K skins.
 *
 * Selection modes (PSXRECOMP_SKIN_TARGETS):
 *   UNSET   (variable absent or empty) -> the caller's existing legacy path runs unchanged;
 *   INVALID (non-empty but rejected)   -> FAIL CLOSED: every draw stock, legacy channels suppressed;
 *   VALID                              -> target mode: only a fully gated per-target key gets its target's
 *                                         profile; "target=stock" validly disables that target; every
 *                                         other draw (legacy-channel keys included) is stock.
 * There is no cross-target fallback.
 *
 * Gate qualification (explicit):
 *   QUALIFIED by source facts at draw time: exact key, real upload (upload_serial != 0), required native
 *     upload size, observed page, observed CLUT, UV bounds contained in ONE vetted observed rectangle,
 *     material generation equal to the commit generation;
 *   UNQUALIFIED / proposal: the HD-image gate checks only that a replacement is sampled and its size. That
 *     does NOT prove native alpha preservation or that the image is the frozen admitted file; a trusted
 *     pack-entry admission identity bound once at load is not implemented. The rectangle lists are the
 *     complete set of S2-observed boxes, which is observation provenance, not exclusive actor ownership.
 *   OPEN: re-committing a target selection after a live material change (generation bump) is not
 *     implemented, so a later live change leaves target mode stock until restart. */
#ifndef PSXRECOMP_HD_SKIN_TARGETS_H
#define PSXRECOMP_HD_SKIN_TARGETS_H
#include "hd_skin_material.h"

#define HD_SKIN_TARGETS_CONTRACT "ein-skin-targets-v0r1-proposal"
#define HD_SKIN_TARGET_MAX 16
#define HD_SKIN_TARGET_MAX_KEYS 16
#define HD_SKIN_TARGET_MAX_RECTS 32

enum { HD_SKIN_TARGET_UNRESOLVED = 0, HD_SKIN_TARGET_BOUND = 1 };
enum { HD_SKIN_TGT_MODE_INVALID = -1, HD_SKIN_TGT_MODE_UNSET = 0, HD_SKIN_TGT_MODE_VALID = 1 };

typedef struct { uint8_t u0, v0, u1, v1; } HdSkinTargetRect;   /* inclusive, page-relative texels */

typedef struct {
    uint32_t texture, palette;
    uint16_t page_x, page_y;               /* observed texture page (VRAM units) */
    uint16_t clut_x, clut_y;               /* observed CLUT position */
    const HdSkinTargetRect *rects;         /* vetted observed draw rectangles (not an envelope) */
    int rect_count;
    uint16_t native_w, native_h;           /* required native upload size in texels */
    uint16_t hd_w, hd_h;                   /* candidate HD image size (UNQUALIFIED gate, see above) */
} HdSkinTargetKey;

typedef struct {
    const char *id;
    const char *label;
    int status;
    const HdSkinTargetKey *keys;   /* BOUND: owned keys. UNRESOLVED: diagnostic candidates, never applied */
    int key_count;
    const char *unresolved_reason; /* NULL when BOUND */
} HdSkinTarget;

/* Exact Stage 2 draws-s2.json (6a693c70) uv_top boxes; each list has uv_distinct entries and its counts
 * sum to the key's draw count, i.e. it is every distinct S2-observed box (not exclusivity proof). */
static const HdSkinTargetRect hd_skin_rects_724E77DA[] = {
    {156,24,190,43},{153,45,190,51},{130,25,139,43},{140,21,157,43},{171,54,190,60}};
static const HdSkinTargetRect hd_skin_rects_7E3ADD56[] = {
    {213,227,233,230},{192,208,216,215},{194,242,245,247},{248,232,251,249},{196,222,200,223},
    {196,222,203,228},{198,242,244,247},{248,232,253,252},{248,233,254,254}};
static const HdSkinTargetRect hd_skin_rects_B16492B1[] = {
    {193,193,254,228},{223,234,251,245},{194,229,209,252},{237,195,252,206},{237,195,246,206},{214,248,250,254}};
static const HdSkinTargetRect hd_skin_rects_E2F3477C[] = {
    {1,221,32,238},{28,195,61,215},{1,193,28,212},{32,217,38,238},{1,244,34,253},{1,243,34,253},{38,217,61,238}};
static const HdSkinTargetRect hd_skin_rects_5CC44E5F[] = {
    {159,104,161,115},{164,105,168,123},{164,106,168,123},{164,105,169,123},{149,104,160,125},{161,116,162,124},
    {131,65,141,70},{159,104,162,125},{129,65,142,100},{164,106,169,123},{131,65,142,71}};
#define HD_SKIN_NRECTS(a) ((int)(sizeof(a) / sizeof((a)[0])))

/* Generic SHARED hull candidate: the 4 hull keys of palette 21FDE894 (legacy player allowlist
 * hd_skin_material.h:48-52 + S2 observation). Not a named craft, not live-accepted. Native 64x64 is the
 * size hd_skin_detail.h:122 already requires for this palette (code constraint, not observed). */
static const HdSkinTargetKey hd_skin_target_hull_keys[] = {
    {0x724E77DAu,0x21FDE894u, 832,256, 288,488, hd_skin_rects_724E77DA, HD_SKIN_NRECTS(hd_skin_rects_724E77DA), 64,64, 1024,1024},
    {0x7E3ADD56u,0x21FDE894u, 832,256, 288,488, hd_skin_rects_7E3ADD56, HD_SKIN_NRECTS(hd_skin_rects_7E3ADD56), 64,64, 1024,1024},
    {0xB16492B1u,0x21FDE894u, 896,256, 288,488, hd_skin_rects_B16492B1, HD_SKIN_NRECTS(hd_skin_rects_B16492B1), 64,64, 1024,1024},
    {0xE2F3477Cu,0x21FDE894u, 896,256, 288,488, hd_skin_rects_E2F3477C, HD_SKIN_NRECTS(hd_skin_rects_E2F3477C), 64,64, 1024,1024},
};
static const HdSkinTargetKey hd_skin_target_mech_sheet_candidates[] = {
    {0x5CC44E5Fu,0x053D9A00u, 832,256, 304,510, hd_skin_rects_5CC44E5F, HD_SKIN_NRECTS(hd_skin_rects_5CC44E5F), 64,64, 1024,1024},
};

static const HdSkinTarget hd_skin_targets[] = {
    {"player.hull.shared_candidate", "generic shared player-hull candidate (not a named craft; not live-accepted)",
     HD_SKIN_TARGET_BOUND, hd_skin_target_hull_keys, 4, NULL},
    {"player.mechanical_sheet", "shared mechanical sheet", HD_SKIN_TARGET_UNRESOLVED, hd_skin_target_mech_sheet_candidates, 1,
     "5CC44E5F-053D9A00 is a shared mechanical sheet (S2: 56 draws over 11 small boxes); which actor parts it owns is unproven"},
    {"player.craft.named", "named player craft", HD_SKIN_TARGET_UNRESOLVED, NULL, 0,
     "no craft->key ownership proof; one shared hull key set for every craft"},
    {"player.gunpods", "player gunpods / guns", HD_SKIN_TARGET_UNRESOLVED, NULL, 0,
     "pod/gun TEX families (e.g. S2 0223BCEF, B24C6DA2) have no proven key+CLUT+rect ownership"},
    {"enemy.stage1.strips", "Stage 1 enemy strips", HD_SKIN_TARGET_UNRESOLVED, NULL, 0,
     "6 x -527B28B9 strips are allowlisted from Stage 1 captures, but no page/CLUT/UV draw records are in hand and cross-stage exclusivity is unproven (0 S2 draws)"},
    {"enemy.stage2.families", "Stage 2 enemy families", HD_SKIN_TARGET_UNRESOLVED, NULL, 0,
     "S2 enemy TEX 3DD37B6B/F47289DC/2E670984/721C46B1/7A844A1C/8D419ACF: family level only, no per-key ownership"},
    {"boss", "bosses", HD_SKIN_TARGET_UNRESOLVED, NULL, 0,
     "S2 boss TEX CA05583A/A65BA8AE/4CE48309/986B6314/AC93CD6C: 0 drawn, 0 authored HD images"},
    {"weapons.effects", "weapons, bullets, effects", HD_SKIN_TARGET_UNRESOLVED, NULL, 0,
     "no identity mapping for weapons, bullets or effects"},
};
#define HD_SKIN_TARGET_COUNT ((int)(sizeof(hd_skin_targets) / sizeof(hd_skin_targets[0])))

typedef struct {
    int mode;                                           /* HD_SKIN_TGT_MODE_* */
    const HdSkinTarget *catalog;
    int count;
    const HdSkinProfile *profile[HD_SKIN_TARGET_MAX];  /* NULL = stock for that target */
    float strength[HD_SKIN_TARGET_MAX];
    uint64_t generation;                                /* material generation at commit */
} HdSkinTargetSelection;

typedef struct {
    uint32_t texture, palette;
    int hd_image;               /* 1 = this draw samples a decoded/resident HD replacement */
    unsigned hd_w, hd_h;        /* that replacement's size */
    uint64_t upload_serial;     /* 0 = native page fallback */
    unsigned native_w, native_h;
    unsigned page_x, page_y, clut_x, clut_y;
    unsigned u0, v0, u1, v1;    /* draw UV bounds, inclusive */
    uint64_t generation;        /* current material generation */
} HdSkinDrawFacts;

enum {
    HD_SKIN_TGT_APPLY = 0,
    HD_SKIN_TGT_MODE_OFF,              /* UNSET: caller keeps its legacy behaviour */
    HD_SKIN_TGT_MODE_REJECTED,         /* INVALID: fail closed, stock */
    HD_SKIN_TGT_UNKNOWN_KEY,
    HD_SKIN_TGT_AMBIGUOUS_KEY,
    HD_SKIN_TGT_TARGET_UNRESOLVED,
    HD_SKIN_TGT_STOCK_SELECTED,        /* key's own target not selected / selected stock; no fallback */
    HD_SKIN_TGT_NO_HD_IMAGE,
    HD_SKIN_TGT_HD_SIZE_MISMATCH,
    HD_SKIN_TGT_NATIVE_FALLBACK,
    HD_SKIN_TGT_NATIVE_SIZE_MISMATCH,
    HD_SKIN_TGT_PAGE_MISMATCH,
    HD_SKIN_TGT_CLUT_MISMATCH,
    HD_SKIN_TGT_OUTSIDE_RECTS,         /* not contained in any single vetted rectangle */
    HD_SKIN_TGT_GENERATION_STALE,
    HD_SKIN_TGT_REASON_COUNT
};
static const char *const hd_skin_target_reason_names[HD_SKIN_TGT_REASON_COUNT] = {
    "apply","mode_unset","mode_invalid","unknown_key","ambiguous_key","target_unresolved","stock_selected",
    "no_hd_image","hd_size_mismatch","native_fallback","native_size_mismatch","page_mismatch",
    "clut_mismatch","outside_rects","generation_stale"};
static const char *hd_skin_target_reason_name(int r) {
    return r >= 0 && r < HD_SKIN_TGT_REASON_COUNT ? hd_skin_target_reason_names[r] : "invalid_reason";
}

static int hd_skin_rects_overlap(const HdSkinTargetRect *a, const HdSkinTargetRect *b) {
    return a->u0 <= b->u1 && b->u0 <= a->u1 && a->v0 <= b->v1 && b->v0 <= a->v1;
}

/* 0 = consistent. Checks EVERY target regardless of status: valid status, non-empty unique id, key_count
 * in [0, MAX_KEYS], keys non-NULL when key_count > 0, BOUND => key_count > 0; every key: rect_count in
 * [1, MAX_RECTS], rects non-NULL, each rect ordered, nonzero sizes; no (texture,palette) listed twice; no
 * rectangle of one target overlapping a rectangle of ANOTHER target on the same page+CLUT. */
static int hd_skin_target_catalog_check(const HdSkinTarget *cat, int count) {
    int a, b, i, j, r, s;
    if (!cat || count <= 0 || count > HD_SKIN_TARGET_MAX) return 1;
    for (a = 0; a < count; ++a) {
        if (!cat[a].id || !cat[a].id[0]) return 1;
        if (cat[a].status != HD_SKIN_TARGET_BOUND && cat[a].status != HD_SKIN_TARGET_UNRESOLVED) return 6;
        for (b = 0; b < a; ++b) if (!strcmp(cat[a].id, cat[b].id)) return 7;
        if (cat[a].key_count < 0 || cat[a].key_count > HD_SKIN_TARGET_MAX_KEYS) return 8;
        if (cat[a].key_count > 0 && !cat[a].keys) return 9;
        if (cat[a].status == HD_SKIN_TARGET_BOUND && cat[a].key_count == 0) return 2;
        for (i = 0; i < cat[a].key_count; ++i) {
            const HdSkinTargetKey *k = &cat[a].keys[i];
            if (k->rect_count < 1 || k->rect_count > HD_SKIN_TARGET_MAX_RECTS || !k->rects) return 3;
            if (!k->native_w || !k->native_h || !k->hd_w || !k->hd_h) return 3;
            for (r = 0; r < k->rect_count; ++r)
                if (k->rects[r].u0 > k->rects[r].u1 || k->rects[r].v0 > k->rects[r].v1) return 3;
        }
    }
    for (a = 0; a < count; ++a)
        for (i = 0; i < cat[a].key_count; ++i) {
            const HdSkinTargetKey *k = &cat[a].keys[i];
            for (b = a; b < count; ++b)
                for (j = (b == a ? i + 1 : 0); j < cat[b].key_count; ++j) {
                    const HdSkinTargetKey *o = &cat[b].keys[j];
                    if (k->texture == o->texture && k->palette == o->palette) return 4;
                    if (b != a && k->page_x == o->page_x && k->page_y == o->page_y &&
                        k->clut_x == o->clut_x && k->clut_y == o->clut_y)
                        for (r = 0; r < k->rect_count; ++r)
                            for (s = 0; s < o->rect_count; ++s)
                                if (hd_skin_rects_overlap(&k->rects[r], &o->rects[s])) return 5;
                }
        }
    return 0;
}

static int hd_skin_target_index(const HdSkinTarget *cat, int count, const char *id, size_t len) {
    int i;
    for (i = 0; i < count; ++i)
        if (strlen(cat[i].id) == len && !strncmp(cat[i].id, id, len)) return i;
    return -1;
}

/* CSV "target=profile[@strength],..." or "target=stock". Returns the mode:
 * UNSET (NULL/empty), VALID, or INVALID on: inconsistent catalog, unknown or UNRESOLVED target, unknown
 * profile, strength on "stock", duplicate target (tracked in seen[], since NULL profile means stock),
 * bad strength or syntax. INVALID is fail-closed (stock, legacy suppressed) - never legacy. */
static int hd_skin_target_selection_parse(HdSkinTargetSelection *out, const HdSkinTarget *cat, int count,
                                          const char *csv, uint64_t generation) {
    const char *p = csv;
    int seen[HD_SKIN_TARGET_MAX];
    if (!out) return HD_SKIN_TGT_MODE_INVALID;
    memset(out, 0, sizeof(*out));
    memset(seen, 0, sizeof seen);
    out->mode = HD_SKIN_TGT_MODE_UNSET;
    if (!p || !p[0]) return out->mode;
    if (hd_skin_target_catalog_check(cat, count)) goto bad;
    for (;;) {
        const char *name, *prof;
        char buf[64];
        int t, is_stock;
        size_t plen;
        float amount = HD_SKIN_DEFAULT_STRENGTH;
        while (*p && isspace((unsigned char)*p)) ++p;
        name = p;
        while (*p && *p != '=' && *p != ',') ++p;
        if (*p != '=') goto bad;
        t = hd_skin_target_index(cat, count, name, (size_t)(p - name));
        if (t < 0 || cat[t].status != HD_SKIN_TARGET_BOUND || seen[t]) goto bad;
        seen[t] = 1;
        prof = ++p;
        while (*p && *p != ',' && *p != '@' && !isspace((unsigned char)*p)) ++p;
        plen = (size_t)(p - prof);
        if (!plen || plen >= sizeof buf) goto bad;
        memcpy(buf, prof, plen); buf[plen] = 0;
        is_stock = !strcmp(buf, "stock");
        out->profile[t] = is_stock ? NULL : hd_skin_find_profile(buf);
        if (!is_stock && !out->profile[t]) goto bad;
        if (*p == '@') {
            char *e = NULL;
            const char *at = ++p;
            if (is_stock) goto bad;
            amount = strtof(at, &e);
            if (!e || e == at || !isfinite(amount) || amount < 0.0f || amount > 1.0f) goto bad;
            p = e;
        }
        out->strength[t] = is_stock ? 0.0f : amount;
        while (*p && isspace((unsigned char)*p)) ++p;
        if (!*p) break;
        if (*p++ != ',') goto bad;
    }
    out->catalog = cat;
    out->count = count;
    out->generation = generation;
    out->mode = HD_SKIN_TGT_MODE_VALID;
    return out->mode;
bad:
    memset(out, 0, sizeof(*out));
    out->mode = HD_SKIN_TGT_MODE_INVALID;
    return out->mode;
}

/* 1 if the key is listed in a VALID selection's catalog (BOUND or candidate): such draws must stay out of
 * the opaque batch (batched followers reuse the first draw's uniforms; the batch key has no UV bounds). */
static int hd_skin_target_key_listed(const HdSkinTargetSelection *sel, uint32_t texture, uint32_t palette) {
    int t, i;
    if (!sel || sel->mode != HD_SKIN_TGT_MODE_VALID || !sel->catalog) return 0;
    for (t = 0; t < sel->count; ++t)
        for (i = 0; i < sel->catalog[t].key_count; ++i)
            if (sel->catalog[t].keys[i].texture == texture && sel->catalog[t].keys[i].palette == palette) return 1;
    return 0;
}

static int hd_skin_target_resolve(const HdSkinTargetSelection *sel, const HdSkinDrawFacts *f, int *target_out) {
    int t, i, r, hits = 0, hit_t = -1, inside = 0;
    const HdSkinTargetKey *k = NULL;
    if (target_out) *target_out = -1;
    if (!sel || sel->mode == HD_SKIN_TGT_MODE_UNSET) return HD_SKIN_TGT_MODE_OFF;
    if (sel->mode != HD_SKIN_TGT_MODE_VALID || !sel->catalog) return HD_SKIN_TGT_MODE_REJECTED;
    if (!f) return HD_SKIN_TGT_UNKNOWN_KEY;
    for (t = 0; t < sel->count; ++t)
        for (i = 0; i < sel->catalog[t].key_count; ++i)
            if (sel->catalog[t].keys[i].texture == f->texture && sel->catalog[t].keys[i].palette == f->palette) {
                ++hits; hit_t = t; k = &sel->catalog[t].keys[i];
            }
    if (!hits) return HD_SKIN_TGT_UNKNOWN_KEY;
    if (hits > 1) return HD_SKIN_TGT_AMBIGUOUS_KEY;
    if (sel->catalog[hit_t].status != HD_SKIN_TARGET_BOUND) return HD_SKIN_TGT_TARGET_UNRESOLVED;
    if (!sel->profile[hit_t]) return HD_SKIN_TGT_STOCK_SELECTED;
    if (!f->hd_image) return HD_SKIN_TGT_NO_HD_IMAGE;
    if (f->hd_w != k->hd_w || f->hd_h != k->hd_h) return HD_SKIN_TGT_HD_SIZE_MISMATCH;
    if (!f->upload_serial) return HD_SKIN_TGT_NATIVE_FALLBACK;
    if (f->native_w != k->native_w || f->native_h != k->native_h) return HD_SKIN_TGT_NATIVE_SIZE_MISMATCH;
    if (f->page_x != k->page_x || f->page_y != k->page_y) return HD_SKIN_TGT_PAGE_MISMATCH;
    if (f->clut_x != k->clut_x || f->clut_y != k->clut_y) return HD_SKIN_TGT_CLUT_MISMATCH;
    if (f->u0 <= f->u1 && f->v0 <= f->v1)
        for (r = 0; r < k->rect_count && !inside; ++r)
            inside = f->u0 >= k->rects[r].u0 && f->u1 <= k->rects[r].u1 &&
                     f->v0 >= k->rects[r].v0 && f->v1 <= k->rects[r].v1;
    if (!inside) return HD_SKIN_TGT_OUTSIDE_RECTS;
    if (f->generation != sel->generation) return HD_SKIN_TGT_GENERATION_STALE;
    if (target_out) *target_out = hit_t;
    return HD_SKIN_TGT_APPLY;
}

/* The ONE decision used by both the draw and its proof receipt.
 * legacy = what the caller's existing hd_skin_for_draw returns for this key (may be NULL).
 * UNSET -> legacy; INVALID -> NULL (fail closed); VALID -> a one-key target config in *scratch or NULL. */
static const HdSkinConfig *hd_skin_target_decide(const HdSkinTargetSelection *sel, const HdSkinDrawFacts *f,
                                                 const HdSkinConfig *legacy, HdSkinConfig *scratch,
                                                 int *reason_out, int *target_out) {
    int target = -1;
    const int reason = hd_skin_target_resolve(sel, f, &target);
    if (reason_out) *reason_out = reason;
    if (target_out) *target_out = target;
    if (reason == HD_SKIN_TGT_MODE_OFF) return legacy;
    if (reason != HD_SKIN_TGT_APPLY || !scratch || !f) return NULL;
    memset(scratch, 0, sizeof(*scratch));
    scratch->profile = sel->profile[target];
    scratch->strength = sel->strength[target];
    scratch->enabled = scratch->strength > 0.0f;
    scratch->valid = 1;
    scratch->keys[0].texture = f->texture;
    scratch->keys[0].palette = f->palette;
    scratch->key_count = 1;
    return scratch;
}

#endif
