"""Bracket final-menu source admissions against screenshot frames; no game I/O."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "remaster-audit"
V5 = AUDIT / "dev-center-evidence/hud-4k-candidate-20261112-v5"


def ref(path, data=None):
    data = path.read_bytes() if data is None else data
    return dict(path=str(path),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))


def main():
    rows = []
    snapshots = []
    for capture_path in sorted(V5.glob("native-*/capture.jsonl")):
        raw = capture_path.read_bytes()
        snapshots.append(ref(capture_path,raw))
        for line, text in enumerate(raw.splitlines(),1):
            try:
                row = json.loads(text)
            except json.JSONDecodeError:
                continue
            row["line"] = line
            row["stream"] = str(capture_path)
            rows.append(row)
    rows.sort(key=lambda row:(row.get("frame",0),row["stream"],row["line"]))
    candidate = json.loads((V5 / "candidate.json").read_text())
    files = {r["name"][:-4]:r for r in candidate["files"]}
    font_keys = set(json.loads((AUDIT / "menu-restoration/font-strip-candidate-v3/manifest.json").read_text())["expected_keys"])
    selected = font_keys | {k for k in files if k.startswith(("B77B98B9-","8E1A509D-","323B5FB0-"))}
    draws = [r for r in rows if r.get("event") == "replacement_gl_draw_submitted" and r.get("key") in selected]
    checked = {}
    for row in draws:
        expected = files[row["key"]]
        if row["replacement_size"] != expected["dimensions"]:
            raise ValueError("Actual replacement dimensions differ from selected candidate: "+row["key"])
        checked[row["key"]] = dict(path=str(V5 / "pack/einhander-texture-replacements" / expected["name"]),sha256=expected["sha256"])
    for info in checked.values():
        if ref(Path(info["path"]))["sha256"] != info["sha256"]:
            raise ValueError("Actual private replacement PNG changed")
    def summarize(row):
        return {k:row[k] for k in ("stream","line","event","key","frame","native_words","source_kind","depth","semi","page_xy","clut_xy","uv_bounds","xy","replacement_size") if k in row}
    def is_footer(row):
        uv = row.get("uv_bounds",[])
        return (row["key"].startswith("8E1A509D-") and len(uv)==4 and
                80<=uv[0]<=uv[2]<199 and 236<=uv[1]<=uv[3]<248)
    screenshots = []
    for path in sorted((V5 / "captures").glob("e2e-*.json")):
        shot = json.loads(path.read_text())
        label = shot.get("label",path.stem)
        image_path = path.with_suffix(".png")
        if ref(image_path)["sha256"] != shot["sha256"]:
            raise ValueError("Screenshot changed")
        lo,hi = shot["frame_before"],shot["frame_after"]
        exact = [r for r in draws if lo <= r["frame"] <= hi]
        before = [r for r in draws if lo-60 <= r["frame"] < lo]
        after = [r for r in draws if hi < r["frame"] <= hi+60]
        footer_before = [r for r in draws if r["frame"] <= hi and is_footer(r)]
        screenshots.append(dict(label=label,screenshot=ref(image_path),receipt=ref(path),
            frames=[lo,hi],exact_bracket_draws=[summarize(r) for r in exact],
            sampled_prior60_draws=[summarize(r) for r in before],sampled_following60_draws=[summarize(r) for r in after],
            exact_font39_keys=sorted({r["key"] for r in exact if r["key"] in font_keys}),
            exact_banner_keys=sorted({r["key"] for r in exact if r["key"].startswith("B77B98B9-")}),
            exact_footer_draws=[summarize(r) for r in exact if is_footer(r)],
            footer_cold_loading_gate=(bool(footer_before) if "title" in label else None),
            scope="Sampled GL submissions in or near a sequential present screenshot bracket; draw presence alone does not prove visible coverage or visual quality."))
    first = {}
    for row in draws:
        first.setdefault(row["key"],dict(line=row["line"],frame=row["frame"],replacement_size=row["replacement_size"]))
    report = dict(schema_version=1,generated_at_utc=datetime.now(timezone.utc).isoformat(),
        source_stream_snapshots=snapshots,candidate=ref(V5 / "candidate.json"),
        actual_replacement_pngs=checked,first_observed_gl_submissions=first,screenshots=screenshots,
        first_actual_footer_submission=next((summarize(r) for r in draws if is_footer(r)),None),
        cold_loading_rule="For each required component, capture only after at least one matching replacement_gl_draw_submitted for the final candidate PNG. Prefer an exact screenshot-frame bracket submission; otherwise require nearby sampled prior submissions plus actual visual review. A native source query, declared pack entry or warmed unrelated asset is insufficient.",
        rejected_for_footer_visual_acceptance=["e2e-title-copyright-and-loaded-pilot: frames1983..1987 precede recorder1989 and footer first GL draw2012"],
        limitations=["Recorder is sampled; missing exact event does not prove a missing draw", "GL-submission events carry not_visibility_proof; combined visual review is required", "The initial PILOT title remains valid native-load state evidence independently of footer readiness", "No full menu/art/gameplay quality completion claim is made"])
    out = V5 / "final-menu-draw-brackets.json"
    out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(**ref(out),screenshots=len(screenshots),observed_pngs=len(checked))))


if __name__ == "__main__":
    main()
