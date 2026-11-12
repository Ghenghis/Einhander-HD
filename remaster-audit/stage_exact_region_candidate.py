"""Prepare a source-checked isolated region experiment; never auto-launch.

Policy: v7's 1151 keys, eleven corrected description outputs, five Results
regions, one Game Over region, experimental runtime, old validated rollback.
All visible-quality and whole-game acceptance remain separate from this gate.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import sys
import zlib

import numpy as np
from PIL import Image

import launch_ui_candidate as ui
import stage_world_candidate as world
import stage_description_candidate as font_stage
from build_three_asset_proof import verify_stock

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "remaster-audit"
PARENT = world.DEFAULT_EVIDENCE
FONT = AUDIT / "menu-restoration/description-continuity-candidate-v3"
RESULTS = AUDIT / "menu-restoration/results-current-art-candidate-v1"
EVIDENCE = world.ALLOWED / "hud-world-region-candidate-20261112-v9"
OLD_SHA = "0b746a7f10d8db0f5b2481b6c5859913e4b209468ef40cb45928a21f3027942e"
TITLE = "Einhander - HUD world and exact regions v9 experiment"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2)+"\n",encoding="utf-8")


def receipt(path):
    path = Path(path).resolve()
    return dict(path=str(path),sha256=ui.sha(path))


def references(node):
    found = []
    if isinstance(node,dict):
        if isinstance(node.get("path"),str) and isinstance(node.get("sha256"),str):
            path = Path(node["path"])
            if not path.is_absolute():
                path = ROOT / path
            require(ui.sha(path) == node["sha256"],"Referenced input changed: "+str(path))
            found.append(dict(path=str(path.resolve()),sha256=node["sha256"]))
        for value in node.values():
            found.extend(references(value))
    elif isinstance(node,list):
        for value in node:
            found.extend(references(value))
    return world.references_unique(found)


def verify_font_centers(directory=FONT):
    manifest,refs,checks = font_stage.verify_font(directory)
    directory = Path(directory)
    page = next(r for r in manifest["files"] if r["key"]==font_stage.BASE_KEY)
    native = font_stage.pixels(directory/"source-proof"/(font_stage.BASE_KEY+".png"))
    authored = font_stage.pixels(page["path"])
    selected = np.zeros((256,256),bool)
    for x0,y0,x1,y1 in font_stage.REGIONS:
        selected[y0:y1,x0:x1]=True
    verify_center_coverage(native,authored,selected)
    center_path = directory/"coverage-center-verification.json"
    center = load(center_path)
    require(center["checks"]=="PASS" and center["erased_ink_centers"]==center["filled_counter_centers"]==0 and
            center["checked_native_centers"]==int(selected.sum())==10240 and center["output_sha256"]==page["sha256"],
            "Font center verification receipt differs")
    refs.append(receipt(center_path))
    return manifest,world.references_unique(refs),checks


def verify_center_coverage(native,authored,selected):
    expected = native[:,:,3] != 0
    observed = authored[8::16,8::16,3] != 0
    require(np.array_equal(expected[selected],observed[selected]),"Font native ink/counter center coverage changed")


def verify_runtime(executable):
    override = ui.runtime_override(executable)
    build = load(override["build_receipt"])
    require(build["link_exit"]==0 and all(r["exit"]==0 for r in build["commands"]),"Experimental build/link failed")
    for field,minimum in (("native_tests",24),("gl_tests",22),("prior_capture_tests",17)):
        match = re.search(r"RESULT checks=(\d+) failures=(\d+)",build[field])
        require(match is not None and int(match[1])>=minimum and int(match[2])==0,"Runtime regression gate failed: "+field)
    alpha = json.loads(build["prior_alpha_tests"].strip())
    require(alpha["pass"] is True and alpha["current_class_mismatches"]==0,"Prior alpha regression failed")
    refs = references(build)+[receipt(override["build_receipt"])]
    for path,digest in build["source_hashes"].items():
        require(ui.sha(path)==digest,"Runtime/test source changed: "+path)
        refs.append(dict(path=path,sha256=digest))
    require(ui.sha(build["link_response"])==build["link_response_sha256"],"Runtime link response changed")
    refs.append(dict(path=build["link_response"],sha256=build["link_response_sha256"]))
    return override,world.references_unique(refs)


def verify_review(path,override):
    review=load(path)
    require(review["status"]=="PASS" and review["build_receipt"]==dict(path=override["build_receipt"],sha256=override["build_receipt_sha256"]),
            "Independent review does not pass this exact runtime build")
    require(review["executable"]==dict(path=override["executable"],sha256=override["sha256"]),"Independent review names another executable")
    require(review["independent_tests"] and all(r["exit"]==0 for r in review["independent_tests"]),"Independent focused tests did not pass")
    require(all(r["status"]=="resolved" for r in review.get("findings",[])),"Independent review has unresolved findings")
    refs=references(review)+[receipt(path)]
    build=load(override["build_receipt"])
    for source,digest in review["reviewed_source_hashes"].items():
        require(build["source_hashes"].get(source)==digest==ui.sha(source),"Independent review source differs from build")
        refs.append(dict(path=source,sha256=digest))
    return world.references_unique(refs)


def verify_regions(gameover):
    plans=[]
    all_refs=[]
    for kind,directory,expected_count in (("results",RESULTS,5),("gameover",Path(gameover),1)):
        path=directory/"manifest.json"
        manifest=load(path)
        require(manifest["contract"]==("verified-current-results-art-v1" if kind=="results" else "verified-gameover-region-art-v3"),
                "Only approved Results v1 / tonal Game Over v3 candidates are allowed")
        require(len(manifest["files"])==expected_count,"Unexpected region asset count")
        builder=directory/"build-source.py"
        if not builder.is_file():
            builder=Path(manifest["builder"]["path"])
        all_refs.extend(references(manifest)+[receipt(path),receipt(builder)])
        for row in manifest["files"]:
            key=row["key"]
            proof_rows=row.get("source_archives",row.get("source_proof",[]))
            proofs={Path(r["path"]).name:r for r in proof_rows}
            files={suffix:Path(proofs[key+suffix]["path"]) for suffix in (".words.bin",".clut.bin",".valid.bin",".source.json")}
            metadata=load(files[".source.json"])
            raw=files[".words.bin"].read_bytes();clut=files[".clut.bin"].read_bytes();valid=files[".valid.bin"].read_bytes()
            x,y=metadata["page_xy"];w,h=metadata["width_words"],metadata["height"]
            require(metadata["depth"]==2 and metadata["clut_words"]==0 and not clut and key==f"{zlib.crc32(raw):08X}-00000000",
                    "Exact direct-color source/CRC contract differs: "+key)
            require(len(raw)==w*h*2 and len(valid)==w*h and all(v==1 for v in valid) and
                    metadata["known_words"]==metadata["total_words"]==w*h,"Incomplete exact-region source: "+key)
            require(0<=x<x+w<=1024 and 0<=y<y+h<=512 and w==64 and h in (224,256),"Region bounds differ")
            words=np.frombuffer(raw,dtype="<u2").reshape(h,w)
            rgba=np.stack(((words&31)<<3,((words>>5)&31)<<3,((words>>10)&31)<<3,
                           np.where(words==0,0,np.where((words&0x8000)!=0,255,127))),axis=2).astype(np.uint8)
            authored=font_stage.pixels(row["path"])
            size=row.get("dimensions",row.get("size"))
            require(authored.shape==(h*16,w*16,4) and size==[w*16,h*16] and ui.sha(row["path"])==row["sha256"],
                    "Region PNG hash/dimensions differ: "+key)
            expected_alpha=np.repeat(np.repeat(rgba[:,:,3],16,0),16,1)
            require(np.array_equal(authored[:,:,3],expected_alpha),"Region native STP classes changed: "+key)
            if kind=="results":
                require(row["source_page_xy"]==[x,y] and row["native_used_region_half_open"]==[0,0,64,224] and
                        __import__("hashlib").sha256(rgba.tobytes()).hexdigest()==row["source_native_rgba_sha256"],"Results source geometry/decode differs")
                _,parent_raw,_=verify_stock(directory/"source-proof",row["full_page_key"])
                require(b"".join(parent_raw[i*512:i*512+128] for i in range(224))==raw,"Results region is not exact used parent-page words")
            else:
                require(row["source_region_words"]==[x,y,w,h],"Game Over region geometry differs")
                verify_stock(directory/"source-proof",key)
                require(np.array_equal(authored[8::16,8::16],rgba),"Game Over original RGB/STP pixel centers changed")
                snapshot=metadata.get("source_vram")
                if snapshot:
                    vram=Path(snapshot["path"]).read_bytes()
                    require(len(vram)==1024*512*2 and b"".join(vram[((y+i)*1024+x)*2:((y+i)*1024+x+w)*2] for i in range(h))==raw,
                            "Game Over proof differs from bracketed GPU-truth VRAM region")
            all_refs.extend(references(metadata))
            plans.append(dict(kind=kind,key=key,path=row["path"],sha256=row["sha256"],dimensions=size,
                              source_rect=[x,y,w,h],depth=2,clut_xy=[0,0],source_files={s:str(p) for s,p in files.items()},
                              source_manifest=str(path),visual_accepted=False))
    require(len({r["key"] for r in plans})==6,"Expected six distinct region keys")
    for i,a in enumerate(plans):
        x,y,w,h=a["source_rect"]
        for b in plans[i+1:]:
            bx,by,bw,bh=b["source_rect"]
            require(not(x<bx+bw and bx<x+w and y<by+bh and by<y+h),"Unexpected region overlap")
    return plans,world.references_unique(all_refs)


def expected_tsv(plans):
    return "EIN_EXACT_REGIONS_V1\n"+"".join(" ".join(map(str,[r["key"],*r["source_rect"],r["depth"],*r["clut_xy"]]))+"\n" for r in plans)


def rollback_plan(report):
    # No region/font/proof/build-new-runtime dependency is read on this path.
    evidence=Path(report["evidence"])
    require(ui.sha(Path(__file__))==report["region_launcher"]["sha256"],"Region wrapper changed")
    original_manifest=ui.BASE/"manifest.json"
    require(ui.sha(original_manifest)==report["base_manifest_sha256"],"Original base manifest changed")
    _,originals=ui.inventory(ui.BASE,"base");ui.verify_base(originals)
    require(len(originals)==964,"Original base key count differs")
    spec=report["launches"]["rollback"];exe=ui.owned(spec["arguments"][0],evidence)
    require(ui.sha(exe)==spec["executable_sha256"]==OLD_SHA,"Stock rollback must use old validated runtime")
    require(ui.sha(exe.parent/"settings.toml")==spec["settings_sha256"],"Rollback settings changed")
    require(Path(spec["environment_overrides"]["PSXRECOMP_HD_TEXTURE_ROOT"])==ui.BASE and
            Path(spec["writable_state"])==evidence/"state-rollback","Rollback pack/state isolation differs")
    rollback=copy.deepcopy(report);rollback["runtime_override"]=None
    rollback["overlay_manifests"]={"stock_base":dict(**receipt(original_manifest),asset_count=964,
        referenced_files=[dict(path=r["path"],sha256=r["sha256"]) for r in originals])}
    ui.verify_provenance(rollback)
    return rollback,dict(ok=True,old_validated_runtime_sha256=OLD_SHA,base_pngs_verified=964,
        experimental_file_dependencies=False,experimental_files_accessed=0,game_actions=0,rollback_tested_live=False)


def revalidate(report,full_decode=False,require_review=True):
    evidence=Path(report["evidence"])
    require(ui.sha(Path(__file__))==report["region_launcher"]["sha256"],"Region staging wrapper changed")
    require({"exact_region_assets","exact_region_composition","description_v3","runtime_region_build","parent_v7"}<=set(report["overlay_manifests"]),
            "Exact-region provenance is incomplete")
    if require_review:
        require("runtime_independent_review" in report["overlay_manifests"],"Independent runtime code review not locked")
        verify_review(report["overlay_manifests"]["runtime_independent_review"]["path"],report["runtime_override"])
    ui.verify_provenance(report)
    plans,_=verify_regions(report["exact_region_policy"]["gameover_directory"])
    font,_,_=verify_font_centers()
    require((evidence/"pack/ExactRegions.tsv").read_text()==expected_tsv(plans),"Combined region manifest changed")
    parent={r["name"][:-4]:r for r in load(PARENT/"candidate.json")["files"]}
    current={r["name"][:-4]:r for r in report["files"]};font_rows={r["key"]:r for r in font["files"]}
    require(len(current)==len(report["files"])==report["final_count"]==1157 and set(current)==set(parent)|{r["key"] for r in plans},"Unexpected final key set")
    require(all(current[k]["sha256"]==v["sha256"] for k,v in parent.items() if k not in font_rows),"An unapproved parent key changed")
    require(all(current[k]["sha256"]==v["sha256"] for k,v in font_rows.items()),"Font v3 overlay differs")
    require({p.name for p in (evidence/"pack/einhander-texture-replacements").glob("*.png")}=={r["name"] for r in report["files"]},"Pack PNG directory differs")
    require(len(list((evidence/"native-sources").iterdir()))==700,"Local world source sidecar count differs")
    for r in plans:
        for suffix,source in r["source_files"].items():
            require(ui.sha(evidence/"pack"/(r["key"]+suffix))==ui.sha(source),"Local exact-region sidecar changed")
    if full_decode:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(world.decode_row,row) for row in report["files"]]
            for n,future in enumerate(as_completed(futures),1):
                future.result()
                if n%200==0:print(json.dumps(dict(full_png_decodes=n,total=1157)),flush=True)
    else:
        for row in report["files"]:
            require(ui.sha(ui.owned(row["composed_path"],evidence))==row["sha256"],"Composed PNG changed")
    for mode,spec in report["launches"].items():
        exe=ui.owned(spec["arguments"][0],evidence)
        expected=report["runtime_override"]["sha256"] if mode=="candidate" else OLD_SHA
        require(ui.sha(exe)==spec["executable_sha256"]==expected and ui.sha(exe.parent/"settings.toml")==spec["settings_sha256"],"Runtime/settings changed")
        require(Path(spec["writable_state"])==evidence/("state" if mode=="candidate" else "state-rollback"),"Private state differs")
    return dict(ok=True,at_utc=datetime.now(timezone.utc).isoformat(),final_count=1157,region_additions=6,font_v3_overwrites=11,
        parent_v7_nonfont_choices_preserved=1140,world_additions_preserved=140,all_png_hashes_verified=1157,
        full_png_decodes=1157 if full_decode else 0,exact_crc_validity_stp_geometry_verified=True,font_native_centers_verified=10240,
        runtime_independent_review_locked="runtime_independent_review" in report["overlay_manifests"],
        live_visual_acceptance=False,game_actions=0,candidate_receipt=receipt(evidence/"candidate.json"))


def prepare(gameover,runtime,review=None):
    require(not EVIDENCE.exists(),"Preparation requires a fresh v9 evidence directory")
    parent=ui.load_report(PARENT);world.revalidate(parent,full_decode=False)
    font,font_refs,font_checks=verify_font_centers();plans,region_refs=verify_regions(gameover)
    override,runtime_refs=verify_runtime(runtime)
    review_refs=verify_review(review,override) if review else None
    old_exe=Path(parent["runtime"]["executable"]);require(ui.sha(old_exe)==OLD_SHA,"Old validated rollback source changed")
    seed_source,seed=world.closed_private_seed()
    report=copy.deepcopy(parent);report.pop("launches",None);report.pop("prepared_at_utc",None)
    report.update(evidence=str(EVIDENCE),window_title=TITLE,game_launched=False,production_installed=False,runtime_override=override)
    report["runtime"].update(executable=override["executable"],sha256=override["sha256"],selection="experimental exact-region build",
        build_receipt=override["build_receipt"],build_receipt_sha256=override["build_receipt_sha256"])
    font_rows={r["key"]:r for r in font["files"]}
    for row in report["files"]:
        row.pop("composed_path",None);row.pop("composition",None);key=row["name"][:-4]
        if key in font_rows:
            new=font_rows[key];row["font_override_parent"]=dict(path=row["path"],sha256=row["sha256"])
            row.update(path=new["path"],sha256=new["sha256"],dimensions=new["size"],bytes=Path(new["path"]).stat().st_size,origin="description continuity v3")
            row.setdefault("overlay_sources",[]).append(dict(origin=row["origin"],path=new["path"],sha256=new["sha256"]))
    require(not {r["key"] for r in plans}&{r["name"][:-4] for r in report["files"]},"Region additions overlap parent keys")
    for r in plans:
        report["files"].append(dict(name=r["key"]+".png",path=r["path"],sha256=r["sha256"],dimensions=r["dimensions"],
            bytes=Path(r["path"]).stat().st_size,origin="exact "+r["kind"]+" region",overlay_sources=[dict(origin=r["kind"],path=r["path"],sha256=r["sha256"])],
            live_visual_accepted=False))
    report["final_count"]=1157;report["overlay_input_count"]+=17
    report["source_counts"].update(description_v3=11,exact_results_regions=5,exact_gameover_region=1)
    report["overlay_manifests"].update(parent_v7=dict(**receipt(PARENT/"candidate.json"),asset_count=1151),
        description_v3=dict(**receipt(FONT/"manifest.json"),asset_count=11,referenced_files=font_refs),
        exact_region_assets=dict(**receipt(RESULTS/"manifest.json"),asset_count=6,referenced_files=region_refs),
        runtime_region_build=dict(**receipt(override["build_receipt"]),asset_count=0,referenced_files=runtime_refs))
    report["exact_region_policy"]=dict(parent=str(PARENT),font_directory=str(FONT),gameover_directory=str(Path(gameover).resolve()),
        copied_region_keys=[r["key"] for r in plans],fullpage_unused_outputs_installed=False,
        excluded_experiments=[dict(path=str(world.ALLOWED/"hud-world-font-candidate-20261112-v8"),reason="Font v2 introduced visible stroke gaps; superseded by v3"),
            dict(path=str(AUDIT/"menu-restoration/gameover-region-candidate-v1"),reason="ImageGen wordmark changed original geometry"),
            dict(path=str(AUDIT/"menu-restoration/gameover-region-candidate-v2"),reason="Binary contour promoted glow into filled white strokes; only include if superseded by corrected tonal candidate")],
        quality_status="unaccepted_isolated_experiment_requires_actual_live_replay")
    ui.TITLE=TITLE;ui.prepare(report)
    for r in plans:
        for suffix,source in r["source_files"].items():ui.copy_verified(source,EVIDENCE/"pack"/(r["key"]+suffix))
    (EVIDENCE/"pack/ExactRegions.tsv").write_text(expected_tsv(plans),encoding="utf-8")
    # Preserve local source evidence independently of the parent directories.
    shutil.copytree(PARENT/"native-sources",EVIDENCE/"native-sources")
    shutil.copytree(FONT/"source-proof",EVIDENCE/"font-native-sources")
    local_world=load(PARENT/"world-additions-manifest.json")
    local_world_refs=[]
    for asset in local_world["assets"]:
        for proof in asset["copied_native_files"]:
            target=EVIDENCE/"native-sources"/Path(proof["path"]).name
            require(ui.sha(target)==proof["sha256"],"Copied world proof changed")
            proof["source_path"]=proof["path"];proof["path"]=str(target)
            local_world_refs.append(dict(path=str(target),sha256=proof["sha256"]))
    world_manifest=EVIDENCE/"world-additions-manifest.json";write(world_manifest,local_world)
    report["overlay_manifests"]["world_composition"]=dict(**receipt(world_manifest),asset_count=140,referenced_files=local_world_refs)
    exact_local=[receipt(EVIDENCE/"pack"/(r["key"]+suffix)) for r in plans for suffix in r["source_files"]]
    exact_local.append(receipt(EVIDENCE/"pack/ExactRegions.tsv"))
    exact_local.extend(receipt(p) for p in sorted((EVIDENCE/"font-native-sources").iterdir()))
    ui.copy_verified(FONT/"coverage-center-verification.json",EVIDENCE/"font-coverage-center-verification.json")
    exact_local.append(receipt(EVIDENCE/"font-coverage-center-verification.json"))
    composition=EVIDENCE/"exact-region-composition.json"
    write(composition,dict(schema_version=1,regions=plans,font_checks=font_checks,policy=report["exact_region_policy"],
        candidate_runtime=override,stock_rollback_sha256=OLD_SHA,game_actions=0,live_accepted=False))
    report["overlay_manifests"]["exact_region_composition"]=dict(**receipt(composition),asset_count=6,referenced_files=exact_local)
    for mode in ("candidate","rollback"):
        spec=report["launches"][mode]
        if mode=="rollback":
            target=Path(spec["arguments"][0]);ui.copy_verified(old_exe,target);spec["executable_sha256"]=OLD_SHA
        target=Path(spec["writable_state"])/"card1.mcd";ui.copy_verified(seed_source,target)
        flag=" --rollback" if mode=="rollback" else ""
        (EVIDENCE/("launch-"+mode+".cmd")).write_text('@echo off\r\n"'+sys.executable+'" "'+str(Path(__file__).resolve())+'" --launch'+flag+'\r\n',encoding="utf-8")
    write(EVIDENCE/"private-card-seed.json",dict(seed,candidate_state=str(EVIDENCE/"state"),rollback_state=str(EVIDENCE/"state-rollback"),restart_load_verified=False))
    report["region_launcher"]=receipt(Path(__file__))
    if review:
        report["overlay_manifests"]["runtime_independent_review"]=dict(**receipt(review),asset_count=0,referenced_files=review_refs)
    write(EVIDENCE/"candidate.json",report)
    result=revalidate(report,full_decode=True,require_review=bool(review));_,rollback=rollback_plan(report)
    write(EVIDENCE/"rollback-isolation-check.json",rollback)
    write(EVIDENCE/"preparation-revalidation.json",result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gameover",type=Path)
    parser.add_argument("--runtime-executable",type=Path)
    parser.add_argument("--independent-review",type=Path)
    operation=parser.add_mutually_exclusive_group();operation.add_argument("--check",action="store_true");operation.add_argument("--launch",action="store_true")
    parser.add_argument("--rollback",action="store_true");args=parser.parse_args()
    require(not args.rollback or args.launch,"--rollback requires --launch")
    if args.check or args.launch:
        report=ui.load_report(EVIDENCE)
        if args.rollback:
            rollback,result=rollback_plan(report)
            if args.launch:result=ui.launch(rollback,True)
        else:
            result=revalidate(report,full_decode=args.check)
            if args.launch:result=ui.launch(report,False)
    else:
        require(args.gameover is not None and args.runtime_executable is not None,"Preparation needs explicit Game Over candidate and final runtime")
        result=prepare(args.gameover,args.runtime_executable,args.independent_review)
    print(json.dumps(result,indent=2));return 0


if __name__=="__main__":
    raise SystemExit(main())
