# Number Cages

A daily logic puzzle at three levels. Every puzzle is solvable by deduction alone, and the in-game
hints explain each forced step. Play it at https://mavimatics.github.io/number-cages/.

Fill an n×n grid with 1..n so that no number repeats in a row or column (a **Latin square**), and
every outlined cage reaches its target with its operation: + and × for any cage, − and ÷ for
two-square cages (larger over smaller). A one-square cage gives its value.

| Level | Grid | Operations | Hardest deduction needed |
|---|---|---|---|
| Easy | 4×4 | +, − | cage arithmetic |
| Intermediate | 6×6 | +, −, ×, ÷ | cage arithmetic, sometimes pigeonhole |
| Guru | 8×8 | +, −, ×, ÷ | always pigeonhole or cage line |

There are 365 puzzles per level, one per day from 1 January 2026, cycling after a year.

## Guarantee: unique, and no guessing

The generator keeps a puzzle only if a solver restricted to six sound rules of inference fills the
whole grid:

1. **given**: a one-square cage holds its target
2. **single**: a square with one candidate left holds it
3. **hidden single**: a number with one possible square left in a row/column goes there
4. **cage**: drop candidates that appear in no valid filling of a cage (proof by cases)
5. **subset**: k squares in a row/column whose candidates are the same k numbers use them up (pigeonhole), k = 2, 3
6. **cage line**: if every valid filling of a cage puts v in row (column) r, no other square of r is v

Each rule only removes values that cannot appear in any solution. So if the solver finishes, every
solution must equal its grid, which is the grid the puzzle was built from: the solution is unique and
reachable without trial and error. Puzzles are graded by the hardest rule needed (rules are always
tried simplest first).

## Generation

1. Random Latin square by randomized backtracking.
2. Random connected cages grown from random squares (size distribution per level; few one-square cages).
3. Operations chosen per cage (÷ favored when it divides evenly); targets computed from the square.
4. Solve with rules up to the level's maximum; keep it if solved and hard enough, otherwise retry.

```bash
python3 generate.py                  # all levels, 365 each (~8 minutes, mostly Guru)
python3 generate.py --levels easy    # one level
```

Pure Python 3, no dependencies. Output: `out/<level>-<chunk>.json` (31 puzzles per file),
`out/manifest.json`, `out/stats.json`. A puzzle is
`{"id", "n", "cages": [[op, target, [cell indices]]], "solution", "hardest", "steps", "uses"}`,
with cells numbered row by row from 0.

## Hints

The game runs the same six rules in JavaScript (`cages_solver.js` in the website repository) on the
player's current grid: it reports wrong entries first, otherwise finds the next value that can be
forced and shows the deductions that lead to it, in three steps (where to look, why, the value).
It was checked against all 1,095 puzzles: it reaches the same solution and the same grade as the
Python solver, solving with hints alone always completes the grid, and hints from random partial
grids are always correct.
