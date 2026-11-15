#!/usr/bin/env python3
"""Build the PRIVATE view-provenance v3 patch (claude-einhander). Source generation only. Inputs are the delivered v2
OUTPUT files (hash-pinned against ../impl-v2/patch-receipt.json; the v2 folder is read, never written) - canonical runtime
files are untouched. Diffs are produced against the canonical bases too.

v3 answers my adapter review (claude-backlog/remix-review/SCENE-PACKET-REVIEW.md items 1, 2 and 6):
  * census per kind: FRAME-LAG histogram of hits (draw frame - view frame mod 2^32: 0, 1, 2, >=3, future; plus a wrap count) - measures whether a
    same-frame rule would reject real draws;
  * census per kind: per-flag HIT split (XY_SAT, XY_CLAMP, IR_SAT, DIV_OVF, SZ_SAT, WS_SQUASH, DOME, any MAC OVF44, any MAC
    WRAP32) - measures what a blanket NATIVE_DIVERGED/WS rejection would drop;
  * gte.cpp: gte_rtp_ring_xform_hash(seq, &hash) recomputes the FNV xform hash (RT, TR, H, OFX, OFY) of a LIVE ring record;
    census counter hit_xform_match = committed hits whose live ring record re-hashes to the view's xform_hash (an
    independent check that also covers V components equal to 0, where the MAC re-check cannot constrain RT);
  * gte.cpp: gte_rtp_ring_get_projection(seq, &h, &ofx, &ofy) - sibling accessor exposing H/OFX/OFY of a live record;
  * pgxp.h: declarations for the ring accessors (seq_live / get_xform / get_projection / xform_hash) for consumers;
  * debug_server.c: pgxp_view reply gains "lag", "hit_flags" and "hit_xform_match" per kind.
Default OFF; no render or guest-state change; no printf."""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent / "impl-v2"
RT = Path("C:/github/Einhander/windows-x64/psxrecomp/runtime")
FILES = ["include/pgxp.h", "src/pgxp.cpp", "src/gte.cpp", "src/gpu.c", "include/gpu.h", "src/debug_server.c",
         "src/pgxp_view_census.cpp"]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def apply(text, edits, name):
    for i, (old, new) in enumerate(edits):
        n = text.count(old)
        if n != 1:
            raise SystemExit(f"{name} edit {i}: anchor found {n} times:\n{old[:300]}")
        text = text.replace(old, new)
    return text


H_KIND_OLD = """    uint64_t all_hit_one_command;    /* all-hit and every vertex committed from *
                                      * the same GTE command (one rtp_seq)      */
} PgxpViewCensusKind;
"""
H_KIND_NEW = """    uint64_t all_hit_one_command;    /* all-hit and every vertex committed from *
                                      * the same GTE command (one rtp_seq)      */
    /* v3 */
    uint64_t lag[5];                 /* hits by draw frame - view frame, mod   *
                                      * 2^32: [0]=0 [1]=1 [2]=2 [3]=>=3         *
                                      * [4]=future (view frame after the draw) */
    uint64_t lag_wrapped;            /* past lags that crossed the 32-bit      *
                                      * frame-counter wrap (also in [0..3])    */
    uint64_t hit_flag[PGXP_VIEW_CENSUS_FLAG_COUNT]; /* hits carrying each flag */
    uint64_t hit_xform_match;        /* committed hits whose LIVE ring record  *
                                      * re-hashes to the view's xform_hash     */
} PgxpViewCensusKind;
"""
H_FLAGENUM_OLD = "typedef struct PgxpViewCensusKind {\n"
H_FLAGENUM_NEW = """/* v3: per-flag hit split indices (PgxpViewCensusKind.hit_flag) */
enum {
    PGXP_VIEW_CENSUS_FLAG_XY_SAT = 0, PGXP_VIEW_CENSUS_FLAG_XY_CLAMP, PGXP_VIEW_CENSUS_FLAG_IR_SAT,
    PGXP_VIEW_CENSUS_FLAG_DIV_OVF, PGXP_VIEW_CENSUS_FLAG_SZ_SAT, PGXP_VIEW_CENSUS_FLAG_WS_SQUASH,
    PGXP_VIEW_CENSUS_FLAG_DOME, PGXP_VIEW_CENSUS_FLAG_MAC_OVF44, PGXP_VIEW_CENSUS_FLAG_MAC_WRAP32,
    PGXP_VIEW_CENSUS_FLAG_COUNT
};

typedef struct PgxpViewCensusKind {
"""
H_RING_OLD = "void pgxp_test_view_census_fail_ring_alloc(int count);\n"
H_RING_NEW = """void pgxp_test_view_census_fail_ring_alloc(int count);

/* gte.cpp GTE projection ring accessors (records exist only in builds with
 * debug tools; every accessor returns 0 for a record that was never written or
 * has been overwritten). v3 adds the xform re-hash: FNV-1a over RT, TR, H,
 * OFX, OFY of the live record, the same function the producer stores in
 * PgxpView.xform_hash. */
int gte_rtp_ring_seq_live(uint64_t seq);
int gte_rtp_ring_get_xform(uint64_t seq, int16_t rt[9], int32_t tr[3],
                           uint32_t *frame, uint32_t *caller_ra);
int gte_rtp_ring_xform_hash(uint64_t seq, uint32_t *hash);
int gte_rtp_ring_get_projection(uint64_t seq, uint16_t *h, int32_t *ofx,
                                int32_t *ofy);
"""

GTE_OLD = """    if (frame) *frame = e->frame;
    if (caller_ra) *caller_ra = e->caller_ra;
    return 1;
}
"""
GTE_NEW = """    if (frame) *frame = e->frame;
    if (caller_ra) *caller_ra = e->caller_ra;
    return 1;
}

/* v3: re-hash a live record exactly as the producer hashed the transform in
 * force (consumers compare it with PgxpView.xform_hash). */
extern "C" int gte_rtp_ring_xform_hash(uint64_t seq, uint32_t *hash) {
    if (!gte_rtp_ring_seq_live(seq)) return 0;
    const GteRtpRec *e = &s_gte_rtp_ring[seq % GTE_RTP_RING_CAP];
    int16_t rt[3][3];
    for (int r = 0; r < 3; r++)
        for (int c = 0; c < 3; c++) rt[r][c] = e->RT[r * 3 + c];
    if (hash) *hash = gte_view_xform_hash(rt, e->TR, e->H, e->OFX, e->OFY);
    return 1;
}

/* v3: projection parameters of a live record (sibling of get_xform). */
extern "C" int gte_rtp_ring_get_projection(uint64_t seq, uint16_t *h,
                                           int32_t *ofx, int32_t *ofy) {
    if (!gte_rtp_ring_seq_live(seq)) return 0;
    const GteRtpRec *e = &s_gte_rtp_ring[seq % GTE_RTP_RING_CAP];
    if (h) *h = e->H;
    if (ofx) *ofx = e->OFX;
    if (ofy) *ofy = e->OFY;
    return 1;
}
"""

CEN_DECL_OLD = "extern \"C\" int gte_rtp_ring_seq_live(uint64_t seq);\n"
CEN_DECL_NEW = ""   # now declared in pgxp.h
CEN_HIT_OLD = """            if (committed) {
                k->hit_committed++;
                if (gte_rtp_ring_seq_live(v.rtp_seq)) k->hit_ring_live++;
            }
            if (v.flags & PGXP_VIEW_NATIVE_DIVERGED) k->hit_diverged++;
"""
CEN_HIT_NEW = """            if (committed) {
                k->hit_committed++;
                if (gte_rtp_ring_seq_live(v.rtp_seq)) k->hit_ring_live++;
                uint32_t xh = 0;
                if (gte_rtp_ring_xform_hash(v.rtp_seq, &xh) && xh == v.xform_hash)
                    k->hit_xform_match++;
            }
            if (v.flags & PGXP_VIEW_NATIVE_DIVERGED) k->hit_diverged++;
            {   /* v3: frame lag and per-flag split of hits */
                const uint32_t d = rec.frame - v.frame;          /* mod 2^32 */
                if (d >= 0x80000000u) {
                    k->lag[4]++;                                  /* future   */
                } else {
                    k->lag[d > 3u ? 3 : (int)d]++;
                    if (rec.frame < v.frame) k->lag_wrapped++;    /* crossed  */
                }
                static const uint16_t kFlag[PGXP_VIEW_CENSUS_FLAG_COUNT] = {
                    PGXP_VIEW_XY_SAT, PGXP_VIEW_XY_CLAMP, PGXP_VIEW_IR_SAT,
                    PGXP_VIEW_DIV_OVF, PGXP_VIEW_SZ_SAT, PGXP_VIEW_WS_SQUASH,
                    PGXP_VIEW_DOME,
                    (uint16_t)(PGXP_VIEW_MAC1_OVF44 | PGXP_VIEW_MAC2_OVF44 | PGXP_VIEW_MAC3_OVF44),
                    (uint16_t)(PGXP_VIEW_MAC1_WRAP32 | PGXP_VIEW_MAC2_WRAP32 | PGXP_VIEW_MAC3_WRAP32) };
                for (int f = 0; f < PGXP_VIEW_CENSUS_FLAG_COUNT; f++)
                    if (v.flags & kFlag[f]) k->hit_flag[f]++;
            }
"""

DBG_OLD = """        for (int r = 1; r < PGXP_VIEW_MISS_COUNT; r++)
            PV_APPEND("%s\\"%s\\":%llu", r == 1 ? "" : ",", kMiss[r],
                      (unsigned long long)q->miss[r]);
        PV_APPEND("}},");
"""
DBG_NEW = """        for (int r = 1; r < PGXP_VIEW_MISS_COUNT; r++)
            PV_APPEND("%s\\"%s\\":%llu", r == 1 ? "" : ",", kMiss[r],
                      (unsigned long long)q->miss[r]);
        /* v3: frame lag of hits, per-flag hit split, xform re-hash matches */
        PV_APPEND("},\\"lag\\":{\\"0\\":%llu,\\"1\\":%llu,\\"2\\":%llu,\\"3plus\\":%llu,"
                  "\\"future\\":%llu,\\"wrapped\\":%llu},\\"hit_xform_match\\":%llu,\\"hit_flags\\":{",
                  (unsigned long long)q->lag[0], (unsigned long long)q->lag[1],
                  (unsigned long long)q->lag[2], (unsigned long long)q->lag[3],
                  (unsigned long long)q->lag[4], (unsigned long long)q->lag_wrapped,
                  (unsigned long long)q->hit_xform_match);
        {
            static const char *const kFlagName[PGXP_VIEW_CENSUS_FLAG_COUNT] = {
                "xy_sat", "xy_clamp", "ir_sat", "div_ovf", "sz_sat", "ws_squash",
                "dome", "mac_ovf44", "mac_wrap32" };
            for (int f = 0; f < PGXP_VIEW_CENSUS_FLAG_COUNT; f++)
                PV_APPEND("%s\\"%s\\":%llu", f == 0 ? "" : ",", kFlagName[f],
                          (unsigned long long)q->hit_flag[f]);
        }
        PV_APPEND("}},");
"""


def main():
    rec = json.loads((V2 / "patch-receipt.json").read_text(encoding="utf-8"))
    receipt = dict(v2_receipt_sha256=sha((V2 / "patch-receipt.json").read_bytes()), bases={}, outputs={},
                   generator_sha256=sha(Path(__file__).read_bytes()))
    text, fmt = {}, {}
    for rel in FILES:
        b = (V2 / rel).read_bytes()
        want = rec["outputs"][rel]["sha256"]
        if sha(b) != want:
            raise SystemExit(f"v2 output {rel} changed; refusing")
        bom = b.startswith(b"\xef\xbb\xbf")
        s = b.decode("utf-8-sig" if bom else "utf-8")
        fmt[rel] = (bom, "\r\n" in s)
        text[rel] = s.replace("\r\n", "\n")
        receipt["bases"][rel] = dict(path=str(V2 / rel), sha256=want)
    t = dict(text)
    t["include/pgxp.h"] = apply(t["include/pgxp.h"], [(H_FLAGENUM_OLD, H_FLAGENUM_NEW), (H_KIND_OLD, H_KIND_NEW),
                                                      (H_RING_OLD, H_RING_NEW)], "pgxp.h")
    t["src/gte.cpp"] = apply(t["src/gte.cpp"], [(GTE_OLD, GTE_NEW)], "gte.cpp")
    t["src/pgxp_view_census.cpp"] = apply(t["src/pgxp_view_census.cpp"], [(CEN_DECL_OLD, CEN_DECL_NEW), (CEN_HIT_OLD, CEN_HIT_NEW)],
                                          "census")
    t["src/debug_server.c"] = apply(t["src/debug_server.c"], [(DBG_OLD, DBG_NEW)], "debug_server.c")
    (HERE / "diffs").mkdir(exist_ok=True)
    for rel in FILES:
        bom, crlf = fmt[rel]
        s = t[rel]
        data = (b"\xef\xbb\xbf" if bom else b"") + (s.replace("\n", "\r\n") if crlf else s).encode("utf-8")
        p = HERE / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        out = dict(path=str(p), sha256=sha(data), changed_vs_v2=(s != text[rel]))
        canon = RT / rel
        base_txt = canon.read_bytes().decode("utf-8-sig").replace("\r\n", "\n") if canon.exists() else ""
        d = "".join(difflib.unified_diff(base_txt.splitlines(True), s.splitlines(True),
                                         f"a/windows-x64/psxrecomp/runtime/{rel}", f"b/windows-x64/psxrecomp/runtime/{rel}"))
        dp = HERE / "diffs" / (Path(rel).name + ".diff")
        dp.write_text(d, encoding="utf-8", newline="\n")
        out["diff_vs_canonical"] = dict(path=str(dp), sha256=sha(dp.read_bytes()), lines=d.count("\n"))
        receipt["outputs"][rel] = out
    (HERE / "patch-receipt.json").write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: (v["sha256"][:16], v["changed_vs_v2"], v["diff_vs_canonical"]["lines"]) for k, v in receipt["outputs"].items()}, indent=1))


if __name__ == "__main__":
    main()
