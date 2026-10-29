# Team Work Guide (4 technical roles): Adaptive Step-Up Authentication for UPI

**How to use this file with an LLM**

1. Copy **Part A (Shared context)** and **your own Part B section** (B1, B2, B3 or B4) into your LLM chat.
2. Say: *"You are helping me build my part of this project. Follow the specs exactly. If something is unclear or conflicts with the shared context, ask me before guessing. Write Python 3.11+, with tests."*
3. Ask for one small piece at a time, and run its tests before moving on.
4. If you change any number or format, tell the team first. Other people's code depends on it.

All numbers in this file are **version 1 placeholders**. They are starting values the team can change through the config file, not facts about real UPI.

**What changed from the earlier guide:** every role now writes code, and together the four roles produce one tool: a simulator, a policy engine, an experiment pipeline, and a decision service with a web interface. Literature reading and paper writing are split across the four roles instead of sitting with one person.

---

# Part A: Shared context (everyone reads this)

## A1. What the project is

UPI is India's instant payment system. Every UPI payment already needs the user's PIN. Banks and payment apps may add extra checks on top when a payment looks risky (RBI allows this from April 2026).

This project builds and evaluates a **risk-scoring policy**:

1. Look at signals about a payment (new device, new payee, unusual amount, SIM changed, and so on).
2. Add up points to get a **risk score from 0 to 100**.
3. Map the score to an **action** (nothing extra, step-up check, hold, or block).
4. Measure two things: how much **fraud** the policy stops, and how much **friction** (annoyance) it adds for genuine users.

Everything runs on **synthetic (made-up) data** in a simulator, because real payment data is not available. The research result is a **trade-off curve**: fraud stopped (y-axis) against friction on genuine users (x-axis), comparing our policy with simpler rules.

**The deliverable is a tool with four parts:**

| Part | What it is | Owner |
|---|---|---|
| Simulator | Generates genuine payments and attacks | Person 1 |
| Policy engine | Scores a payment and picks the action | Person 2 |
| Experiment pipeline | Baselines, cost model, metrics, plots | Person 3 |
| Decision service and web app | An API and a browser interface around the engine, plus config, CI and packaging | Person 4 |

**What we are NOT claiming:** that this beats real bank systems, or that results match real UPI fraud rates. We claim only that an open, explainable, rule-based policy gives a good trade-off in a documented simulation, and that it is practical to run as a service.

## A2. Words you need

| Term | Meaning |
|---|---|
| Genuine payment | A normal payment by the real owner |
| Attack | A fraudulent payment. Five types below |
| Signal | One fact about a payment (for example "new payee") |
| Weight or points | How many risk points a signal adds when it is on. These are the same thing |
| Tier | The action chosen for a payment (0, W, 1, 2, 3) |
| Strictness shift `d` | One number that moves all three tier thresholds together |
| Friction | Cost to a genuine user of an extra step (separate from risk points) |
| Baseline | A simpler rule we compare against |
| FRI | A government risk label for the payee's mobile number (medium, high, very high) |

**The five attacks**

| Attack | What happens |
|---|---|
| `simswap` | Attacker gets the victim's number on a new SIM, so they receive the OTP |
| `screenshare` | Victim is coached to share their screen and pays a scammer themselves |
| `collect` | Victim approves a fraudulent "collect request" |
| `replay` | Attacker reuses a captured OTP or session |
| `stolen` | Thief has the unlocked phone and knows the PIN |

## A3. The payment record (the shared data format)

One row per payment, as a pandas DataFrame. Every module uses exactly these columns.

| Column | Type | Meaning |
|---|---|---|
| `kind` | str | `legit` or `attack` |
| `attack_type` | str or null | `simswap`, `screenshare`, `collect`, `replay`, `stolen` |
| `median` | int | the user's usual payment in rupees |
| `ratio` | float | amount divided by `median` |
| `amount` | int | rupees, `round(median * ratio)` |
| `new_device` | bool | device never seen for this user |
| `network` | str | `home`, `mobile`, `public` |
| `new_payee` | bool | payee never paid before |
| `velocity` | bool | more than 3 payments in 10 minutes |
| `sim_change` | bool | SIM change in last 72 hours, **as observed** |
| `remote` | bool | remote-access app detected, **as observed** |
| `far_location` | bool | far from the user's usual location |
| `fri` | int | payee-number risk label: 0 none, 1 medium, 2 high, 3 very high |
| `u` | float in [0,1) | one fixed random draw per payment, shared by all policies |

`u` matters: every policy sees the same payments and the same luck, so differences between policies are real and not random noise.

## A4. The tiers (actions)

| Code | Name | What the user sees |
|---|---|---|
| `0` | PIN only | Nothing extra. The PIN is always required |
| `W` | Warning | On-screen warning, then PIN. Used only by the FRI-style baseline |
| `1` | Step-up | PIN plus a biometric or OTP check |
| `2` | Hold | PIN, biometric, then a 30-minute hold with a confirmation prompt |
| `3` | Block | Payment stopped until the bank verifies by call-back |

## A5. Interfaces (do not change without telling the team)

```python
# common/config.py   (Person 4)
def load_config(path: str) -> Config:
    """Loads and validates a YAML config. Raises on unknown or missing keys."""

# sim/generate.py   (Person 1)
def generate(cfg: Config, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (legit_df, attacks_df), both in the A3 format."""

# policy/engine.py   (Person 2)
SIGNAL_GROUPS: dict[str, list[str]]   # group name -> list of weight keys (used by ablation)

def score(tx: dict, weights: dict) -> tuple[int, list[tuple[str, int]]]:
    """Returns (score 0..100, [(signal_name, points), ...]) so every decision is explainable."""

def make_engine(weights: dict, shift: int = 0) -> "Policy":
    """Returns a policy."""

# A Policy takes a DataFrame of payments and returns a Series of tier codes.
Policy = Callable[[pd.DataFrame], pd.Series]

# baselines/__init__.py   (Person 3)
def get_baselines(cfg: Config) -> dict[str, Policy]:
    """Keys: pin_only, always_strict, amount_rule, fri_only (and ml_baseline if built)."""

# eval/metrics.py   (Person 3)
def evaluate(policy, legit, attacks, assume) -> dict
def sweep(weights, legit, attacks, assume, shifts) -> list[dict]
def ablation(weights, shift, legit, attacks, assume) -> list[dict]
```

Policies must be **vectorised** (work on the whole DataFrame at once, not row by row). One evaluation of about 31,500 payments should take well under a second, because sweeps and optimisers call it thousands of times.

## A6. Repository layout

```
upi-stepup/
  pyproject.toml                 # numpy, pandas, matplotlib, pyyaml, pydantic, fastapi, uvicorn, pytest, ruff; optional: scikit-learn, cma
  Dockerfile
  .github/workflows/ci.yml
  configs/default.yaml           # all weights, probabilities, costs, sizes, seeds
  common/     config.py
  sim/        generate.py  attacks.py  rng.py
  policy/     engine.py  calibrate.py
  baselines/  __init__.py  simple.py  ml_baseline.py
  eval/       metrics.py  plots.py  run_experiment.py
  service/    api.py  schemas.py  decision_log.py  web/ (index.html, app.js, styles.css)
  tools/      run_reference.js  bench_latency.py
  tests/      test_scenarios.py  test_marginals.py  test_metrics.py  test_parity.py  test_api.py
  reference/  upi_reference_core.js     # read-only reference implementation
  docs/       assumptions.md  literature.csv  paper/
  results/    (generated)
```

`reference/upi_reference_core.js` is a working JavaScript version of the simulator, engine, baselines and evaluation. If this guide and that file disagree, tell the team and check both.

## A7. Team rules

- Anything that changes a result (weights, probabilities, costs, seeds, sizes) lives in `configs/*.yaml`. No constants hard-coded in code.
- Every figure and table comes from `python -m eval.run_experiment --config configs/<name>.yaml`. No hand-made plots.
- Work on your own branch, open a pull request, get one review. CI runs `pytest` and `ruff`.
- Use fixed seeds. Report results over several seeds (default 5), with mean and spread.
- Write every assumption in `docs/assumptions.md` as you make it.
- Never claim results show real UPI fraud rates.
- Everyone adds papers to `docs/literature.csv` (see each person's reading topic) and verifies that every reference exists before citing it.

## A8. Research claims to test (everyone's reading feeds this)

1. Public UPI work mostly detects fraud, and rarely evaluates which authentication level to apply and what it costs genuine users.
2. A fraud-stopped versus friction trade-off against several baselines is not openly published for UPI-style payments.
3. SIM swap, collect-request scams and screen-share scams are rarely simulated together against a tiered policy that respects the RBI two-factor floor.
4. The marginal value of individual signals under a fixed friction budget is not known.
5. No open, seeded simulator with labelled UPI-style attacks exists, to our knowledge.

These came from a limited search. Treat them as hypotheses until the team's reading confirms or corrects them.

## A9. Known weak spots (raise early)

1. Attack signatures are written by us, so the policy sees them by design. The "attackers look normal" variant and the learned attacker test this.
2. The chance that each action stops each attack is an estimate. Sensitivity analysis shows how much the conclusions depend on it.
3. At default settings about 17% of genuine payments get an extra check. The main cause is mobile data (5 points) plus new payee (15 points) reaching the 20-point threshold. This is a design decision to review.
4. A hold prompt shown on the same phone a thief is holding would just be tapped. How the prompt is delivered must be decided and documented.
5. All data is synthetic.

---

# Part B: Individual work

## B1. Person 1: Simulator and attackers

**Your job in one sentence:** generate genuine payments and five types of labelled attacks, reproducibly, in the A3 format, and later build an attacker that learns.

**You deliver:** `sim/generate.py`, `sim/attacks.py`, `sim/rng.py`, `test_marginals.py`, the generator section of `configs/default.yaml`.

### Genuine payments (v1)

| Item | Value |
|---|---|
| Size | 1000 users, 30 payments each (30,000 rows) |
| Usual amount `median` | lognormal, location ln(400), sigma 0.8, clipped to 60..5000, rounded |
| `ratio` | with probability 0.03: uniform between 10 and 150 (big one-off payments). Otherwise `exp(0.7 * N(0,1))` |
| `new_device` | probability 0.02 |
| `network` | home 0.45, mobile 0.50, public 0.05 |
| `new_payee` | 0.12 |
| `velocity` | 0.03 |
| `far_location` | 0.03 |
| True SIM change, true remote app | 0.005 each, then filtered by coverage (below) |
| `fri` | 0 with 0.975, 1 with 0.020, 2 with 0.004, 3 with 0.001 |

### Attacks (v1), 300 of each type

Each attack picks a random user's `median`, then `ratio = max(1.2, exp(mu + sigma * N(0,1)))`. All other entries are probabilities.

| Type | new_device | network home/mobile/public | new_payee | mu | sigma | velocity | true SIM change | true remote | far_location | fri 0/1/2/3 |
|---|---|---|---|---|---|---|---|---|---|---|
| `simswap` | 0.95 | .10/.60/.30 | 0.95 | ln 25 | 0.6 | 0.5 | 0.9 | 0.05 | 0.5 | .45/.20/.20/.15 |
| `screenshare` | 0.03 | .50/.50/0 | 0.90 | ln 15 | 0.7 | 0.2 | 0 | 0.9 | 0.05 | .45/.20/.20/.15 |
| `collect` | 0.02 | .50/.48/.02 | 0.90 | ln 6 | 0.6 | 0.1 | 0 | 0.05 | 0.05 | .45/.20/.20/.15 |
| `replay` | 0.80 | .20/.30/.50 | 0.70 | ln 8 | 0.6 | 0.7 | 0.1 | 0.05 | 0.4 | .90/.05/.03/.02 |
| `stolen` | 0 | .10/.70/.20 | 0.90 | ln 15 | 0.7 | 0.7 | 0 | 0 | 0.6 | .45/.20/.20/.15 |

### Observed versus true signals

Detection is imperfect. A true SIM change shows up in `sim_change` only with probability **0.90** (SIM-feed coverage). A true remote-access app shows up in `remote` only with probability **0.85**. Apply the same filter to genuine payments. Both numbers come from config.

### Must-have signals

Some signals an attacker cannot hide. In `attacks.py`, give each attack an `immutable` list: `simswap` needs SIM change, `screenshare` needs the remote app, `stolen` needs a new payee, `collect` needs a payee. The learned attacker needs this.

### Evasive variant (config flag `evasive: true`)

For each attack: with probability 0.60 set `ratio = 1 + U(0,1)` (looks like a normal amount); set `velocity = False`; change `public` network to `mobile`; with probability 0.85 set `fri = 0`.

### Random numbers

Use one `numpy.random.Generator` per seed. Draw `u` last for each payment, so adding a feature later does not change the existing draws. Stretch goal: port `mulberry32` plus the Box-Muller step from the reference JavaScript so the same seed gives identical payments. If the 32-bit integer maths is fiddly in Python, skip it and use the statistical parity test (B4).

### Learned attacker (second half of your work)

Build a search-based attacker that tries to get the most money past the policy.

- Each attack type exposes 6 to 10 adjustable parameters: amount parameters `mu` and `sigma`, velocity probability, location probability, network mix, `fri` evasion probability.
- Parameters in the `immutable` list stay fixed.
- Optimiser: random search first, then CMA-ES (the `cma` package or a hand-written evolution strategy).
- Reward: rupees that get through the policy at a given strictness, using the shared `evaluate()`.
- Limit the number of tries per attacker, since a real attacker cannot probe a bank without limit.
- Train on some seeds and test on others, and hold out one attack type.
- Output: worst-case fraud loss at each strictness, and how much the learned attacker beats the hand-written evasive variant. Give Person 3 a function that returns these numbers for plotting.

### Research reading (add rows to `docs/literature.csv`)

Synthetic transaction generators and fraud simulators (for example PaySim), mobile-money and UPI fraud datasets, adversarial or evasion attacks on fraud and risk-based authentication systems. At least three papers.

### Paper section you draft

Simulator design, attack models and the learned attacker.

### You are done when

- `generate(cfg, seed)` returns two DataFrames with exactly the A3 columns and types.
- Marginals match the tables (for example, genuine `new_payee` rate is 0.12 +/- 0.01 on 30,000 rows).
- Same seed gives the same data. Different seeds differ.
- Evasive mode and coverage filtering are tested.
- The learned attacker reports worst-case loss on held-out seeds and a held-out attack type.

---

## B2. Person 2: Policy engine and calibration

**Your job in one sentence:** build the explainable scoring function and tier mapping, then replace hand-picked weights with a principled search.

**You deliver:** `policy/engine.py`, `policy/calibrate.py`, `test_scenarios.py`, the policy section of `configs/default.yaml`.

### Scoring (v1)

Add the points of every signal that is on, then cap the total at 100.

| Signal | Condition | Points |
|---|---|---|
| New device | `new_device` | 30 |
| Network | `mobile` / `public` | 5 / 15 |
| New payee | `new_payee` | 15 |
| Amount versus usual | `2 <= ratio <= 10` / `ratio > 10` | 10 / 25 |
| Velocity | `velocity` | 10 |
| SIM change | `sim_change` | 25 |
| Remote-access app | `remote` | 30 |
| Far location | `far_location` | 15 |
| Payee-number risk | `fri` = 1 / 2 / 3 | 10 / 20 / 35 |

The points are the weights. There is only one set of numbers.

### Tiers

Base thresholds are 20, 50 and 70. The strictness shift `d` moves all three: the thresholds become `20+d`, `50+d`, `70+d`. In the demo, the "strictness" slider sets `d = -strictness`, so a stricter policy has lower thresholds.

| Score | Tier |
|---|---|
| below `20+d` | `0` |
| `20+d` up to `49+d` | `1` |
| `50+d` up to `69+d` | `2` |
| `70+d` and above | `3` |

Your engine never returns `W`. Only the FRI-style baseline does.

### Explainability and groups

- `score()` returns the per-signal breakdown, for example `[("new_payee", 15), ("amt_over_10x", 25)]`. Person 4 shows this in the decision log and the web app.
- `SIGNAL_GROUPS` maps each group to its weight keys, for the ablation study: `device`, `network`, `payee`, `amount`, `velocity`, `sim`, `remote`, `location`, `fri`.

### Golden tests (must pass exactly, at `d = 0`)

| Case | Inputs | Score | Tier |
|---|---|---|---|
| A chai | mobile network, ratio 0.72, nothing else | 5 | `0` |
| B rent | home, new payee, ratio 180 | 40 | `1` |
| C SIM swap | new device, new payee, SIM change, public network, ratio 180 (raw total 110, capped) | 100 | `3` |
| D screen-share | remote app, new payee, ratio 180, home | 70 | `3` |
| E stolen phone | new payee, velocity, far location, home, ratio 180 | 65 | `2` |

### Speed

`make_engine(...)` returns a vectorised policy. Scoring 31,500 payments should take under 0.2 s. Provide the single-payment `score()` separately for Person 4's service.

### Calibration

Replace hand-picked weights with a search that keeps the best trade-offs.

- **Variables:** the 13 weights (each 0 to 100) and the three thresholds.
- **Objectives:** maximise fraud value stopped; minimise friction per 1,000 genuine payments. Report the whole Pareto set, not one point.
- **Method:** random search first, then NSGA-II (a multi-objective evolutionary algorithm). The result stays a plain points table.
- **Protocol:** tune on seeds 1 to 5. Report on seeds 101 to 105, which are never tuned on. Also hold out one attack type from tuning and report on it.
- **Output:** `configs/calibrated.yaml` and the numbers for a figure comparing hand-picked against calibrated curves (Person 3 draws it).
- **Stretch: robust calibration.** Alternate with Person 1: tune weights against the best learned attacker, retrain the attacker against the new weights, and repeat for a few rounds.

### Research reading (add rows to `docs/literature.csv`)

Risk-based authentication, adaptive and step-up authentication, usability and friction cost, multi-objective optimisation for security policies. At least three papers.

### Paper section you draft

Policy design, scoring, calibration method.

### You are done when

- All five golden tests pass.
- Engine is vectorised and fast.
- Calibration runs and reports on held-out seeds and a held-out attack type.

---

## B3. Person 3: Experiment pipeline (baselines, cost model, evaluation)

**Your job in one sentence:** build the comparison rules, the cost model, and the whole evaluation pipeline that turns payments and policies into numbers and figures.

**You deliver:** `baselines/*`, the cost section of `configs/default.yaml`, `eval/metrics.py`, `eval/plots.py`, `eval/run_experiment.py`, `test_metrics.py`, `docs/assumptions.md`.

### Baselines

Each is a Policy (DataFrame in, Series of tier codes out). Expose them through `get_baselines(cfg)`.

| Name | Rule |
|---|---|
| `pin_only` | tier `0` for every payment |
| `always_strict` | tier `1` for every payment |
| `amount_rule` | tier `1` if `amount > 10000`, otherwise `0` |
| `fri_only` | `fri == 3` gives `3`; `fri` of 1 or 2 gives `W`; otherwise `0` |
| `ml_baseline` (optional) | Gradient-boosted trees or logistic regression on the same signals, trained on seeds 1 to 5. Turn its predicted attack probability into tiers `0/1/2/3` using thresholds, and sweep those thresholds so it draws its own trade-off curve instead of one arbitrary point |

### Cost model (v1)

Friction points per action, and the chance a genuine user abandons the payment because of it:

| Action | Friction points | Genuine user gives up |
|---|---|---|
| `0` PIN only | 0 | 0 |
| `W` warning | 0.5 | 0.01 |
| `1` step-up | 1 | 0.02 |
| `2` hold | 5 | 0.25 |
| `3` block | 10 | 0.60 |

Chance an action stops an attack:

| Action | simswap | screenshare | collect | replay | stolen |
|---|---|---|---|---|---|
| `0` | 0 | 0 | 0 | 0 | 0 |
| `W` | .05 | .15 | .15 | .02 | .02 |
| `1` step-up | .15 | .10 | .10 | .50 | .35 |
| `2` hold | .55 | .50 | .50 | .80 | .60 |
| `3` block | .90 | .85 | .85 | .95 | .85 |

Reasoning to record in `docs/assumptions.md`: a step-up check is weak against `simswap` (attacker receives the OTP) and `screenshare` (victim reads out the OTP). A hold helps because it gives the real owner time to notice. Also resolve the hold-delivery problem (A9, point 4): decide how the confirmation prompt reaches the owner and adjust the `stolen` column to match.

### Metrics

For one policy over genuine payments `L` and attacks `X`, report per 1,000 genuine payments:

| Metric | Definition |
|---|---|
| `friction` | sum of friction points of chosen tiers over `L`, divided by `len(L)`, times 1000 |
| `extra` | share of `L` with tier other than `0`, times 1000 |
| `abandoned` | payments in `L` where `u < abandon[tier]`, divided by `len(L)`, times 1000 |
| `holds`, `blocks` | share of `L` at tier `2` and `3`, times 1000 |

Over attacks:

| Metric | Definition |
|---|---|
| `prevented %` | total `amount` of attacks where `u < p_stop[tier][attack_type]`, divided by total attack amount, times 100 |
| `lost` | total attack amount minus the amount prevented |
| per-type stopped | share of attacks of each type (by count) that were stopped |

An attack is stopped when its own `u` is below the stop chance for the tier the policy chose. Use the same `u` for every policy.

### Functions

- `evaluate(policy, legit, attacks, assume)` returns all metrics above.
- `sweep(...)`: the engine at `d` from -30 to +60 in steps of 3. Each point gives (friction, prevented %).
- `ablation(...)`: for each group in `SIGNAL_GROUPS`, set its weights to 0 and re-evaluate at the chosen shift. Report the change in prevented % and in friction.
- Run everything over 5 seeds. Report mean and standard deviation.
- `run_experiment.py` runs the whole pipeline from one config: generate, evaluate every policy, sweep, ablation, sensitivity, plots, and a results table saved to `results/`.

### Sensitivity analysis

Rerun key results with the friction points and the stop chances multiplied by 0.5 and by 2. State whether the conclusions hold across these changes.

### Plots (all from scripts)

1. Trade-off curve: x = friction per 1,000 genuine payments, y = fraud value stopped (%). Engine as a line, baselines as single points.
2. The same for the evasive variant.
3. Ablation bar chart.
4. Sensitivity plot (cost assumptions at 0.5x, 1x, 2x).
5. Calibrated versus hand-picked curves (from Person 2).
6. Worst-case curve against the learned attacker (from Person 1).

### Research reading (add rows to `docs/literature.csv`)

Fraud-detection ML baselines for payments, cost-sensitive evaluation, class imbalance, how fraud systems report precision, recall and friction. At least three papers. For each close paper record: signals used, whether an action or friction cost is modelled, whether a trade-off curve is reported, which attacks are simulated, whether data and code are open.

### Paper section you draft

Experimental setup, baselines, cost model, results.

### You are done when

- The four baselines and the cost model load from config and have unit tests.
- `test_metrics.py` passes on a hand-computed tiny example (4 genuine, 4 attack payments, exact friction and prevented %).
- One command reproduces every figure and table.
- `docs/assumptions.md` explains every number and the sensitivity results.
- (Optional) the ML baseline traces a trade-off curve.

---

## B4. Person 4: Decision service, web app, and platform

**Your job in one sentence:** wrap the policy engine as a working decision service with a browser interface, and provide the shared platform (config, CI, packaging, parity checks) that keeps the team's code consistent. This role has the most independent code but depends least on the others' research results.

**You deliver:** `common/config.py`, `service/*`, `tools/*`, `Dockerfile`, `.github/workflows/ci.yml`, `test_parity.py`, `test_api.py`, `pyproject.toml`.

### 1. Config loader (everyone depends on this, so deliver it first)

- `load_config(path)` reads YAML and returns a typed, validated object (pydantic or dataclasses).
- Reject unknown keys and missing keys, with a clear error message naming the key.
- Provide `configs/default.yaml` with every number from this guide: generator probabilities, attack table, coverage values, weights, thresholds, friction and abandonment values, stop chances, sizes and seeds.
- Support override files and a dictionary of overrides, so Person 3 can run sensitivity versions.

### 2. Decision service (FastAPI)

The service loads a policy from config and exposes it.

| Endpoint | Does |
|---|---|
| `GET /health` | returns status and policy version |
| `GET /policy` | returns weights, thresholds and the strictness shift |
| `POST /score` | scores one payment (below) |
| `POST /score/batch` | scores a list of payments |
| `POST /compare` | returns the tier each baseline would choose for one payment |
| `POST /simulate` | runs a small simulation (limited sizes) and returns trade-off curve data as JSON |
| `POST /policy` | updates weights or shift in memory, after validation, and changes the policy version |

**`POST /score` input** (same fields as A3, without labels and `u`):

```json
{"amount": 45000, "median": 250, "network": "home", "new_device": false, "new_payee": true,
 "velocity": false, "sim_change": false, "remote": true, "far_location": false, "fri": 0}
```

`ratio` is computed by the service as `amount / median`.

**Output:**

```json
{"score": 70, "raw_total": 70, "tier": "3", "tier_name": "Block and call back",
 "breakdown": [{"signal": "new_payee", "points": 15}, {"signal": "amt_over_10x", "points": 25}, {"signal": "remote", "points": 30}],
 "thresholds": [20, 50, 70], "policy_version": "<hash of weights and thresholds>"}
```

Validate every input with pydantic. Reject negative amounts, unknown networks and values out of range. Return clear error messages.

### 3. Decision log

Every scored payment is appended as one JSON line to `service/decisions.jsonl`: timestamp, inputs, score, breakdown, tier, thresholds, policy version. This is the explainability and audit feature. Add a `GET /decisions?limit=50` endpoint to read recent entries.

### 4. Web app (`service/web/`)

A single-page browser interface that calls the API. Plain HTML and JavaScript is fine, or React if the team prefers.

- **Try a payment:** a form with preset cases (chai stall, rent deposit, SIM-swap fraud, screen-share scam, stolen phone), a score meter showing the tier bands, the per-signal breakdown, and a table of what each baseline would do (`/compare`).
- **Strictness control:** a slider that calls `POST /policy` and re-scores.
- **Run simulation:** a panel that calls `/simulate` and draws the fraud-stopped versus friction curve with the baselines as points.
- **Decision log view:** shows recent decisions.
- A working JavaScript version of the interface logic already exists in `reference/upi_reference_core.js` and the published simulator. You may reuse its design, but the web app must call your API instead of running logic in the browser.

### 5. Parity harness (`tools/run_reference.js`, `test_parity.py`)

- `tools/run_reference.js` loads `reference/upi_reference_core.js` with Node and prints, as JSON, the golden scores and the aggregate results for a given seed and config.
- `test_parity.py` runs it and compares with the Python results.

**Parity targets** from the reference: seed 7, 1000 users, 30 payments each, 300 attacks of each type, default config, shift 0:

| Policy | Fraud stopped | Friction per 1,000 genuine | Extra checks per 1,000 |
|---|---|---|---|
| PIN only | 0.0% | 0 | 0 |
| OTP on every payment | 20.2% | 1000 | 1000 |
| OTP above Rs 10,000 | 13.9% | 27 | 27 |
| FRI-style rule | 14.6% | 23 | 25 |
| Engine, shift 0 | 79.2% | 195 | 169 |

If the random streams differ, exact numbers will differ. Accept parity when averages over 10 seeds are within about 3 percentage points on fraud stopped and within about 10% on friction. Golden scores (5, 40, 100, 70, 65) must match exactly.

### 6. Platform

- **CI:** GitHub Actions workflow that installs the package, runs `ruff` and `pytest` on every pull request.
- **Packaging:** `pyproject.toml` with pinned dependency ranges; `pip install -e .` works from a clean checkout.
- **Docker:** a `Dockerfile` that runs the service with `uvicorn`, and serves the web app.
- **Latency benchmark (`tools/bench_latency.py`):** send many `/score` requests concurrently and report requests per second and p50, p95 and p99 latency. Aim for p95 under 50 ms for one payment on a laptop (this is a target to measure, not a promise). Also report the engine's own scoring time for 31,500 payments in batch.
- **Reproducibility:** a `make` or script entry that runs tests, runs the default experiment and starts the service.

### Research reading (add rows to `docs/literature.csv`)

Read the primary sources and cite them, not news summaries:

- The RBI Authentication Mechanisms for Digital Payment Transactions Directions, 2025 (the circular itself).
- The DoT Financial Fraud Risk Indicator announcement.
- NPCI circulars on UPI security.
- Papers or documentation on real-time risk engines, latency budgets and explainable decision logging.

At least three sources. These back up the deployment story in the paper.

### Paper section you draft

System design and deployment: where the engine would run in real life, latency, the decision log, regulatory framing (it only adds checks above the mandated two-factor floor).

### You are done when

- `load_config` rejects bad configs with clear errors and every module uses it.
- All API endpoints work, have tests in `test_api.py`, and validate input.
- The web app runs end to end against the service.
- Golden and parity tests pass in CI.
- `docker build` and `docker run` start the service from a clean checkout.
- The latency report exists.

---

# Part C: Who depends on whom

| You need | From | Format |
|---|---|---|
| Config loader and `default.yaml` | Person 4 | `load_config(path)` returning a typed object |
| Payments and attacks | Person 1 | Two DataFrames in the A3 format |
| A scoring policy and signal groups | Person 2 | `make_engine`, `score`, `SIGNAL_GROUPS` |
| Baselines, cost values, metrics | Person 3 | `get_baselines`, `evaluate`, `sweep`, `ablation` |
| Learned-attacker results | Person 1 | Worst-case loss per strictness, as a function Person 3 can call |
| Calibrated weights | Person 2 | `configs/calibrated.yaml` |
| A running service for demos | Person 4 | Docker image and web app |

If your piece changes a format others depend on, tell the team before you merge.

# Part D: Paper

The paper is written by all four, each drafting the section named in their role:

| Section | Drafted by |
|---|---|
| Simulator design, attack models, learned attacker | Person 1 |
| Policy design, scoring, calibration | Person 2 |
| Experimental setup, baselines, cost model, results | Person 3 |
| System design, deployment, regulatory framing | Person 4 |
| Introduction, related work, limitations | Shared: each person writes the part that matches their reading topic; limitations come from `docs/assumptions.md` |

Target an IEEE-indexed Indian conference first, then extend for a journal such as the Journal of Banking and Financial Technology.
