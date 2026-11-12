import type { Network, Payment, Tier } from "@/lib/api"

export const TIER: Record<Tier, { short: string; color: string; says: string }> = {
  "0": { short: "Cleared", color: "var(--tier-0)", says: "Nothing extra. The payer enters their UPI PIN as usual." },
  W: { short: "Warning", color: "var(--tier-w)", says: "An on-screen warning, then the PIN." },
  "1": { short: "Step-up", color: "var(--tier-1)", says: "PIN plus a biometric or OTP check." },
  "2": { short: "Hold", color: "var(--tier-2)", says: "PIN and biometric, then a 30-minute hold while the account owner confirms." },
  "3": { short: "Block", color: "var(--tier-3)", says: "Stopped until the bank verifies the payment with a call-back." },
}

export const BASELINE_LABEL: Record<string, string> = {
  pin_only: "PIN only",
  always_strict: "OTP on every payment",
  amount_rule: "OTP above ₹10,000",
  fri_only: "FRI-style rule",
}

export const SIGNAL_LABEL: Record<string, string> = {
  new_device: "New device",
  net_mobile: "Mobile data",
  net_public: "Public network",
  new_payee: "New payee",
  amt_2x_10x: "Amount 2–10× usual",
  amt_over_10x: "Amount over 10× usual",
  velocity: "Rapid payments",
  sim_change: "SIM changed recently",
  remote: "Remote-access app",
  far_location: "Far from usual place",
  fri_1: "Payee FRI: medium",
  fri_2: "Payee FRI: high",
  fri_3: "Payee FRI: very high",
}

export type Flag = "new_device" | "new_payee" | "velocity" | "sim_change" | "remote" | "far_location"

export const FLAGS: { field: Flag; label: string; weight: string }[] = [
  { field: "new_device", label: "New device", weight: "new_device" },
  { field: "new_payee", label: "New payee", weight: "new_payee" },
  { field: "velocity", label: "More than 3 payments in 10 min", weight: "velocity" },
  { field: "sim_change", label: "SIM changed in last 72 h", weight: "sim_change" },
  { field: "remote", label: "Remote-access app running", weight: "remote" },
  { field: "far_location", label: "Far from usual location", weight: "far_location" },
]

export const NETWORKS: { value: Network; label: string; weight: string | null }[] = [
  { value: "home", label: "Home Wi-Fi", weight: null },
  { value: "mobile", label: "Mobile data", weight: "net_mobile" },
  { value: "public", label: "Public", weight: "net_public" },
]

export const FRI_LEVELS: { value: number; label: string; weight: string | null }[] = [
  { value: 0, label: "None", weight: null },
  { value: 1, label: "Medium", weight: "fri_1" },
  { value: 2, label: "High", weight: "fri_2" },
  { value: 3, label: "Very high", weight: "fri_3" },
]

const OFF = { new_device: false, new_payee: false, velocity: false, sim_change: false, remote: false, far_location: false, fri: 0 }

// The five golden cases from the team guide (B2). ratio = amount / median.
export const PRESETS: Record<string, Payment> = {
  "Chai stall": { ...OFF, amount: 288, median: 400, network: "mobile" },
  "Rent deposit": { ...OFF, amount: 45000, median: 250, network: "home", new_payee: true },
  "SIM-swap fraud": { ...OFF, amount: 45000, median: 250, network: "public", new_device: true, new_payee: true, sim_change: true },
  "Screen-share scam": { ...OFF, amount: 45000, median: 250, network: "home", new_payee: true, remote: true },
  "Stolen phone": { ...OFF, amount: 45000, median: 250, network: "home", new_payee: true, velocity: true, far_location: true },
}

export const inr = (n: number, digits = 0) =>
  n.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits })
