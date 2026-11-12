# upi-stepup

Adaptive step-up authentication for UPI-style payments: a simulator, an explainable
rule-based policy engine, an evaluation pipeline, and a decision service with a web app.
All data is synthetic, and all numbers are version 1 placeholders, not real UPI fraud rates.

## Quick start

The project is self-contained and uses synthetic data. Anyone with Python 3.11+
can run the tests, API, and browser demo locally.

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"

python -m pytest
python -m uvicorn service.api:app --host 127.0.0.1 --port 8000
# open http://127.0.0.1:8000/ui/ (API docs at /docs)
```

On Windows, the complete local workflow is:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_all.ps1
```

Use `-SkipServe` to run linting, tests, and the experiment without starting
the server.

Docker:

```bash
docker build -t upi-stepup .
docker run --rm -p 8000:8000 upi-stepup
```

The committed production frontend is served by FastAPI, so Node.js is not
required for the normal demo.

## Configuration

```python
from common.config import load_config
cfg = load_config("configs/default.yaml")
cfg = load_config("configs/default.yaml", override_files=["configs/my_override.yaml"])
cfg = load_config("configs/default.yaml", overrides={"costs.friction.2": 10})
cfg2 = cfg.with_overrides({"generator.evasive": True})
```

An override file can contain only the keys it changes and can name its base:

```yaml
extends: default.yaml
costs:
  friction: {"2": 10, "3": 20}
```

Unknown or missing keys raise `ConfigError` with the full key path, for example
`unknown key 'policy.weigths'` or `missing key 'policy.weights.remote'`.

## Decision service API

| Endpoint | Does |
|---|---|
| `GET /health` | status, policy version, config fingerprint |
| `GET /policy` | weights, base and effective thresholds, shift |
| `POST /policy` | partial update `{"weights": {...}, "shift": -10, "thresholds": [..]}` or `{"reset": true}` |
| `POST /score` | score one payment, with breakdown |
| `POST /score/batch` | `{"payments": [...]}` (max 1000) |
| `POST /compare` | engine result plus each baseline's tier |
| `POST /simulate` | small seeded simulation, returns the trade-off curve and baseline points |
| `GET /decisions?limit=50` | recent decision-log entries, newest first |
| `/ui/` | the web app |

Example:

```bash
curl -s localhost:8000/score -H "Content-Type: application/json" -d '{"amount":45000,"median":250,"network":"home","new_device":false,"new_payee":true,"velocity":false,"sim_change":false,"remote":true,"far_location":false,"fri":0}'
# {"score":70,"raw_total":70,"tier":"3","tier_name":"Block and call back",
#  "breakdown":[{"signal":"new_payee","points":15},{"signal":"amt_over_10x","points":25},
#               {"signal":"remote","points":30}],"thresholds":[20,50,70],"policy_version":"..."}
```

Environment variables: `UPI_CONFIG` (config path) and `UPI_DECISION_LOG` (log path).

## Web app

The browser UI in `frontend/` is React + TypeScript (Vite) with shadcn/ui components,
shadcn charts (Recharts) and Motion animations. Its production build lives in `service/web/`
and is committed, so running the service needs no Node. Only people changing the UI need it:

```bash
cd frontend
npm ci
npm run dev      # live-reloading UI at http://localhost:5173/ui/ (start uvicorn on :8000 first)
npm run build    # rebuild service/web, then commit frontend/ and service/web/ together
```

Tabs: **Simulation** (trade-off curve, strictness sweep, policy comparison),
**Score a payment** (a realistic phone-style checkout where you enter an amount
and see the required authentication), and **Decision log**. Use **Details** in
the payment screen to test individual risk signals such as a new device, SIM
change, remote-access app, or unusual location.

## Tools

* `python -m tools.parity` prints the golden scores, the Python aggregates over 10 seeds, a
  comparison with the reference table, and the JS reference results when
  `reference/upi_reference_core.js` is present.
* `node tools/run_reference.js --seeds 1,2,3` runs the JavaScript reference on its own.
* `python -m tools.bench_latency` measures `/score` latency and throughput plus batch engine
  time, and writes `results/latency.md` and `results/latency.json`.

## Team contributions

The branches have been integrated into `main`. The implementation is split
into four connected parts:

| Part | Owner | Status in this repo |
|---|---|---|
| Simulator and attack scenarios (`sim/*`) | Person 1 | integrated |
| Risk policy and calibration (`policy/*`, calibrated configs) | Person 2 | integrated |
| Evaluation and comparison (`baselines/*`, `eval/*`, metrics and parity tests) | Person 3 | integrated |
| API, web app, configuration, CI, Docker, and packaging (`service/*`, `frontend/*`, `common/*`, `tools/*`) | Person 4 | integrated |

All tests pass on the integrated branch. The repository is a research/demo
prototype: numbers are synthetic placeholders and are not production fraud
rates or a real banking service.
