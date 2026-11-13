"""Screen-space enemy targeting from bounded native draw-source geometry.

Targets are tracked clusters, not native object IDs or collision hitboxes.
Decisions depend on current geometry rather than elapsed-time movement patterns.
"""
from robin_threat_policy import ThreatPolicy

class CombatPolicy:
    def __init__(self):
        self.previous=[];self.lock=None;self.next_id=1;self.threat=ThreatPolicy();self.last={}

    def decide(self,state,reply):
        now=state['frame']+state['age_frames'];l,t,r,b=state['bounds'];x,y=(l+r)/2,(t+b)/2
        result=dict(mode='observe',fire=False,pod_fire=False,aligned=False,moves=[],movement_frames=6,target=None,
            source_frame=None,coverage='partial source-matched enemy geometry',qualified=False)
        frame=reply.get('frame') if isinstance(reply,dict) else None
        if (not isinstance(reply,dict) or reply.get('ok') is not True or reply.get('enabled') is not True or
            type(frame) is not int or not 0<=now-frame<=18 or type(reply.get('age_frames')) is not int or
            not 0<=reply['age_frames']<=12):
            self.previous=[];self.lock=None;result['mode']='await fresh enemy observation';self.last=result;return result
        objects=reply.get('objects');viewport=reply.get('viewport')
        if not isinstance(objects,list) or len(objects)>64 or (objects and viewport!=[320,224]):
            self.last=result;return result
        candidates=[];greif=[]
        for item in objects:
            if not isinstance(item,dict):self.last=result;return result
            bounds=item.get('bounds');family=item.get('family');key=item.get('key')
            if (family not in ('fighter','uhu','greif','tracer') or not isinstance(key,str) or
                not isinstance(bounds,list) or len(bounds)!=4 or not all(type(v) is int for v in bounds) or
                not 0<=bounds[0]<bounds[2]<320 or not 0<=bounds[1]<bounds[3]<224):
                self.last=result;return result
            if family=='tracer':continue
            if family=='greif':greif.append(bounds);continue
            candidates.append(dict(family=family,key=family,bounds=list(bounds)))
        if greif:
            candidates.append(dict(family='greif',key='greif',bounds=[min(q[0] for q in greif),min(q[1] for q in greif),
                max(q[2] for q in greif),max(q[3] for q in greif)]))
        used=set();tracks=[]
        for item in candidates:
            q=item['bounds'];cx,cy=(q[0]+q[2])/2,(q[1]+q[3])/2;best=None;distance=1e20
            for i,old in enumerate(self.previous):
                dt=frame-old['frame'];d=(cx-old['x'])**2+(cy-old['y'])**2
                if i not in used and item['family']==old['family'] and item['key']==old['key'] and 0<dt<=30 and d<distance and d<=(dt*10)**2:
                    best=(i,old,dt);distance=d
            item.update(x=cx,y=cy,frame=frame,vx=0.,vy=0.)
            if best:
                i,old,dt=best;used.add(i);item.update(track=old['track'],vx=(cx-old['x'])/dt,vy=(cy-old['y'])/dt)
            else:item['track']=self.next_id;self.next_id+=1
            tracks.append(item)
        self.previous=tracks
        forward=[q for q in tracks if q['bounds'][2]>r+12 and q['x']>x+24]
        # Keep a target unless another is substantially easier to engage.
        def cost(q):
            value=max(0,q['bounds'][0]-r)*.25+abs(q['y']-y)
            return value*.55 if q['track']==self.lock else value
        chosen=min(forward,key=cost) if forward else None
        target_y=80.;tolerance=10.;result.update(source_frame=frame,visible_enemy_clusters=len(tracks),fire=True)
        if chosen:
            self.lock=chosen['track'];flight=min(24,max(0,(chosen['x']-x)/12))
            target_y=min(196,max(24,chosen['y']+chosen['vy']*flight))
            tolerance=min(8,max(3,(chosen['bounds'][3]-chosen['bounds'][1])/4))
            result.update(mode='aim',target=dict(track=chosen['track'],family=chosen['family'],bounds=chosen['bounds'],
                lead_y=target_y,velocity=[chosen['vx'],chosen['vy']],aim_error=target_y-y))
            # Approximate firing corridor, explicitly not a hitbox assertion.
            result['aligned']=abs(y-target_y)<=max(tolerance,6)
            result['pod_fire']=result['aligned']
            if result['aligned']:result['mode']='engage'
        else:self.lock=None;result['mode']='search'
        preferred='down' if target_y>y else 'up'
        escape=self.threat.target_y(reply,[l,t,r,b],now,preferred=preferred)
        if escape is not None:
            target_y=escape;tolerance=6;result.update(mode='evade',escape_y=escape)
        result['threat']=dict(self.threat.last)
        errors=[];moves=[]
        if x>52:moves.append('left');errors.append(x-52)
        elif x<32:moves.append('right');errors.append(32-x)
        if y>target_y+tolerance:moves.append('up');errors.append(y-target_y)
        elif y<target_y-tolerance:moves.append('down');errors.append(target_y-y)
        speed=3.75 if state.get('source_set')==2 else 3.1
        result.update(moves=moves,movement_frames=max(1,min(6,int(min(errors)/speed))) if errors else 1)
        self.last=result;return result
