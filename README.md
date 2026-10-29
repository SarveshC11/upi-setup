# upi-stepup: adaptive step-up authentication for UPI

A transparent rule-based risk score (0 to 100) maps each UPI payment's signals to an action tier
(PIN only, step-up, hold, block). It is evaluated in a synthetic simulator on a
fraud-stopped versus friction trade-off against baselines.

Full role descriptions: `docs/team_work_guide.md`. Assumptions behind every number: `docs/assumptions.md`.

## Who owns what

| Person | Lane | Folders |
|---|---|---|
| 1 | Simulator and attacker | `sim/`, `tests/test_marginals.py` |
| 2 | Scoring engine and calibration | `policy/` |
| 3 | Experiment pipeline | `baselines/`, `eval/`, `configs/`, `docs/assumptions.md`, `docs/literature.csv` |
| 4 | Service and demo | `service/`, `reference/` (the JS simulator, for parity checks) |

Shared contract: the payment table columns listed in `docs/team_work_guide.md` (section A3). Do not
change a column name without telling everyone.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q                                              # all green before you start
python -m eval.run_experiment --out results/quick --quick   # about 7 s
python -m eval.run_experiment --out results/default         # about 35 s, full run
```

Outputs land in `results/<name>/` (CSV tables plus `plots/*.png`). `results/` is git-ignored except
`results/final/`, where we commit the numbers that go into the paper.

## Git workflow

1. `git switch main && git pull`
2. `git switch -c p3/short-description` (prefix with your person number)
3. Work, then `pytest -q && ruff check .`
4. `git add <files> && git commit -m "eval: add ablation plot"`
5. `git push -u origin p3/short-description`, open a Pull Request into `main`
6. One teammate reviews, then squash-merge. Never push straight to `main`.

Keep commits small. Do not commit large files, `.venv`, or anything in `results/` except `results/final/`.
