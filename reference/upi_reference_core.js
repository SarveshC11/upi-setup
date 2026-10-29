(function (root) {
'use strict';

var GROUPS = [
  { id: 'device', label: 'New device', keys: ['newDevice'] },
  { id: 'network', label: 'Network type', keys: ['netMobile', 'netPublic'] },
  { id: 'payee', label: 'New payee', keys: ['newPayee'] },
  { id: 'amount', label: 'Amount vs usual', keys: ['amt2', 'amt10'] },
  { id: 'velocity', label: 'Payment velocity', keys: ['velocity'] },
  { id: 'sim', label: 'Recent SIM change', keys: ['simChange'] },
  { id: 'remote', label: 'Remote-access app', keys: ['remote'] },
  { id: 'location', label: 'Unusual location', keys: ['farLocation'] },
  { id: 'fri', label: 'Payee number risk', keys: ['friMed', 'friHigh', 'friVeryHigh'] }
];

var SIGNAL_LABELS = {
  newDevice: 'New, never-seen device',
  netMobile: 'Mobile data',
  netPublic: 'Open public Wi-Fi',
  newPayee: 'New payee',
  amt2: 'Amount 2 to 10 times usual',
  amt10: 'Amount over 10 times usual',
  velocity: 'More than 3 payments in 10 minutes',
  simChange: 'SIM changed in last 72 hours',
  remote: 'Remote-access app active',
  farLocation: 'Far from usual location',
  friMed: 'Payee number: medium risk',
  friHigh: 'Payee number: high risk',
  friVeryHigh: 'Payee number: very high risk'
};

var DEFAULT_W = {
  newDevice: 30, netMobile: 5, netPublic: 15, newPayee: 15, amt2: 10, amt10: 25,
  velocity: 10, simChange: 25, remote: 30, farLocation: 15,
  friMed: 10, friHigh: 20, friVeryHigh: 35
};

var BASE_T = [20, 50, 70];

var TIERS = {
  '0': { name: 'PIN only', steps: 'UPI PIN, as always. No extra check.' },
  'W': { name: 'Warning shown', steps: 'On-screen warning about the payee, then PIN.' },
  '1': { name: 'Step-up check', steps: 'PIN plus a biometric or OTP check.' },
  '2': { name: 'Hold and confirm', steps: 'PIN, biometric, then a 30-minute hold with a confirmation prompt.' },
  '3': { name: 'Block and call back', steps: 'Payment stopped until the bank verifies by call-back.' }
};

var ATTACKS = {
  simswap: { label: 'SIM swap', newDevice: 0.95, net: [0.1, 0.6, 0.3], newPayee: 0.95, mu: Math.log(25), sg: 0.6, velocity: 0.5, sim: 0.9, remote: 0.05, far: 0.5, fri: [0.45, 0.2, 0.2, 0.15] },
  screenshare: { label: 'Screen-share scam', newDevice: 0.03, net: [0.5, 0.5, 0], newPayee: 0.9, mu: Math.log(15), sg: 0.7, velocity: 0.2, sim: 0, remote: 0.9, far: 0.05, fri: [0.45, 0.2, 0.2, 0.15] },
  collect: { label: 'Collect-request scam', newDevice: 0.02, net: [0.5, 0.48, 0.02], newPayee: 0.9, mu: Math.log(6), sg: 0.6, velocity: 0.1, sim: 0, remote: 0.05, far: 0.05, fri: [0.45, 0.2, 0.2, 0.15] },
  replay: { label: 'Replayed OTP or session', newDevice: 0.8, net: [0.2, 0.3, 0.5], newPayee: 0.7, mu: Math.log(8), sg: 0.6, velocity: 0.7, sim: 0.1, remote: 0.05, far: 0.4, fri: [0.9, 0.05, 0.03, 0.02] },
  stolen: { label: 'Stolen unlocked phone', newDevice: 0, net: [0.1, 0.7, 0.2], newPayee: 0.9, mu: Math.log(15), sg: 0.7, velocity: 0.7, sim: 0, remote: 0, far: 0.6, fri: [0.45, 0.2, 0.2, 0.15] }
};
var ATTACK_ORDER = ['simswap', 'screenshare', 'collect', 'replay', 'stolen'];

var DEFAULT_A = {
  friction: { '0': 0, 'W': 0.5, '1': 1, '2': 5, '3': 10 },
  abandon: { '0': 0, 'W': 0.01, '1': 0.02, '2': 0.25, '3': 0.6 },
  pStop: {
    '0': { simswap: 0, screenshare: 0, collect: 0, replay: 0, stolen: 0 },
    'W': { simswap: 0.05, screenshare: 0.15, collect: 0.15, replay: 0.02, stolen: 0.02 },
    '1': { simswap: 0.15, screenshare: 0.1, collect: 0.1, replay: 0.5, stolen: 0.35 },
    '2': { simswap: 0.55, screenshare: 0.5, collect: 0.5, replay: 0.8, stolen: 0.6 },
    '3': { simswap: 0.9, screenshare: 0.85, collect: 0.85, replay: 0.95, stolen: 0.85 }
  },
  simFeedCoverage: 0.9,
  remoteCoverage: 0.85
};

function clone(o) { return JSON.parse(JSON.stringify(o)); }

function score(tx, W) {
  var parts = [];
  function add(key, on) { if (on && W[key]) parts.push({ key: key, label: SIGNAL_LABELS[key], points: W[key] }); }
  var r = tx.ratio;
  add('newDevice', tx.newDevice);
  add('netMobile', tx.network === 'mobile');
  add('netPublic', tx.network === 'public');
  add('newPayee', tx.newPayee);
  add('amt2', r >= 2 && r <= 10);
  add('amt10', r > 10);
  add('velocity', tx.velocity);
  add('simChange', tx.simChange);
  add('remote', tx.remote);
  add('farLocation', tx.farLocation);
  add('friMed', tx.fri === 1);
  add('friHigh', tx.fri === 2);
  add('friVeryHigh', tx.fri === 3);
  var raw = 0;
  for (var i = 0; i < parts.length; i++) raw += parts[i].points;
  return { score: Math.min(100, raw), raw: raw, parts: parts };
}

function thresholds(d) { return [BASE_T[0] + d, BASE_T[1] + d, BASE_T[2] + d]; }

function tierFromScore(s, T) {
  return s >= T[2] ? '3' : s >= T[1] ? '2' : s >= T[0] ? '1' : '0';
}

var policies = {
  engine: function (W, T) { return function (tx) { return tierFromScore(score(tx, W).score, T); }; },
  pinOnly: function () { return function () { return '0'; }; },
  alwaysStrict: function () { return function () { return '1'; }; },
  amountRule: function (lim) { lim = lim || 10000; return function (tx) { return tx.amount > lim ? '1' : '0'; }; },
  friOnly: function () { return function (tx) { return tx.fri === 3 ? '3' : (tx.fri >= 1 ? 'W' : '0'); }; }
};

function mulberry32(a) {
  return function () {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    var t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

function generate(opts, A) {
  var users = opts.users || 1000, legitPerUser = opts.legitPerUser || 30;
  var perType = opts.attacksPerType == null ? 250 : opts.attacksPerType;
  var evasive = !!opts.evasive;
  var rnd = mulberry32(opts.seed == null ? 7 : opts.seed);
  function norm() { var u = 0; while (u === 0) u = rnd(); var v = rnd(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
  function pick(ws) { var r = rnd(), c = 0; for (var i = 0; i < ws.length; i++) { c += ws[i]; if (r < c) return i; } return ws.length - 1; }
  var NETS = ['home', 'mobile', 'public'];
  var medians = [];
  for (var i = 0; i < users; i++) medians.push(Math.round(Math.min(5000, Math.max(60, Math.exp(Math.log(400) + 0.8 * norm())))));

  function observed(sim, remote) {
    return { simChange: sim && rnd() < A.simFeedCoverage, remote: remote && rnd() < A.remoteCoverage };
  }

  var legit = [];
  for (var u = 0; u < users; u++) {
    for (var k = 0; k < legitPerUser; k++) {
      var ratio = rnd() < 0.03 ? 10 + rnd() * 140 : Math.exp(0.7 * norm());
      var o = observed(rnd() < 0.005, rnd() < 0.005);
      legit.push({
        kind: 'legit', median: medians[u], ratio: ratio, amount: Math.round(medians[u] * ratio),
        newDevice: rnd() < 0.02, network: NETS[pick([0.45, 0.5, 0.05])], newPayee: rnd() < 0.12,
        velocity: rnd() < 0.03, simChange: o.simChange, remote: o.remote, farLocation: rnd() < 0.03,
        fri: pick([0.975, 0.02, 0.004, 0.001]), u: rnd()
      });
    }
  }

  var attacks = [];
  ATTACK_ORDER.forEach(function (type) {
    var S = ATTACKS[type];
    for (var n = 0; n < perType; n++) {
      var med = medians[Math.floor(rnd() * users)];
      var ratio = Math.max(1.2, Math.exp(S.mu + S.sg * norm()));
      var net = pick(S.net), velocity = rnd() < S.velocity, fri = pick(S.fri);
      if (evasive) {
        if (rnd() < 0.6) ratio = 1 + rnd();
        velocity = false;
        if (net === 2) net = 1;
        if (rnd() < 0.85) fri = 0;
      }
      var o = observed(rnd() < S.sim, rnd() < S.remote);
      attacks.push({
        kind: 'attack', type: type, median: med, ratio: ratio, amount: Math.round(med * ratio),
        newDevice: rnd() < S.newDevice, network: NETS[net], newPayee: rnd() < S.newPayee,
        velocity: velocity, simChange: o.simChange, remote: o.remote, farLocation: rnd() < S.far,
        fri: fri, u: rnd()
      });
    }
  });
  return { legit: legit, attacks: attacks };
}

function evaluate(policy, data, A) {
  var fr = 0, extra = 0, aband = 0, counts = { '0': 0, 'W': 0, '1': 0, '2': 0, '3': 0 };
  var i, tx, t;
  for (i = 0; i < data.legit.length; i++) {
    tx = data.legit[i]; t = policy(tx); counts[t]++;
    fr += A.friction[t]; if (t !== '0') extra++;
    if (tx.u < A.abandon[t]) aband++;
  }
  var n = data.legit.length || 1;
  var prevented = 0, total = 0, per = {};
  ATTACK_ORDER.forEach(function (k) { per[k] = { n: 0, stopped: 0 }; });
  for (i = 0; i < data.attacks.length; i++) {
    tx = data.attacks[i]; t = policy(tx);
    var stop = tx.u < A.pStop[t][tx.type];
    total += tx.amount; per[tx.type].n++;
    if (stop) { prevented += tx.amount; per[tx.type].stopped++; }
  }
  return {
    friction: fr / n * 1000, extra: extra / n * 1000, abandoned: aband / n * 1000,
    holds: counts['2'] / n * 1000, blocks: counts['3'] / n * 1000,
    prevented: total ? prevented / total * 100 : 0, lost: total - prevented, total: total, per: per
  };
}

function sweep(W, data, A, from, to, step) {
  var out = [];
  for (var d = from; d <= to; d += step) {
    var m = evaluate(policies.engine(W, thresholds(d)), data, A);
    m.d = d; out.push(m);
  }
  return out;
}

function ablation(W, d, data, A) {
  var T = thresholds(d);
  var base = evaluate(policies.engine(W, T), data, A);
  var rows = GROUPS.map(function (g) {
    var W2 = clone(W); g.keys.forEach(function (k) { W2[k] = 0; });
    var m = evaluate(policies.engine(W2, T), data, A);
    return { id: g.id, label: g.label, prevented: m.prevented, friction: m.friction, dPrevented: m.prevented - base.prevented, dFriction: m.friction - base.friction };
  });
  return { base: base, rows: rows };
}

var api = {
  GROUPS: GROUPS, SIGNAL_LABELS: SIGNAL_LABELS, DEFAULT_W: DEFAULT_W, BASE_T: BASE_T, TIERS: TIERS,
  ATTACKS: ATTACKS, ATTACK_ORDER: ATTACK_ORDER, DEFAULT_A: DEFAULT_A, clone: clone,
  score: score, thresholds: thresholds, tierFromScore: tierFromScore, policies: policies,
  generate: generate, evaluate: evaluate, sweep: sweep, ablation: ablation
};
if (typeof module !== 'undefined' && module.exports) module.exports = api;
else root.UPI = api;
})(typeof window !== 'undefined' ? window : this);
