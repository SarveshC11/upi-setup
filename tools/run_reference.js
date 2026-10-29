// Runs the JS reference simulator and prints headline numbers as JSON (used by tests/test_parity.py).
// Usage: node tools/run_reference.js <seed> [users] [legitPerUser] [attacksPerType]
const U = require('../reference/upi_reference_core.js');
const [seed, users, lpu, apt] = process.argv.slice(2).map(Number);
const opts = { seed: seed || 7, users: users || 1000, legitPerUser: lpu || 30, attacksPerType: apt || 300 };
const data = U.generate(opts, U.DEFAULT_A);
const out = {};
const pol = {
  pin_only: U.policies.pinOnly(), always_strict: U.policies.alwaysStrict(),
  amount_rule: U.policies.amountRule(10000), fri_only: U.policies.friOnly(),
  engine: U.policies.engine(U.DEFAULT_W, U.thresholds(0)),
};
for (const k of Object.keys(pol)) {
  const m = U.evaluate(pol[k], data, U.DEFAULT_A);
  out[k] = { friction: m.friction, extra: m.extra, abandoned: m.abandoned, prevented: m.prevented };
}
console.log(JSON.stringify(out));
