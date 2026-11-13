"""Read-only Continue recognition; finite confirmation belongs to the caller."""
from __future__ import annotations
from collections import deque
from pathlib import Path
import hashlib
import numpy as np
from PIL import Image
from native_ui_facade_route import native_pixels, crop, dice

REFERENCE=Path(__file__).resolve().parent/'dev-center-evidence/stage1-completion-20261112/robin-wave2-hd-v1/hd-on_rewind-off/observations/terminal-0148.png'
REFERENCE_SHA='6453244cba6a5c57871654713323c3cd037d2ef25bb683dbe568771c9f1a39ed'

def load_reference():
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest()!=REFERENCE_SHA:
        raise ValueError('Continue reference changed')
    with Image.open(REFERENCE) as image:return native_pixels(image)

def classify(pixels,reference):
    if pixels.shape!=(240,320,3):raise ValueError('Continue gate requires native 320x240 RGB')
    def mask(a):return (a.max(2)>100)&(a.min(2)>35)
    # Exclude the changing countdown. Require the distinct question AND Yes/No
    # instructions, and a black field where the player's hull would be.
    rects=[(88,45,232,68),(88,192,222,214)]
    scores=[dice(mask(crop(pixels,r)),mask(crop(reference,r))) for r in rects]
    black=float((crop(pixels,(0,70,90,190)).max(2)<8).mean())
    return dict(continue_prompt=min(scores)>=.985 and black>=.99,
                header_score=scores[0],choices_score=scores[1],black_field=black)

class ContinueGate:
    def __init__(self,reference=None):
        self.reference=load_reference() if reference is None else reference
        self.streak=deque(maxlen=3);self.issued=False;self.ready=False

    def observe(self,pixels,frame,*,hull_valid=False):
        result=classify(pixels,self.reference)
        increasing=isinstance(frame,int) and (not self.streak or frame>self.streak[-1])
        if self.issued or hull_valid or not result['continue_prompt'] or not increasing:
            self.streak.clear();self.ready=False
        else:
            self.streak.append(frame);self.ready=len(self.streak)==3
        return dict(result,consecutive=len(self.streak),ready=self.ready,issued=self.issued)

    def mark_issued(self):
        if self.issued or not self.ready:raise RuntimeError('Unverified or duplicate Continue confirmation refused')
        self.issued=True;self.ready=False

    def resumed(self,*,lives,hull_valid):
        if not self.issued or not hull_valid or not isinstance(lives,int) or lives<=0:
            raise RuntimeError('Continue resume requires positive lives and fresh hull geometry')
        self.issued=False;self.streak.clear();self.ready=False
