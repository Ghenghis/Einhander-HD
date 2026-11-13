"""Experimental pad-only stage schedule from robin-analysis/ROBIN-DEATHS.md.

Checkpoint A is inferred within about 200 guest frames. Later Greif sweeps are
unqualified hypotheses. A fresh source-matched hull drives each finite pulse;
this module neither reads/writes RAM nor sends commands. No threat API is assumed.
"""
VERSION='stage-schedule-experiment-2'
NEW_LIFE_GAP=150
TUMBLE_FRAMES=62
CPA=1733
CP1=3882
GREIF=5130

class StagePolicy:
    def __init__(self):
        self.start=None;self.last_frame=None;self.checkpoint=0
        self.life=0;self.deaths=[];self.closed=False;self.greif_anchor=None;self.last={}
        self.native_lives=None;self.pending_loss=False;self.missing_age=0

    def absent(self,now):
        # Camera pans and clipping can hide the hull without killing it.
        # Absence alone must never advance a checkpoint or count a death.
        self.missing_age=0 if self.last_frame is None else max(0,now-self.last_frame)

    def note_lives(self,lives):
        if type(lives) is not int or not 0<=lives<=255:raise ValueError('Native lives counter unavailable')
        lost=self.native_lives is not None and lives<self.native_lives
        self.native_lives=lives
        if not lost or self.start is None:return
        hit=self.last_frame-TUMBLE_FRAMES
        stage=self.checkpoint+hit-self.start
        self.deaths.append(dict(hit_frame=hit,stage=stage,life=self.life,
            next_checkpoint=CP1 if stage>=CP1 else CPA if stage>=CPA else 0,
            basis='Observed native lives decrement; hit frame estimated from last hull'))
        self.pending_loss=True

    def observe(self,frame):
        if self.last_frame is not None and frame<self.last_frame:raise ValueError('Guest clock reversed')
        if self.start is None:
            self.start=frame;self.life=1
        elif self.pending_loss:
            self.checkpoint=self.deaths[-1]['next_checkpoint']
            self.start=frame;self.life+=1;self.pending_loss=False;self.greif_anchor=None
        self.last_frame=frame

    def target(self,stage,g):
        # (vertical target, tolerance, permitted direction, label). The home
        # band spans one six-frame pulse, keeping the hull below the top clip.
        if g>=400:
            if g<650:return 14+(g-400)*186/250,10,'down','Greif volley 1'
            if g<680:return 200,4,'bottom','Greif gap'
            if g<900:return 200-(g-680)*186/220,10,'up','Greif volley 2'
            leg,phase=divmod(g-900,250);down=leg%2==0
            y=14+min(phase,200)*186/200 if down else 200-min(phase,200)*186/200
            return y,10,'down' if down else 'up','Greif later hypothesis'
        for a,b,bottom,speed,label in [(1650,1950,170,1.,'fighter wave 3'),
                (2300,2750,170,1.,'fighter wave 4'),(4100,4880,120,.9,'neon sweep')]:
            if a<=stage<b:
                leg=(bottom-14)/speed;cycles=int((b-a)//(2*leg))
                if not cycles:leg=(b-a)/2;cycles=1;speed=(bottom-14)/leg
                t=stage-a
                if t>=cycles*2*leg:break
                t%=2*leg
                return (14+speed*t,10,'down',label) if t<leg else (bottom-speed*(t-leg),10,'up',label)
        return 28,12,None,'upper home'

    def moves(self,state,x,y):
        frame,age=state.get('frame'),state.get('age_frames')
        if type(frame) is not int or frame<0 or type(age) is not int or not 0<=age<=12:
            raise ValueError('Fresh guest clock unavailable')
        self.observe(frame);now=frame+age;stage=self.checkpoint+now-self.start
        # The bridge has already validated this completed-frame source clock.
        clock=state.get('greif_draw',{})
        if clock.get('valid') is True and stage>=GREIF-600:
            self.greif_anchor=clock['first_frame']
        g=stage-GREIF if self.greif_anchor is None else now-self.greif_anchor
        target,tolerance,direction,label=self.target(stage,g);moves=[]
        if x>32:moves.append('left')
        elif x<16:moves.append('right')
        if y>target+tolerance and direction not in ('down','bottom'):moves.append('up')
        elif y<target-tolerance and direction not in ('up','top'):moves.append('down')
        self.last=dict(version=VERSION,now=now,stage=stage,greif=g,life=self.life,
            checkpoint=self.checkpoint,target_y=target,direction=direction,label=label,
            moves=list(moves),qualified=False,deaths=self.deaths[-5:])
        return moves

_SESSION=None
def session():
    global _SESSION
    if _SESSION is None:_SESSION=StagePolicy()
    return _SESSION
