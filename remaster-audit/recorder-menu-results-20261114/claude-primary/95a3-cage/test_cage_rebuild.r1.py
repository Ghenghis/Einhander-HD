"""Synthetic tests for cage_rebuild.r1.py (claude-einhander). Tiny arrays only; no real page is written.
Run: python test_cage_rebuild.r1.py   (or python -m pytest test_cage_rebuild.r1.py)"""
import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_var] = "1"

import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("cage_rebuild_r1", HERE / "cage_rebuild.r1.py")
cr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cr)

# 857DB48E-like palette: monotone ramp, saturated blue at 5, STP black at 15 (class 255)
PAL = dict(rgb=[[216, 224, 248], [168, 192, 224], [128, 152, 176], [80, 96, 136], [56, 72, 88], [8, 56, 144],
                [24, 40, 72], [16, 40, 56], [16, 32, 48], [8, 24, 40], [8, 24, 32], [8, 16, 24], [0, 8, 16],
                [0, 0, 8], [0, 0, 8], [0, 0, 0]],
           stp=[0] * 15 + [1])
P = np.array(PAL["rgb"], np.int64)
CLS = cr.class_of(PAL)


def raw_clut(pal):
    rgb = np.array(pal["rgb"], np.int64) >> 3
    return (rgb[:, 0] | (rgb[:, 1] << 5) | (rgb[:, 2] << 10) | (np.array(pal["stp"], np.int64) << 15)).astype(np.uint16)


def rng_field(seed, H=12, W=10):
    return np.random.default_rng(seed).integers(0, 16, size=(H, W))


def test_classes_and_void():
    assert CLS.tolist() == [127] * 15 + [255]
    v = cr.void_mask(np.arange(16)[None, :], P)
    assert v[0].tolist() == [False] * 15 + [True]


def test_palette_refusals():
    cr.palette_classes("ok", PAL, raw_clut(PAL))
    bad_t = dict(rgb=PAL["rgb"], stp=[0] * 16)                       # entry 15 transparent black -> class 0
    for pal, clut in ((bad_t, None), (PAL, np.where(np.arange(16) == 3, 0, raw_clut(PAL)).astype(np.uint16)),
                      (PAL, (raw_clut(PAL) ^ np.uint16(1)).astype(np.uint16))):
        try:
            cr.palette_classes("bad", pal, clut)
        except RuntimeError:
            continue
        raise AssertionError("refusal expected")


def test_crisp_large_step_and_smooth_small_step():
    s = 8
    O = np.array([[0, 3]])                                   # max step 136 >= TAU: crisp
    F = cr.render_field(O, P, cr.void_mask(O, P), s)
    assert np.allclose(F[:, :s], P[0]) and np.allclose(F[:, s:], P[3])
    O = np.array([[0, 1]])                                   # max step 48 < TAU: smoothed toward each other
    F = cr.render_field(O, P, cr.void_mask(O, P), s)
    left, right = F[:, :s], F[:, s:]
    assert left[:, -1].mean() < P[0].mean() and right[:, 0].mean() > P[1].mean()
    assert np.allclose(left[:, :s // 2], P[0])               # far half of each cell sees only the region edge
    assert not np.allclose(left.min(axis=(0, 1)), left.max(axis=(0, 1)))


def test_void_never_blends():
    s = 8
    O = np.array([[1, 15, 1], [1, 15, 1]])
    void = cr.void_mask(O, P)
    F = cr.render_field(O, P, void, s)
    assert np.allclose(F[:, s:2 * s], 0)                    # void blocks exact black
    # non-void cells only see the other non-void texel of their own column (vertical, identical colour)
    assert np.allclose(F[:, :s], P[1]) and np.allclose(F[:, 2 * s:], P[1])


def test_mean_exact_and_round_exact_sums():
    s = 8
    for seed in range(6):
        O = rng_field(seed)
        void = cr.void_mask(O, P)
        roi, st = cr.render_roi(O, P, CLS, void, s)
        sums = roi[..., :3].astype(np.int64).reshape(O.shape[0], s, O.shape[1], s, 3).sum(axis=(1, 3))
        assert np.array_equal(sums, P[O] * s * s), seed
        assert st["rounding_out_of_range"] == 0
        blk = roi[..., 3].reshape(O.shape[0], s, O.shape[1], s)
        assert np.array_equal(blk.min(axis=(1, 3)), CLS[O]) and np.array_equal(blk.max(axis=(1, 3)), CLS[O])


def test_mean_exact_extreme_targets_no_clip():
    s = 8
    pal = np.array([[255, 255, 255], [0, 0, 0], [255, 0, 0], [0, 255, 8]] + [[8, 8, 8]] * 12, np.int64)
    O = np.array([[0, 1, 2, 3], [3, 2, 1, 0]])
    void = cr.void_mask(O, pal)
    F = np.full((2 * s, 4 * s, 3), 128.0)                    # far from every target
    X = cr.mean_exact(F, O, pal, void, s)
    m = X.reshape(2, s, 4, s, 3).mean(axis=(1, 3))
    assert np.abs(m - pal[O]).max() < 1e-9 and X.min() >= 0 and X.max() <= 255
    rgb, oor = cr.round_exact(X, O, pal, s)
    assert oor == 0 and np.array_equal(rgb.astype(np.int64).reshape(2, s, 4, s, 3).sum(axis=(1, 3)), pal[O] * s * s)


def _page_case(seed=3):
    s = 8
    rng = np.random.default_rng(seed)
    parent = rng.integers(0, 256, size=(32 * s, 32 * s, 4), dtype=np.uint8)
    bbox = (8, 4, 18, 16)
    O = rng.integers(0, 16, size=(12, 10))
    void = cr.void_mask(O, P)
    roi, st = cr.render_roi(O, P, CLS, void, s)
    page = cr.apply_page(parent, bbox, roi, s)
    return parent, page, bbox, O, void, st, s


def test_validate_pass_and_each_failure():
    parent, page, bbox, O, void, st, s = _page_case()
    g, d = cr.validate(parent, page, page.copy(), bbox, O, P, CLS, void, st, s)
    assert all(g.values()) and set(g) == set(cr.GATES), g
    out = page.copy(); out[0, 0, 0] ^= 1                     # outside the ROI
    g, _ = cr.validate(parent, out, out, bbox, O, P, CLS, void, st, s)
    assert not g["outside_roi_identical_to_parent"]
    al = page.copy(); al[4 * s + 1, 8 * s + 1, 3] ^= 0x80   # one alpha pixel inside the ROI (not a centre)
    g, _ = cr.validate(parent, al, al, bbox, O, P, CLS, void, st, s)
    assert not g["alpha_uniform_per_block"] and g["centre_alpha_equals_native_class"]
    rgb = page.copy(); y, x = 4 * s + 2, 8 * s + 3; rgb[y, x, 1] = 255 if rgb[y, x, 1] < 255 else 254
    g, _ = cr.validate(parent, rgb, rgb, bbox, O, P, CLS, void, st, s)
    assert not g["block_sums_equal_native_exactly"]
    g, _ = cr.validate(parent, page, parent, bbox, O, P, CLS, void, st, s)
    assert not g["readback_equals_written"]
    g, _ = cr.validate(parent, page, page, bbox, O, P, CLS, void, dict(st, rounding_out_of_range=1), s)
    assert not g["rounding_in_range"]
    vo = np.argwhere(void)
    if len(vo):
        r, c = vo[0]
        vv = page.copy(); vv[(4 + r) * s, (8 + c) * s, 2] = 8
        g, _ = cr.validate(parent, vv, vv, bbox, O, P, CLS, void, st, s)
        assert not g["void_blocks_exact_native"]


def _ctx(parent, bbox, O, void):
    return dict(R="C", region_id="C_barred_window_cage", key="95A3BCF8-857DB48E", palette="857DB48E", bbox=bbox,
                O=O, cls=CLS, P=P, void=void, parent=parent, parent_info=dict(path="synthetic", sha256="0" * 64),
                native=dict(synthetic=True), census=dict(synthetic=True))


def _verify_sums(F):
    for line in (F / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        h, rel = line.split("  ", 1)
        assert hashlib.sha256((F / rel).read_bytes()).hexdigest() == h, rel


def test_freeze_ready_then_failed_marker():
    parent, page, bbox, O, void, st, s = _page_case(5)
    with tempfile.TemporaryDirectory() as td:
        F = Path(td) / "frozen" / "set-ok"
        rc = cr.freeze(_ctx(parent, bbox, O, void), F, dict(sources={}, pin=None), s)
        assert rc == 0 and (F / "READY.json").exists() and not (F / "FAILED.json").exists()
        _verify_sums(F)
        man = json.loads((F / "manifest.json").read_text(encoding="utf-8"))
        assert man["region"] == "C_barred_window_cage uv [8,4]-[18,16] half-open (t3-green-lights/regions.json)"
        assert man["why"] and man["method"].startswith("* Void texels") and man["bindings"]
        assert man["keys"]["95A3BCF8-857DB48E"]["live"]["sha256"] == "0" * 64
        assert (F / "cage_rebuild.r1.py").exists()
        try:
            cr.freeze(_ctx(parent, bbox, O, void), F, dict(sources={}, pin=None), s)
            raise AssertionError("existing frozen dir must be refused")
        except FileExistsError:
            pass
        orig = cr.round_exact
        cr.round_exact = lambda X, O_, P_, s_=8: (orig(X, O_, P_, s_)[0], 1)
        try:
            F2 = Path(td) / "frozen" / "set-fail"
            rc = cr.freeze(_ctx(parent, bbox, O, void), F2, dict(sources={}, pin=None), s)
        finally:
            cr.round_exact = orig
        assert rc == 1 and (F2 / "FAILED.json").exists() and not (F2 / "READY.json").exists()
        _verify_sums(F2)
        assert json.loads((F2 / "FAILED.json").read_text(encoding="utf-8"))["failed_checks"] == ["rounding_in_range"]


def test_freeze_with_read_only_builder_source():
    """r1 regression (CG2 18:04:55Z): a read-only builder source must still give READY with verified sums."""
    import shutil, stat
    parent, page, bbox, O, void, st, s = _page_case(7)
    with tempfile.TemporaryDirectory() as td:
        ro = Path(td) / "builder-ro.py"
        shutil.copyfile(HERE / "cage_rebuild.r1.py", ro)
        os.chmod(ro, stat.S_IREAD)
        try:
            F = Path(td) / "frozen" / "set-ro"
            rc = cr.freeze(_ctx(parent, bbox, O, void), F, dict(sources={}, pin=None), s, builder=ro)
            assert rc == 0 and (F / "READY.json").exists() and not (F / "FAILED.json").exists()
            _verify_sums(F)
            assert (F / "builder-ro.py").read_bytes() == ro.read_bytes()
        finally:
            os.chmod(ro, stat.S_IREAD | stat.S_IWRITE)
            for q in Path(td).rglob("*"):
                if q.is_file():
                    os.chmod(q, stat.S_IREAD | stat.S_IWRITE)


def test_real_region_inputs_readonly():
    """Read-only on the real index map and palette (no page): C classes, void set and edge split."""
    if not (cr.IDX.exists() and cr.PALS.exists()):
        return
    idx = np.load(cr.IDX)
    pal = json.loads(cr.PALS.read_text(encoding="utf-8"))["857DB48E"]
    u0, v0, u1, v1 = cr.REGION["bbox"]
    O = idx[v0:v1, u0:u1].astype(np.int64)
    Pr = np.array(pal["rgb"], np.int64)
    void = cr.void_mask(O, Pr)
    assert cr.palette_classes("857DB48E", pal).tolist() == [127] * 15 + [255]
    assert int(void.sum()) == int((O == 15).sum()) == 506
    es = cr.edge_stats(O, Pr, void)
    for k in ("horizontal", "vertical"):
        assert es[k]["smoothed"] > 0 and es[k]["crisp_colour_step"] > 0 and es[k]["crisp_void_border"] > 0


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for n, f in tests:
        try:
            f()
            print("PASS", n)
        except Exception as e:  # noqa: BLE001
            failed += 1
            print("FAIL", n, type(e).__name__, e)
    print(f"{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
