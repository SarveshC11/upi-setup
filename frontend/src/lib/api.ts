// Typed client for the decision service (service/api.py). All scoring happens on the server.

export type Tier = "0" | "W" | "1" | "2" | "3"
export type Network = "home" | "mobile" | "public"

export interface Payment {
  amount: number
  median: number
  network: Network
  new_device: boolean
  new_payee: boolean
  velocity: boolean
  sim_change: boolean
  remote: boolean
  far_location: boolean
  fri: number
}

export interface ScoreResult {
  score: number
  raw_total: number
  tier: Tier
  tier_name: string
  breakdown: { signal: string; points: number }[]
  thresholds: number[]
  policy_version: string
}

export interface CompareResult {
  engine: ScoreResult
  baselines: Record<string, Tier>
  tier_names: Record<Tier, string>
}

export interface Policy {
  weights: Record<string, number>
  base_thresholds: number[]
  thresholds: number[]
  shift: number
  score_cap: number
  policy_version: string
  strictness_range: [number, number]
}

export interface Point {
  shift: number
  friction: number
  prevented_pct: number
  extra: number
}

export interface BaselinePoint extends Omit<Point, "shift"> {
  name: string
}

export interface Simulation {
  curve: Point[]
  baselines: BaselinePoint[]
  current: Point
  n_legit: number
  n_attacks: number
  seed: number
  evasive: boolean
  policy_version: string
  elapsed_ms: number
}

export interface SimulateRequest {
  seed: number
  n_users: number
  payments_per_user: number
  attacks_per_type: number
  evasive: boolean
  shift_start: number
  shift_stop: number
  shift_step: number
}

export interface Decision {
  timestamp: string
  inputs: Payment
  score: number
  raw_total: number
  breakdown: { signal: string; points: number }[]
  tier: Tier
  thresholds: number[]
  policy_version: string
}

async function call<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = (data as { detail?: unknown }).detail
    throw new Error(typeof detail === "string" ? detail : `The service returned HTTP ${res.status}.`)
  }
  return data as T
}

export const api = {
  health: () => call<{ status: string; policy_version: string; config_fingerprint: string }>("/health"),
  policy: () => call<Policy>("/policy"),
  updatePolicy: (body: { shift?: number; weights?: Record<string, number>; reset?: boolean }) =>
    call<Policy>("/policy", body),
  compare: (p: Payment) => call<CompareResult>("/compare", p),
  simulate: (req: SimulateRequest) => call<Simulation>("/simulate", req),
  decisions: (limit = 50) => call<{ decisions: Decision[] }>(`/decisions?limit=${limit}`),
}
