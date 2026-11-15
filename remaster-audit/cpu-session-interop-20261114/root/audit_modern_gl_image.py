"""Independent pixel oracle for the fixed private triangle; not gameplay fidelity acceptance."""
from pathlib import Path
import hashlib,json,math,sys
W,H=320,180
HEADER=b'P6\n320 180\n255\n'
VERTICES=[(-3,-2,8),(0,2,8),(3,-2,8)]
def expected_triangle():
    focal=(H/2)/math.tan(math.radians(60)/2)
    return [(W/2+x*focal/z,H/2-y*focal/z) for x,y,z in VERTICES]
def triangle_region(x,y,margin):
    pts=expected_triangle()
    for i,a in enumerate(pts):
        b=pts[(i+1)%3];cross=(b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0])
        if cross<margin*math.hypot(b[0]-a[0],b[1]-a[1]):return False
    return True
def audit_bytes(data):
    if not data.startswith(HEADER) or len(data)!=len(HEADER)+W*H*3:return dict(passed=False,errors=['exact owned PPM header/length'],scope='Fixed private320x180 triangle only')
    pixels=data[len(HEADER):];green=inside=inside_green=outside_green=corner_green=0
    for y in range(H):
        for x in range(W):
            pos=(y*W+x)*3;r,g,b=pixels[pos:pos+3];is_green=g>=35 and g>1.3*r and g>1.3*b
            green+=int(is_green)
            if triangle_region(x+.5,y+.5,3):inside+=1;inside_green+=int(is_green)
            if not triangle_region(x+.5,y+.5,-4):outside_green+=int(is_green)
            if (x<16 or x>=W-16) and (y<16 or y>=H-16):corner_green+=int(is_green)
    ratio=inside_green/max(1,inside);errors=[]
    if not 500<green<W*H/2:errors.append('bounded green geometry area')
    if ratio<.5:errors.append('expected projected triangle interior')
    if outside_green>max(100,green//4):errors.append('green outside projected geometry/halo')
    if corner_green>10:errors.append('green corner fallback/background')
    return dict(passed=not errors,errors=errors,sha256=hashlib.sha256(data).hexdigest(),green_pixels=green,inside_pixels=inside,inside_green=inside_green,inside_green_fraction=ratio,outside_green=outside_green,corner_green=corner_green,expected_triangle=expected_triangle(),scope='Fixed synthetic scene with identity camera,60degFOV,320x180; not a general game image quality or ray tracing proof')
def audit_file(path):return audit_bytes(Path(path).read_bytes())
if __name__=='__main__':
    rows=[dict(path=x,**audit_file(x)) for x in sys.argv[1:]]
    print(json.dumps(dict(passed=bool(rows) and all(x['passed'] for x in rows),images=rows),indent=2));raise SystemExit(0 if rows and all(x['passed'] for x in rows) else 1)
