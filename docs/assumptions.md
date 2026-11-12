# Assumptions register (owner: Person 3)

Every number in the simulator that is a guess, with where it lives and how we justify it. The paper
reports sensitivity to the costs in section 1, so those are the ones that need honest wording.

All values below are the v1 placeholders in `configs/default.yaml`. Replace each "Source" cell with a
real reference or write "judgement" plainly.

## 1. Cost model (`costs:`)

| Quantity | Value | Source | Sensitivity run? |
|---|---|---|---|
| Friction points: warning / step-up / hold / block | 0.5 / 1 / 5 / 10 | judgement: relative annoyance, step-up = 1 | yes, x0.5 and x2 |
| Giving-up chance: warning / step-up / hold / block | 1% / 2% / 25% / 60% | judgement; compare checkout-abandonment studies | yes, scaled with friction |
| Chance an action stops an attack, per tier and attack type | table in config | judgement: e.g. a hold gives the victim 30 min to notice | yes, x0.5 and x2 |

## 2. Data generation (`generator:`, `attacks:`)

| Quantity | Value | Source |
|---|---|---|
| Payment amounts: per-user median, spread | in config | judgement; no public UPI per-user data |
| New-payee rate for genuine payments | about 12% | judgement; check against any published figure |
| SIM-change feed coverage | 0.90 | assumption: telecom feed is not complete |
| Remote-access detection coverage | 0.85 | assumption: detection is imperfect |
| Attack signal mix per attack type | in config | modelled on public descriptions of each attack |

## 3. What the results do and do not claim

- Data is synthetic. Results show how the policies compare under these assumptions, not real-world rates.
- The ML baseline is trained on data from the same generator, so it is an upper-bound reference, not a fair rival.
  On the v1 run it beats the rules engine at low friction. State this in the paper; our argument for the
  rules engine is transparency (every action has a readable reason), not raw accuracy.
- Evasive-attacker runs hide mutable signals; immutable ones (new device, SIM change) cannot be hidden.

## 4. Open decisions

- [ ] Hold delivery: does a 30-minute hold ask for a confirmation tap, or only wait? Pick one and document it.
- [ ] Replace placeholder costs with literature values where any exist (log them in `docs/literature.csv`).

## 5. Simulator and learned attacker (owner: Person 1)

| Quantity | Value | Where | Note |
|---|---|---|---|
| Attack signal mix, amounts, `immutable` lists | per attack type | `attacks:` | judgement; immutable = signal the attack cannot work without (simswap: SIM change, screenshare: remote app, collect and stolen: new payee) |
| Evasive variant | 60% look-normal amounts, no velocity, no public network, 85% clean payee number | `generator.evasive_params` | hand-written; the evasive random draws use a separate stream, so normal and evasive runs of one seed share every other number (paired) |
| Attacker probe budget | 120 policy probes per attacker | `attacker.tries` | a real attacker cannot test a bank's policy without limit; 40% random search, then CMA-ES |
| Attacker amount cap | Rs 1,00,000 per payment, applied to every attacker alike | `attacker.max_amount` | assumed UPI per-payment limit, **verify against NPCI before the paper**; without a cap the learned attacker simply inflates amounts |
| Attacker knowledge | probes the policy and sees the outcome (white-box on results, not on the weights) | `sim/attacker.py` | strong-attacker assumption, so the worst-case curve is a lower bound for the policy |
| Train / test seeds | train 1-3, test 101-105 | `attacker.train_seeds`, `attacker.test_seeds` | attacker never sees the test seeds |
| Held-out attack type | `collect` (configurable) | `attacker.held_out` | one shared strategy is trained on the other four types and tested on this one |
| Learned attacker's adjustable parameters | up to 10 per type (8 to 10 after immutable signals are frozen) | `PARAMS` in `sim/attacker.py` | amount level and spread, velocity, far-location, network mix, clean-payee routing, new device, new payee, hiding SIM/remote signals |

The attacker's CMA-ES needs `pip install -e ".[opt]"`. Without it the code warns and uses a built-in evolution
strategy, so numbers differ slightly. The committed attacker results were produced with `cma` installed.

Reading the results: compare attackers by **% of attacked rupees stopped** (`*_prevented`). Rupees lost (`*_lost`)
are not comparable across attackers because the learned attacker chooses larger amounts.
`generate()` does not apply the amount cap; only the attacker experiments do.
