/* s67 pure authored controls r1 for hd_skin_targets.h r1 (NOT compiled or run; needs a grant).
 * Single-threaded, no GL, no files. Compile: cc -std=c11 -Wall -I<dir with r1 hd_skin_targets.h and the
 * UNCHANGED canonical hd_skin_material.h> test_hd_skin_targets.c -lm. Exit 0 PASS, 1 FAIL.
 * The caller-fallback section drives hd_skin_target_decide exactly as the proposed renderer does. */
#include "hd_skin_targets.h"
#include <stdio.h>

static int g_fail = 0, g_checks = 0;
#define CHECK(c) do { ++g_checks; if (!(c)) { g_fail = 1; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)
#define CAT hd_skin_targets, HD_SKIN_TARGET_COUNT

static HdSkinDrawFacts good(void) {     /* every gate satisfied for 724E77DA-21FDE894, gen 7 */
    HdSkinDrawFacts f;
    memset(&f, 0, sizeof f);
    f.texture = 0x724E77DAu; f.palette = 0x21FDE894u;
    f.hd_image = 1; f.hd_w = 1024; f.hd_h = 1024;
    f.upload_serial = 77; f.native_w = 64; f.native_h = 64;
    f.page_x = 832; f.page_y = 256; f.clut_x = 288; f.clut_y = 488;
    f.u0 = 156; f.v0 = 24; f.u1 = 190; f.v1 = 43;   /* exactly the most frequent observed rect */
    f.generation = 7;
    return f;
}

int main(void) {
    HdSkinTargetSelection s;
    HdSkinDrawFacts f;
    HdSkinConfig scratch, legacy;
    const HdSkinConfig *m;
    int t, r;

    memset(&legacy, 0, sizeof legacy);
    legacy.profile = hd_skin_find_profile("crimson-red"); legacy.strength = 0.75f; legacy.enabled = 1; legacy.valid = 1;

    CHECK(hd_skin_target_catalog_check(CAT) == 0);

    /* ---- modes and the caller fallback they produce */
    CHECK(hd_skin_target_selection_parse(&s, CAT, NULL, 7) == HD_SKIN_TGT_MODE_UNSET);
    f = good();
    m = hd_skin_target_decide(&s, &f, &legacy, &scratch, &r, &t);
    CHECK(m == &legacy && r == HD_SKIN_TGT_MODE_OFF);                         /* UNSET: legacy unchanged */
    CHECK(hd_skin_target_selection_parse(&s, CAT, "", 7) == HD_SKIN_TGT_MODE_UNSET);
    CHECK(hd_skin_target_decide(&s, &f, NULL, &scratch, &r, &t) == NULL && r == HD_SKIN_TGT_MODE_OFF);

    {
        static const char *bad[] = {
            "player.gunpods=aurora-teal",                                /* unresolved */
            "player.hull.shared_candidate=aurora-teal,boss=crimson-red", /* one unresolved */
            "player.hull=aurora-teal",                                   /* r0 id no longer exists */
            "player.hull.shared_candidate=not-a-profile",
            "player.hull.shared_candidate=aurora-teal@1.5",
            "player.hull.shared_candidate=aurora-teal@x",
            "player.hull.shared_candidate=stock@0.5",                    /* strength on stock */
            "player.hull.shared_candidate=aurora-teal,player.hull.shared_candidate=crimson-red",
            "player.hull.shared_candidate=stock,player.hull.shared_candidate=stock",  /* dup of stock entries */
            "player.hull.shared_candidate",
            "player.hull.shared_candidate=aurora-teal;",
            " , ",
        };
        int i;
        for (i = 0; i < (int)(sizeof bad / sizeof bad[0]); ++i) {
            CHECK(hd_skin_target_selection_parse(&s, CAT, bad[i], 7) == HD_SKIN_TGT_MODE_INVALID);
            f = good();
            m = hd_skin_target_decide(&s, &f, &legacy, &scratch, &r, &t);
            CHECK(m == NULL && r == HD_SKIN_TGT_MODE_REJECTED);                 /* INVALID: fail closed, legacy suppressed */
            f.texture = 0x3594C110u; f.palette = 0x527B28B9u;                  /* a legacy enemy key too */
            CHECK(hd_skin_target_decide(&s, &f, &legacy, &scratch, &r, &t) == NULL);
            CHECK(hd_skin_target_key_listed(&s, 0x724E77DAu, 0x21FDE894u) == 0);
        }
    }

    /* explicit "target=stock" is VALID and disables that target; legacy still suppressed */
    CHECK(hd_skin_target_selection_parse(&s, CAT, "player.hull.shared_candidate=stock", 7) == HD_SKIN_TGT_MODE_VALID);
    f = good();
    CHECK(hd_skin_target_decide(&s, &f, &legacy, &scratch, &r, &t) == NULL && r == HD_SKIN_TGT_STOCK_SELECTED);
    f.texture = 0x3594C110u; f.palette = 0x527B28B9u;
    CHECK(hd_skin_target_decide(&s, &f, &legacy, &scratch, &r, &t) == NULL && r == HD_SKIN_TGT_UNKNOWN_KEY);

    /* ---- VALID selection with a profile */
    CHECK(hd_skin_target_selection_parse(&s, CAT, " player.hull.shared_candidate=aurora-teal@0.5 ", 7) == HD_SKIN_TGT_MODE_VALID);
    CHECK(s.profile[0] && !strcmp(s.profile[0]->id, "aurora-teal") && s.strength[0] == 0.5f && s.generation == 7);
    f = good();
    m = hd_skin_target_decide(&s, &f, &legacy, &scratch, &r, &t);
    CHECK(m == &scratch && r == HD_SKIN_TGT_APPLY && t == 0);
    CHECK(m->valid && m->enabled && m->profile == s.profile[0] && m->strength == 0.5f && m->key_count == 1);
    CHECK(hd_skin_material_matches(m, 0x724E77DAu, 0x21FDE894u) && !hd_skin_material_matches(m, 0x7E3ADD56u, 0x21FDE894u));
    CHECK(!m->preserve_accents && !m->diagnostic_scope);
    /* legacy channel keys are stock in VALID mode (never the legacy pointer) */
    f.texture = 0x3594C110u; f.palette = 0x527B28B9u;
    m = hd_skin_target_decide(&s, &f, &legacy, &scratch, &r, &t);
    CHECK(m == NULL && r == HD_SKIN_TGT_UNKNOWN_KEY);

    /* ---- each gate refuses on its own (VALID mode) */
#define REFUSE(mut, want) do { f = good(); mut; CHECK(hd_skin_target_resolve(&s, &f, &t) == (want) && t == -1); } while (0)
    REFUSE(f.texture = 0x12345678u, HD_SKIN_TGT_UNKNOWN_KEY);
    REFUSE(f.palette = 0x053D9A00u, HD_SKIN_TGT_UNKNOWN_KEY);
    REFUSE((f.texture = 0x5CC44E5Fu, f.palette = 0x053D9A00u), HD_SKIN_TGT_TARGET_UNRESOLVED);
    REFUSE(f.hd_image = 0, HD_SKIN_TGT_NO_HD_IMAGE);
    REFUSE(f.hd_w = 512, HD_SKIN_TGT_HD_SIZE_MISMATCH);
    REFUSE(f.upload_serial = 0, HD_SKIN_TGT_NATIVE_FALLBACK);
    REFUSE((f.native_w = 256, f.native_h = 8), HD_SKIN_TGT_NATIVE_SIZE_MISMATCH);
    REFUSE(f.page_x = 896, HD_SKIN_TGT_PAGE_MISMATCH);
    REFUSE(f.clut_y = 489, HD_SKIN_TGT_CLUT_MISMATCH);
    REFUSE(f.u1 = 191, HD_SKIN_TGT_OUTSIDE_RECTS);                                   /* one texel past */
    REFUSE((f.u0 = 191, f.u1 = 150), HD_SKIN_TGT_OUTSIDE_RECTS);                     /* inverted */
    /* HOLE: inside the min/max envelope [130,21-190,60] but in no single rect (row v=44 is uncovered) */
    REFUSE((f.u0 = 156, f.v0 = 40, f.u1 = 190, f.v1 = 48), HD_SKIN_TGT_OUTSIDE_RECTS);
    /* envelope corner region with no observed rect at all */
    REFUSE((f.u0 = 130, f.v0 = 54, f.u1 = 140, f.v1 = 60), HD_SKIN_TGT_OUTSIDE_RECTS);
    REFUSE(f.generation = 8, HD_SKIN_TGT_GENERATION_STALE);
    /* a sub-box of one rect and a rect's exact edges both apply */
    f = good(); f.u0 = 160; f.v0 = 30; f.u1 = 170; f.v1 = 40;   CHECK(hd_skin_target_resolve(&s, &f, &t) == HD_SKIN_TGT_APPLY);
    f = good(); f.u0 = 171; f.v0 = 54; f.u1 = 190; f.v1 = 60;   CHECK(hd_skin_target_resolve(&s, &f, &t) == HD_SKIN_TGT_APPLY);

    /* every vetted rect of every hull key applies with that key's facts */
    {
        int i, j;
        for (i = 0; i < 4; ++i) {
            const HdSkinTargetKey *k = &hd_skin_target_hull_keys[i];
            for (j = 0; j < k->rect_count; ++j) {
                f = good(); f.texture = k->texture; f.palette = k->palette; f.page_x = k->page_x; f.page_y = k->page_y;
                f.u0 = k->rects[j].u0; f.v0 = k->rects[j].v0; f.u1 = k->rects[j].u1; f.v1 = k->rects[j].v1;
                CHECK(hd_skin_target_resolve(&s, &f, &t) == HD_SKIN_TGT_APPLY && t == 0);
            }
        }
    }

    /* reason names cover every code */
    for (r = 0; r < HD_SKIN_TGT_REASON_COUNT; ++r) CHECK(hd_skin_target_reason_name(r) && hd_skin_target_reason_name(r)[0]);
    CHECK(!strcmp(hd_skin_target_reason_name(HD_SKIN_TGT_OUTSIDE_RECTS), "outside_rects"));

    /* batch-exclusion helper: VALID mode only */
    CHECK(hd_skin_target_key_listed(&s, 0x724E77DAu, 0x21FDE894u) == 1);
    CHECK(hd_skin_target_key_listed(&s, 0x5CC44E5Fu, 0x053D9A00u) == 1);
    CHECK(hd_skin_target_key_listed(&s, 0x3594C110u, 0x527B28B9u) == 0);

    /* ---- synthetic catalogs: cross-target fallback, ambiguity, shared rects, structural checks */
    {
        static const HdSkinTargetRect ra[] = {{0,0,63,63}}, rb[] = {{0,0,63,63}};
        static const HdSkinTargetKey ka[] = {{0xAAAA0001u,0x11110000u, 0,0, 0,480, ra,1, 64,64, 1024,1024}};
        static const HdSkinTargetKey kb[] = {{0xBBBB0001u,0x22220000u, 64,0, 0,481, rb,1, 64,64, 1024,1024}};
        static const HdSkinTarget two[] = {{"a","a",HD_SKIN_TARGET_BOUND,ka,1,NULL},{"b","b",HD_SKIN_TARGET_BOUND,kb,1,NULL}};
        CHECK(hd_skin_target_catalog_check(two, 2) == 0);
        CHECK(hd_skin_target_selection_parse(&s, two, 2, "a=solar-orange", 3) == HD_SKIN_TGT_MODE_VALID);
        f = good(); f.generation = 3; f.texture = 0xBBBB0001u; f.palette = 0x22220000u; f.page_x = 64; f.page_y = 0;
        f.clut_x = 0; f.clut_y = 481; f.u0 = 0; f.v0 = 0; f.u1 = 10; f.v1 = 10;
        CHECK(hd_skin_target_decide(&s, &f, &legacy, &scratch, &r, &t) == NULL && r == HD_SKIN_TGT_STOCK_SELECTED);  /* no fallback */
        f.texture = 0xAAAA0001u; f.palette = 0x11110000u; f.page_x = 0; f.clut_y = 480;
        CHECK(hd_skin_target_decide(&s, &f, &legacy, &scratch, &r, &t) == &scratch && r == HD_SKIN_TGT_APPLY && t == 0);
    }
    {
        static const HdSkinTargetRect r1[] = {{0,0,31,31}}, r2[] = {{32,32,63,63}}, r3[] = {{0,0,40,40}},
                                      r4[] = {{30,30,63,63}}, r5[] = {{41,41,63,63}}, bad_r[] = {{9,0,3,5}};
        static const HdSkinTargetKey dupk1[] = {{0xCCCC0001u,0x33330000u, 0,0, 0,482, r1,1, 64,64, 1024,1024}};
        static const HdSkinTargetKey dupk2[] = {{0xCCCC0001u,0x33330000u, 0,0, 0,482, r2,1, 64,64, 1024,1024}};
        static const HdSkinTarget dup[] = {{"x","x",HD_SKIN_TARGET_BOUND,dupk1,1,NULL},{"y","y",HD_SKIN_TARGET_BOUND,dupk2,1,NULL}};
        static const HdSkinTargetKey sk1[] = {{0xDDDD0001u,0x44440000u, 0,0, 0,483, r3,1, 64,64, 1024,1024}};
        static const HdSkinTargetKey sk2[] = {{0xDDDD0002u,0x44440000u, 0,0, 0,483, r4,1, 64,64, 1024,1024}};
        static const HdSkinTargetKey sk3[] = {{0xDDDD0002u,0x44440000u, 0,0, 0,483, r5,1, 64,64, 1024,1024}};
        static const HdSkinTarget shared[] = {{"p","p",HD_SKIN_TARGET_BOUND,sk1,1,NULL},{"q","q",HD_SKIN_TARGET_BOUND,sk2,1,NULL}};
        static const HdSkinTarget disjoint[] = {{"p","p",HD_SKIN_TARGET_BOUND,sk1,1,NULL},{"q","q",HD_SKIN_TARGET_BOUND,sk3,1,NULL}};
        static const HdSkinTargetKey badrect[] = {{0xEEEE0001u,0x55550000u, 0,0, 0,484, bad_r,1, 64,64, 1024,1024}};
        static const HdSkinTargetKey norects[] = {{0xEEEE0002u,0x55550000u, 0,0, 0,484, NULL,0, 64,64, 1024,1024}};
        static const HdSkinTarget c_bound_nokeys[] = {{"u","u",HD_SKIN_TARGET_BOUND,NULL,0,NULL}};
        static const HdSkinTarget c_unres_nullkeys[] = {{"v","v",HD_SKIN_TARGET_UNRESOLVED,NULL,2,"r"}};   /* r0 would deref NULL */
        static const HdSkinTarget c_negative[] = {{"w","w",HD_SKIN_TARGET_UNRESOLVED,NULL,-1,"r"}};
        static const HdSkinTarget c_oversize[] = {{"w","w",HD_SKIN_TARGET_UNRESOLVED,sk1,HD_SKIN_TARGET_MAX_KEYS + 1,"r"}};
        static const HdSkinTarget c_status[] = {{"s","s",7,sk1,1,NULL}};
        static const HdSkinTarget c_dupid[] = {{"z","z",HD_SKIN_TARGET_BOUND,sk1,1,NULL},{"z","z2",HD_SKIN_TARGET_BOUND,sk3,1,NULL}};
        static const HdSkinTarget c_noid[] = {{"","",HD_SKIN_TARGET_BOUND,sk1,1,NULL}};
        static const HdSkinTarget c_badrect[] = {{"b","b",HD_SKIN_TARGET_BOUND,badrect,1,NULL}};
        static const HdSkinTarget c_norects[] = {{"n","n",HD_SKIN_TARGET_BOUND,norects,1,NULL}};
        HdSkinTargetSelection amb;
        CHECK(hd_skin_target_catalog_check(dup, 2) == 4);
        CHECK(hd_skin_target_selection_parse(&s, dup, 2, "x=aurora-teal", 0) == HD_SKIN_TGT_MODE_INVALID);
        CHECK(hd_skin_target_catalog_check(shared, 2) == 5);
        CHECK(hd_skin_target_selection_parse(&s, shared, 2, "p=aurora-teal", 0) == HD_SKIN_TGT_MODE_INVALID);
        CHECK(hd_skin_target_catalog_check(disjoint, 2) == 0);
        CHECK(hd_skin_target_catalog_check(c_bound_nokeys, 1) == 2);
        CHECK(hd_skin_target_catalog_check(c_unres_nullkeys, 1) == 9);
        CHECK(hd_skin_target_catalog_check(c_negative, 1) == 8);
        CHECK(hd_skin_target_catalog_check(c_oversize, 1) == 8);
        CHECK(hd_skin_target_catalog_check(c_status, 1) == 6);
        CHECK(hd_skin_target_catalog_check(c_dupid, 2) == 7);
        CHECK(hd_skin_target_catalog_check(c_noid, 1) == 1);
        CHECK(hd_skin_target_catalog_check(c_badrect, 1) == 3);
        CHECK(hd_skin_target_catalog_check(c_norects, 1) == 3);
        CHECK(hd_skin_target_catalog_check(NULL, 0) == 1);
        /* resolve still refuses an ambiguous key if a corrupt selection bypassed the check */
        memset(&amb, 0, sizeof amb);
        amb.mode = HD_SKIN_TGT_MODE_VALID; amb.catalog = dup; amb.count = 2;
        amb.profile[0] = amb.profile[1] = hd_skin_find_profile("aurora-teal"); amb.strength[0] = amb.strength[1] = 0.75f;
        f = good(); f.texture = 0xCCCC0001u; f.palette = 0x33330000u;
        CHECK(hd_skin_target_decide(&amb, &f, &legacy, &scratch, &r, &t) == NULL && r == HD_SKIN_TGT_AMBIGUOUS_KEY);
    }

    /* canonical channels are untouched by this header */
    CHECK(hd_skin_find_profile("aurora-teal") != NULL && HD_SKIN_PROFILE_COUNT == 14);
    CHECK(hd_skin_keys_valid("724E77DA-21FDE894") == 1 && hd_skin_keys_valid("5CC44E5F-053D9A00") == 1);

    printf("{\"checks\":%d,\"result\":\"%s\"}\n", g_checks, g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
