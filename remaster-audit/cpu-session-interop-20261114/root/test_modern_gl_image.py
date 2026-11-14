"""CPU-only positive/negative controls for the independent future image oracle."""
from audit_modern_gl_image import HEADER,W,H,triangle_region,audit_bytes
def make(kind):
    out=bytearray()
    for y in range(H):
        for x in range(W):
            inside=triangle_region(x+.5,y+.5,0)
            if kind=='triangle':rgb=(5,220,5) if inside else (0,0,0)
            elif kind=='green':rgb=(0,220,0)
            elif kind=='magenta':rgb=(255,0,255)
            elif kind=='black':rgb=(0,0,0)
            elif kind=='shifted':rgb=(5,220,5) if triangle_region(x-80+.5,y+.5,0) else (0,0,0)
            elif kind=='corner':rgb=(0,220,0) if inside or (x<16 and y<16) else (0,0,0)
            else:raise ValueError(kind)
            out.extend(rgb)
    return HEADER+out
if __name__=='__main__':
    import datetime,json
    cases=[]
    for kind in ['triangle','green','magenta','black','shifted','corner']:
        result=audit_bytes(make(kind));expected=kind=='triangle';assert result['passed']==expected,(kind,result)
        cases.append(dict(kind=kind,expected=expected,**result))
    for kind,data in [('truncated',HEADER+b'\0'),('header',b'P6\n1 1\n255\n'+b'\0'*3)]:
        result=audit_bytes(data);assert not result['passed'];cases.append(dict(kind=kind,expected=False,**result))
    print(json.dumps(dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,cpu_cases=len(cases),cases=cases,gpu_executed=False,real_gpu_images_audited=False),indent=2))
