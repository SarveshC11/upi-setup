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
