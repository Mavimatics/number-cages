"""Generate a year of Number Cages puzzles at three levels, each solvable by deduction alone.

    python3 generate.py [--count 365] [--levels easy,intermediate,guru] [--out out]

A puzzle is an n x n Latin square (each row and column holds 1..n once) cut into "cages": groups
of adjacent squares with a target and an operation (+, -, x, /). One-square cages give their value.

Generation:
  1. Fill a random Latin square by randomized backtracking.
  2. Cut it into random connected cages and give each an operation and the target it produces.
  3. Run the logical solver below. It may only use sound deductions (no guessing), so if it fills
     the whole grid, every value was forced: the solution is unique and reachable by logic.
     Otherwise, or if the puzzle is too easy or too hard for its level, throw it away and retry.

The solver's deductions, from simplest to hardest (the level of a puzzle is the hardest one it needs):
  1 given          a one-square cage shows its value
  2 single         a square has only one possible value left
  3 hidden single  a number has only one possible square left in a row or column
  4 cage           remove values that appear in no valid way of filling a cage
  5 subset         k squares in a row/column share exactly k possible values (k = 2, 3), so
                   those values can be removed from the rest of the row/column
  6 cage line      every valid way of filling a cage puts number d in the same row (or column),
                   so d can be removed from that row's squares outside the cage
"""
import argparse
import json
import random
import time
from collections import Counter
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHUNK = 31
TECHNIQUES = ["", "given", "single", "hidden single", "cage", "subset", "cage line"]

LEVELS = {
    # n: grid size; sizes: cage-size weights; ops2/opsN: operations for two-square and larger cages;
    # max_given: most one-square cages; hardest: allowed range of the hardest deduction needed.
    "easy": dict(n=4, sizes={1: 1, 2: 6, 3: 3}, ops2="+-", opsN="+", max_given=2, hardest=(2, 4)),
    "intermediate": dict(n=6, sizes={1: 1, 2: 9, 3: 6, 4: 2}, ops2="+-*/", opsN="+*", max_given=2,
                         hardest=(4, 5)),
    "guru": dict(n=8, sizes={1: 1, 2: 12, 3: 10, 4: 5, 5: 1}, ops2="+-*/", opsN="+*", max_given=1,
                 hardest=(5, 6)),
}


# ---------------- generation ----------------
def random_latin(n, rng):
    """Random Latin square by filling cells in order with randomized backtracking."""
    grid = [0] * (n * n)
    rows = [set() for _ in range(n)]
    cols = [set() for _ in range(n)]

    def fill(i):
        if i == n * n:
            return True
        r, c = divmod(i, n)
        for v in rng.sample(range(1, n + 1), n):
            if v not in rows[r] and v not in cols[c]:
                grid[i] = v
                rows[r].add(v)
                cols[c].add(v)
                if fill(i + 1):
                    return True
                rows[r].discard(v)
                cols[c].discard(v)
        return False

    fill(0)
    return grid


def random_cages(n, sizes, rng):
    """Cut the grid into connected cages, growing each from a random free square."""
    free = set(range(n * n))
    cages = []
    weights = list(sizes.items())
    while free:
        start = rng.choice(sorted(free))
        target = rng.choices([s for s, _ in weights], [w for _, w in weights])[0]
        cage = [start]
        free.discard(start)
        while len(cage) < target:
            options = sorted({nb for cell in cage for nb in neighbors(cell, n) if nb in free})
            if not options:
                break
            nxt = rng.choice(options)
            cage.append(nxt)
            free.discard(nxt)
        cages.append(sorted(cage))
    return cages


def neighbors(cell, n):
    r, c = divmod(cell, n)
    if r > 0:
        yield cell - n
    if r < n - 1:
        yield cell + n
    if c > 0:
        yield cell - 1
    if c < n - 1:
        yield cell + 1


def assign_op(cells, grid, cfg, rng):
    vals = [grid[i] for i in cells]
    if len(cells) == 1:
        return "", vals[0]
    if len(cells) == 2:
        a, b = max(vals), min(vals)
        ops = [o for o in cfg["ops2"] if o != "/" or a % b == 0]
        # Division is the most informative clue when it's possible, so offer it more often.
        op = rng.choice(ops + (["/"] if "/" in ops else []))
        return op, {"+": a + b, "-": a - b, "*": a * b, "/": a // b}[op]
    op = rng.choice(cfg["opsN"])
    if op == "+":
        return op, sum(vals)
    prod = 1
    for v in vals:
        prod *= v
    return op, prod


# ---------------- solver ----------------
class Solver:
    def __init__(self, n, cages):
        self.n = n
        self.cages = cages  # [(op, target, [cells])]
        self.cand = [set(range(1, n + 1)) for _ in range(n * n)]
        self.placed = [False] * (n * n)
        self.units = [[r * n + c for c in range(n)] for r in range(n)] + \
                     [[r * n + c for r in range(n)] for c in range(n)]
        self.peers = [set() for _ in range(n * n)]
        for unit in self.units:
            for i in unit:
                self.peers[i].update(j for j in unit if j != i)
        self.used = Counter()

    def place(self, i, v):
        self.cand[i] = {v}
        self.placed[i] = True
        for j in self.peers[i]:
            self.cand[j].discard(v)

    def combos(self, cage):
        """All ways to fill a cage consistent with candidates, row/column rules and the target."""
        op, target, cells = cage
        out = []
        n = self.n
        vals = [0] * len(cells)

        def ok_partial(k):
            if op == "+":
                return sum(vals[:k]) <= target
            if op == "*":
                p = 1
                for v in vals[:k]:
                    p *= v
                return target % p == 0
            return True

        def rec(k):
            if k == len(cells):
                if op == "" or (op == "+" and sum(vals) == target) or (op == "-" and abs(vals[0] - vals[1]) == target):
                    out.append(tuple(vals))
                elif op == "*":
                    p = 1
                    for v in vals:
                        p *= v
                    if p == target:
                        out.append(tuple(vals))
                elif op == "/" and max(vals) == target * min(vals):
                    out.append(tuple(vals))
                return
            i = cells[k]
            for v in self.cand[i]:
                if any(vals[j] == v and (cells[j] // n == i // n or cells[j] % n == i % n) for j in range(k)):
                    continue
                vals[k] = v
                if ok_partial(k + 1):
                    rec(k + 1)
            vals[k] = 0

        rec(0)
        return out

    # Each technique returns True if it changed something (one application at a time).
    def t_given(self):
        for op, target, cells in self.cages:
            if op == "" and not self.placed[cells[0]]:
                self.place(cells[0], target)
                return True
        return False

    def t_single(self):
        for i in range(self.n * self.n):
            if not self.placed[i] and len(self.cand[i]) == 1:
                self.place(i, next(iter(self.cand[i])))
                return True
        return False

    def t_hidden(self):
        for unit in self.units:
            for v in range(1, self.n + 1):
                spots = [i for i in unit if v in self.cand[i]]
                if len(spots) == 1 and not self.placed[spots[0]]:
                    self.place(spots[0], v)
                    return True
        return False

    def t_cage(self):
        for cage in self.cages:
            cells = cage[2]
            if all(self.placed[i] for i in cells):
                continue
            combos = self.combos(cage)
            changed = False
            for k, i in enumerate(cells):
                allowed = {c[k] for c in combos}
                if self.cand[i] - allowed:
                    self.cand[i] &= allowed
                    changed = True
            if changed:
                return True
        return False

    def t_subset(self):
        for size in (2, 3):
            for unit in self.units:
                open_cells = [i for i in unit if not self.placed[i] and 2 <= len(self.cand[i]) <= size]
                for group in combinations(open_cells, size):
                    union = set().union(*(self.cand[i] for i in group))
                    if len(union) != size:
                        continue
                    changed = False
                    for j in unit:
                        if j not in group and self.cand[j] & union:
                            self.cand[j] -= union
                            changed = True
                    if changed:
                        return True
        return False

    def t_cage_line(self):
        n = self.n
        for cage in self.cages:
            cells = cage[2]
            if len(cells) < 2 or all(self.placed[i] for i in cells):
                continue
            combos = self.combos(cage)
            if not combos:
                continue
            for axis in (0, 1):  # 0: rows, 1: columns
                lines = {(i // n if axis == 0 else i % n) for i in cells}
                for line in lines:
                    for v in range(1, n + 1):
                        # Does every way of filling the cage put v somewhere on this line?
                        if all(any(combo[k] == v and (cells[k] // n if axis == 0 else cells[k] % n) == line
                                   for k in range(len(cells))) for combo in combos):
                            unit = self.units[line if axis == 0 else n + line]
                            outside = [j for j in unit if j not in cells and v in self.cand[j]]
                            if outside:
                                for j in outside:
                                    self.cand[j].discard(v)
                                return True
        return False

    def solve(self, max_level=6):
        techniques = [None, self.t_given, self.t_single, self.t_hidden, self.t_cage, self.t_subset, self.t_cage_line]
        steps = 0
        while not all(self.placed):
            if any(not c for c in self.cand):
                return False  # contradiction: cannot happen for a puzzle made from a real solution
            for level in range(1, max_level + 1):
                if techniques[level]():
                    self.used[level] += 1
                    steps += 1
                    break
            else:
                return False  # stuck: this puzzle would need guessing
        self.steps = steps
        return True


# ---------------- puzzles ----------------
def make_puzzle(cfg, rng):
    n = cfg["n"]
    while True:
        grid = random_latin(n, rng)
        cells = random_cages(n, cfg["sizes"], rng)
        if sum(len(c) == 1 for c in cells) > cfg["max_given"]:
            continue
        cages = [(*assign_op(c, grid, cfg, rng), c) for c in cells]
        s = Solver(n, cages)
        lo, hi = cfg["hardest"]
        if not s.solve(max_level=hi):
            continue
        hardest = max(s.used)
        if hardest < lo:
            continue
        assert [next(iter(c)) for c in s.cand] == grid  # the forced solution is the one we built
        return {
            "n": n,
            "cages": [[op, target, c] for op, target, c in cages],
            "solution": "".join(map(str, grid)),
            "hardest": TECHNIQUES[hardest],
            "steps": s.steps,
            "uses": {TECHNIQUES[k]: v for k, v in sorted(s.used.items())},
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=365)
    ap.add_argument("--levels", default="easy,intermediate,guru")
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    stats_path = out / "stats.json"
    stats = json.loads(stats_path.read_text()) if stats_path.exists() else {}
    for i, name in enumerate(args.levels.split(",")):
        cfg = LEVELS[name]
        rng = random.Random(args.seed + 101 * (list(LEVELS).index(name) + 1))
        start = time.time()
        puzzles = []
        for k in range(1, args.count + 1):
            p = make_puzzle(cfg, rng)
            p["id"] = k
            puzzles.append(p)
            if k % 50 == 0:
                print(f"  {name}: {k}/{args.count} [{time.time() - start:.0f}s]", flush=True)
        for k in range(0, len(puzzles), CHUNK):
            (out / f"{name}-{k // CHUNK:02d}.json").write_text(json.dumps(puzzles[k:k + CHUNK], separators=(",", ":")))
        hardest = Counter(p["hardest"] for p in puzzles)
        stats[name] = {
            "puzzles": len(puzzles), "size": cfg["n"],
            "cages_per_puzzle": round(sum(len(p["cages"]) for p in puzzles) / len(puzzles), 1),
            "steps_per_puzzle": round(sum(p["steps"] for p in puzzles) / len(puzzles), 1),
            "hardest": dict(hardest), "seconds": round(time.time() - start),
        }
        print(name, stats[name], flush=True)
    stats["latin_squares"] = {"4": "576", "5": "161,280", "6": "812,851,200", "7": "61,479,419,904,000",
                              "8": "108,776,032,459,082,956,800"}
    manifest = {"chunk": CHUNK, "epoch": "2026-01-01",
                "levels": {k: {"count": v["puzzles"], "size": v["size"]}
                           for k, v in stats.items() if isinstance(v, dict) and "puzzles" in v}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    stats_path.write_text(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
