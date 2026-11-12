"""Observed-screen gates for finite, isolated native UI acceptance journeys.

Native thumbnails identify states; composed/hires captures judge final visuals.
This never considers a filename, elapsed delay, or successful pad command a pass.
"""
from pathlib import Path
import json
import time

import numpy as np
from PIL import Image

from ui_candidate_probe import request, pulse, capture
from launch_ui_candidate import command


class DisplayTransition(RuntimeError):
    """The game has temporarily disabled its display during a scene change."""


def title_scores(a):
    cyan = ((a[:,:,0]<70)&(a[:,:,1]>40)&(a[:,:,2]>60)&
            (a[:,:,2]>a[:,:,0]+30))[80:150,20:300].sum()
    white = ((a.min(2)>160)&((a.max(2)-a.min(2))<45))[165:195,105:215].sum()
    return int(cyan), int(white)


class Journey:
    def __init__(self, report):
        self.report = report
        self.root = Path(report["evidence"])
        self.gate = self.root / "journey-state-thumbnail.png"
        self.log = self.root / "journey-observations.jsonl"

    def note(self, kind, **fields):
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(kind=kind, monotonic=time.monotonic(), **fields))+"\n")

    def thumbnail(self):
        reply = command(self.report, json.dumps(dict(cmd="screenshot", path=self.gate.as_posix())))
        if reply.get("ok") is not True:
            if reply.get("error") == "display disabled":
                self.note("display_transition")
                raise DisplayTransition("Display disabled; no scene observed")
            raise RuntimeError("screenshot: " + str(reply))
        if not self.gate.is_file():
            raise RuntimeError("Native state thumbnail missing")
        with Image.open(self.gate) as im:
            pixels = np.asarray(im.convert("RGB").resize((320, 240))).astype(np.int16)
        return pixels

    def title(self, seconds=30):
        """Require the blue/cyan title logo AND the white menu item below it."""
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            try:
                a = self.thumbnail()
            except DisplayTransition:
                time.sleep(.2)
                continue
            cyan, white = title_scores(a)
            if cyan > 400 and white > 130:
                self.note("title_observed", cyan=int(cyan), white=int(white))
                return
            time.sleep(.2)
        self.note("gate_failed", expected="title")
        raise RuntimeError("Title not observed; inputs stopped")

    def like(self, reference, rects, seconds=20, tolerance=18):
        """Compare native regions with a visually verified native reference.

        Composed/hires downscaling changes contours and interlace sampling;
        those files are visual evidence, not native gate references.
        """
        with Image.open(reference) as im:
            im = im.convert("RGB")
            if im.width > 640 or im.height > 512:
                raise ValueError("Scene gates require a native screenshot reference")
            ref = np.asarray(im.resize((320, 240))).astype(np.int16)
        deadline = time.monotonic()+seconds
        consecutive = 0
        distances = None
        while time.monotonic() < deadline:
            try:
                a = self.thumbnail()
            except DisplayTransition:
                consecutive = 0
                time.sleep(.2)
                continue
            distances = [float(np.abs(a[y0:y1,x0:x1]-ref[y0:y1,x0:x1]).mean())
                         for x0,y0,x1,y1 in rects]
            consecutive = consecutive+1 if max(distances) < tolerance else 0
            if consecutive >= 3:
                self.note("reference_observed", reference=str(reference), distances=distances,
                          rects=rects, tolerance=tolerance)
                return
            time.sleep(.2)
        self.note("gate_failed", reference=str(reference), distances=distances)
        raise RuntimeError("Expected native scene not observed; inputs stopped")

    def select_rows(self, target, rows, x0=35, x1=165):
        """Locate the brighter cyan selection before moving a menu cursor."""
        for attempt in range(len(rows)+1):
            a = self.thumbnail()
            brightness = []
            for y0,y1 in rows:
                r = a[y0:y1,x0:x1]
                m = (r[:,:,1]>55)&(r[:,:,1]>r[:,:,0]*1.4)&(r[:,:,2]>r[:,:,0]*1.2)
                brightness.append(float(np.percentile(r[:,:,1][m],85)) if m.any() else 0.)
            order = np.argsort(brightness)
            current = int(order[-1])
            if brightness[current] < 80 or brightness[current] < brightness[int(order[-2])]+8:
                self.note("selection_uncertain", brightness=brightness)
                raise RuntimeError("Menu highlight ambiguous; inputs stopped")
            self.note("selection_observed", current=current, target=target, brightness=brightness)
            if current == target:
                return
            pulse(self.report, "down", .15)
            time.sleep(.45)
        raise RuntimeError("Menu cursor did not reach requested item")

    def shot(self, label):
        result = capture(self.report, label, hires=False)
        self.note("visual_review_required", capture=result)
        return result

    def tap(self, button, wait=.4):
        pulse(self.report, button, .15)
        time.sleep(wait)


FILE_ROWS = [(63,74),(80,91),(97,108),(114,125),(131,142),(165,176)]
CONFIG_ROWS = [(63,74),(80,91),(97,108),(114,125),(165,176)]
