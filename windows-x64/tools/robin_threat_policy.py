"""Experimental short-horizon avoidance of partial source-query clusters.

No object IDs or hitboxes are inferred. Tracers need two matched observations
and an approaching trajectory, so outgoing player fire is not treated as a
known hostile projectile. Returns only a vertical pad target for the bridge.
"""
import math

class ThreatPolicy:
    def __init__(self):
        self.previous=[];self.commit_until=-1;self.target=None;self.last={}

    def target_y(self,reply,hull,now,preferred=None):
        self.last=dict(fresh=False,coverage='partial source-query clusters',qualified=False)
        if not isinstance(reply,dict) or reply.get('ok') is not True or reply.get('enabled') is not True:
            return None
        frame,age=reply.get('frame'),reply.get('age_frames')
        if type(frame) is not int or type(age) is not int or not 0<=age<=12 or not 0<=now-frame<=18:
            self.previous=[];return None
        objects=reply.get('objects');viewport=reply.get('viewport')
        if not isinstance(objects,list) or len(objects)>64:return None
        if objects and viewport!=[320,224]:return None
        boxes=[]
        for item in objects:
            if not isinstance(item,dict):return None
            b=item.get('bounds');family=item.get('family');key=item.get('key')
            if (family not in ('fighter','uhu','tracer','greif','greif_arm','greif_mount') or not isinstance(key,str) or
                not isinstance(b,list) or len(b)!=4 or not all(type(v) is int for v in b) or
                not 0<=b[0]<b[2]<320 or not 0<=b[1]<b[3]<224):
                return None
            boxes.append((family,key.split('-')[0],b))  # Native CLUT fades do not change source ownership.
        hl,ht,hr,hb=hull;hx,hy=(hl+hr)/2,(ht+hb)/2
        current=[];predicted=[];used=set()
        for family,key,b in boxes:
            if family in ('greif','greif_arm','greif_mount'):continue  # Body parts are aim observations, not collision proof.
            cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2;match=None;distance=math.inf
            for i,(old_family,old_key,old_frame,px,py) in enumerate(self.previous):
                dt=frame-old_frame
                if i in used or family!=old_family or key!=old_key or not 0<dt<=30:continue
                d=(cx-px)**2+(cy-py)**2
                if d<distance and d<=(10*dt)**2:match=(i,dt,px,py);distance=d
            current.append((family,key,frame,cx,cy));vx=vy=0.
            if match:
                i,dt,px,py=match;used.add(i);vx,vy=(cx-px)/dt,(cy-py)/dt
            if family=='tracer':
                if not match or vx*(hx-cx)+vy*(hy-cy)<=0:continue
            dx,dy=vx*36,vy*36
            predicted.append([min(b[0],b[0]+dx),min(b[1],b[1]+dy),max(b[2],b[2]+dx),max(b[3],b[3]+dy)])
        self.previous=current
        self.last.update(fresh=True,frame=frame,clusters=len(boxes),predicted=len(predicted),dropped=reply.get('dropped',0))
        if now<self.commit_until:
            self.last.update(target_y=self.target,committed=True);return self.target
        margin=8
        hit=any(b[0]<hr+margin and b[2]>hl-margin and b[1]<hb+margin and b[3]>ht-margin for b in predicted)
        if not hit:self.target=None;return None
        intervals=sorted((max(0,b[1]-margin),min(224,b[3]+margin)) for b in predicted if b[0]<hr+40 and b[2]>hl-8)
        spans=[];top=0;need=hb-ht+2*margin
        for a,b in intervals+[(224,224)]:
            if a-top>=need:spans.append((top,a))
            top=max(top,b)
        if not spans:return None
        half=(hb-ht)/2+margin
        candidates=[min(max(hy,a+half),b-half) for a,b in spans]
        forward=[y for y in candidates if (preferred=='down' and y>hy) or (preferred=='up' and y<hy)]
        if forward:candidates=forward
        self.target=min(candidates,key=lambda y:abs(y-hy));self.commit_until=now+36
        self.last.update(target_y=self.target,committed=False);return self.target
