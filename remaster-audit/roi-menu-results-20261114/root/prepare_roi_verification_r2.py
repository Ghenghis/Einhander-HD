from pathlib import Path
n=Path(__file__).resolve().parent
s=(n/'verify_roi_composer.py').read_text()
s=s.replace('roi-composer-cpu-r1','roi-composer-cpu-r2').replace('roi-composer-synthetic-r1','roi-composer-synthetic-r2')
s=s.replace("manifest=fixture/'manifest.json';manifest.write_text('{}\\n')", "manifest=fixture/'manifest.json';manifest.write_text(json.dumps(dict(region='fixture uv [2,2]-[6,6] half-open',keys={key:dict(live=pin(parent))})))")
s=s.replace("b=np.full((16,16,4),237,dtype=np.uint8);b[:,:,3]=127", "b=a.copy();b[4:12,4:12,:3]=237")
s=s.replace("assert sha(parent)==pin(parent)['sha256']", "assert sha(parent)==json.loads(parentjson.read_text())['files'][0]['sha256']")
s=s.replace('unit_cases=5,negative_geometry_cases=15','unit_cases=7,negative_geometry_and_binding_cases=20')
(n/'verify_roi_composer_r2.py').write_text(s,encoding='utf-8',newline='\n')
print('Prepared fresh ROI r2 verification; earlier r1 evidence preserved.')
