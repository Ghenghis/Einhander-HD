"""Brute-force: is the R5 multi-source BFS fill invariant to the per-pixel neighbour order (x-1,x+1,y-1,y+1 vs
x+1,x-1,y-1,y+1 and other permutations), and NOT invariant to the seed order? Small random images."""
import itertools
import random
from collections import deque


def fill(vis, col, w, h, nbr, reverse_seeds=False):
    out = list(col)
    done = [v for v in vis]
    idx = range(w * h - 1, -1, -1) if reverse_seeds else range(w * h)
    q = deque(i for i in idx if vis[i])
    while q:
        p = q.popleft()
        x, y = p % w, p // w
        for dx, dy in nbr:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                k = ny * w + nx
                if not done[k]:
                    done[k] = True
                    out[k] = out[p]
                    q.append(k)
    return out


base = [(-1, 0), (1, 0), (0, -1), (0, 1)]
perms = list(itertools.permutations(base))
rnd = random.Random(1234)
diff_perm = diff_seed = 0
for trial in range(3000):
    w, h = rnd.randint(2, 9), rnd.randint(2, 9)
    vis = [rnd.random() < 0.25 for _ in range(w * h)]
    if not any(vis):
        continue
    col = [rnd.randint(0, 9) if v else -1 for v in vis]
    ref = fill(vis, col, w, h, base)
    for p in perms:
        if fill(vis, col, w, h, p) != ref:
            diff_perm += 1
            break
    if fill(vis, col, w, h, base, reverse_seeds=True) != ref:
        diff_seed += 1
print("trials with neighbour-order differences:", diff_perm, "| with seed-order differences:", diff_seed)
