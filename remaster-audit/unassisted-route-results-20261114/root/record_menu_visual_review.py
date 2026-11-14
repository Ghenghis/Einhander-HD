from pathlib import Path
import datetime,hashlib,json
n=Path(__file__).resolve().parent
folder=Path('C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui/conflicts/20261114T182225Z')
source=folder/'result.json';sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
assert sha(source)=='b1949aad14be8746677579902adbe9ba1becb8d5bbc450a9caf97492c640cfcc'
d=json.loads(source.read_bytes());rows=[]
for row in d['rows']:
    for kind in ('sheet','overview'):
        p=(folder/row[kind]['path']).resolve()
        assert p.is_relative_to(folder.resolve()) and sha(p)==row[kind]['sha256']
    prompt=row['key'].startswith(('BDAE4156-','DD0B6963-'))
    rows.append(dict(key=row['key'],scale='runtime-2048',detail=row['sheet'],overview=row['overview'],
        actually_viewed=True,decision='provisional w5 prompt candidate' if prompt else 'reject both; new proposal required',
        chosen_folder='w5-cleanup/prompt-sheet-BDAE4156-DD0B6963-w5-v1' if prompt else None,
        reason='Cleaner prompt/digit contours than beaded/broken w4; residual glow and stepping remain.' if prompt else
            'w4 has regular glyph speckles; w5 has warped strokes and gray staircase patches. Artifact mechanism still needs source analysis.',
        native_127_255_display_semantics_not_qualified=True,lower_resolution_reviewed=False,
        installed=False,live_accepted=False,final_4k_accepted=False))
assert len(rows)==6
out=n/'menu-visual-review-r1';out.mkdir(exist_ok=False)
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reviewer='codex-einhander',
    source_sha256=sha(source),actual_images_viewed=12,image_hashes_verified=12,rows=rows,
    private_candidate_choices=3,rejected_spec_text_choices=3,gpu_run=False,game_run=False,installed=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
