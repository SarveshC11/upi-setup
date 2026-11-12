"""Figures (owner: Person 3). Every figure is produced by eval/run_experiment.py, never by hand."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

NAMES = {
    "engine": "Step-up engine",
    "pin_only": "PIN only",
    "always_strict": "OTP on every payment",
    "amount_rule": "OTP above Rs 10,000",
    "fri_only": "Risky-number rule (FRI-style)",
    "ml_baseline": "ML baseline (same signals)",
}
COLORS = {
    "engine": "#2a78d6", "pin_only": "#eb6834", "always_strict": "#1baf7a",
    "amount_rule": "#c98500", "fri_only": "#d55181", "ml_baseline": "#6250d6",
}
MARKERS = {"pin_only": "s", "always_strict": "D", "amount_rule": "^", "fri_only": "P",
           "ml_baseline": "o"}
XTICKS = [0, 10, 25, 50, 100, 250, 500, 1000, 1500]
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e1e0d9"


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=9)


def _xscale(ax, xmax, sparse=False):
    ax.set_xscale("function", functions=(np.sqrt, np.square))
    ax.set_xlim(0, xmax)
    ticks = [t for t in XTICKS if t <= xmax]
    if sparse:
        ticks = [t for t in ticks if t in (0, 100, 500, 1000, 1500, 2000)]
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks])


def _draw_tradeoff(ax, curve, base, ml_curve=None, default_shift=0, labels=True):
    ax.plot(curve["friction_mean"], curve["prevented_mean"], color=COLORS["engine"],
            linewidth=2.4, label=NAMES["engine"], zorder=3)
    ax.fill_between(curve["friction_mean"], curve["prevented_mean"] - curve["prevented_std"],
                    curve["prevented_mean"] + curve["prevented_std"],
                    color=COLORS["engine"], alpha=0.15, linewidth=0)
    row = curve[curve["shift"] == default_shift]
    if len(row):
        ax.scatter(row["friction_mean"], row["prevented_mean"], s=90, facecolor="none",
                   edgecolor=INK, linewidth=1.8, zorder=5)
        ax.scatter(row["friction_mean"], row["prevented_mean"], s=28,
                   color=COLORS["engine"], zorder=6)
    if ml_curve is not None:
        ax.plot(ml_curve["friction_mean"], ml_curve["prevented_mean"], color=COLORS["ml_baseline"],
                linewidth=2.0, linestyle="--", label=NAMES["ml_baseline"], zorder=2)
    for name, r in base.iterrows():
        if name in ("engine", "ml_baseline"):
            continue
        ax.errorbar(r["friction_mean"], r["prevented_mean"], yerr=r["prevented_std"],
                    marker=MARKERS[name], markersize=9, color=COLORS[name],
                    markeredgecolor="white", markeredgewidth=1.2, capsize=0, zorder=4,
                    label=NAMES[name], linestyle="none")
    ax.set_ylim(0, 100)
    _style(ax)


def plot_tradeoff(curve, base, out, title, ml_curve=None, default_shift=0):
    fig, ax = plt.subplots(figsize=(8.2, 5.4), dpi=150)
    _draw_tradeoff(ax, curve, base, ml_curve, default_shift)
    xmax = max(curve["friction_mean"].max(), base["friction_mean"].max()) * 1.05
    _xscale(ax, max(xmax, 50))
    ax.set_xlabel("Friction points per 1,000 genuine payments (square-root scale)",
                  color=MUTED, fontsize=10)
    ax.set_ylabel("Fraud value stopped (%)", color=MUTED, fontsize=10)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=12)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    ax.text(0.01, 0.98, "Up and to the left is better. Ring marks the default strictness.\n"
            "Band and bars show standard deviation over seeds.",
            transform=ax.transAxes, fontsize=8, color=MUTED, va="top")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_ablation(abl, out, title="What each signal group adds"):
    d = abl.sort_values("d_prevented_mean")
    fig, ax = plt.subplots(figsize=(7.6, 4.6), dpi=150)
    ax.barh(d["group"], d["d_prevented_mean"], xerr=d["d_prevented_std"],
            color=COLORS["engine"], height=0.6, error_kw={"ecolor": MUTED, "elinewidth": 1})
    ax.axvline(0, color="#c3c2b7", linewidth=1)
    ax.set_xlabel(
        "Change in fraud value stopped (percentage points) when the group is switched off",
                  color=MUTED, fontsize=9)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=12)
    _style(ax)
    ax.grid(False, axis="y")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_per_type(per, out, title="Share of attacks stopped, by attack type"):
    types = list(per["attack_type"].unique())
    names = [n for n in NAMES if n in set(per["policy"])]
    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=150)
    w = 0.8 / len(names)
    for i, n in enumerate(names):
        vals = [float(per[(per.policy == n) & (per.attack_type == t)]["share_mean"].iloc[0]) * 100
                for t in types]
        ax.bar(np.arange(len(types)) + i * w, vals, width=w * 0.92, color=COLORS[n],
               label=NAMES[n])
    ax.set_xticks(np.arange(len(types)) + w * (len(names) - 1) / 2)
    ax.set_xticklabels(types)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Attacks stopped (%)", color=MUTED, fontsize=10)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=12)
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    _style(ax)
    ax.grid(False, axis="x")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def plot_sensitivity(cases, out):
    """cases: {(kind, scale): (curve_df, base_df)}; kind is 'friction' or 'stop'."""
    kinds = ["friction", "stop"]
    scales = sorted({s for _, s in cases})
    fig, axes = plt.subplots(len(kinds), len(scales), figsize=(4.2 * len(scales), 7.2), dpi=150,
                             sharey=True)
    axes = np.atleast_2d(axes)
    xmax = max(max(c["friction_mean"].max(), b["friction_mean"].max()) for c, b in cases.values())
    for r, kind in enumerate(kinds):
        for c, s in enumerate(scales):
            ax = axes[r, c]
            curve, base = cases[(kind, s)]
            _draw_tradeoff(ax, curve, base)
            _xscale(ax, max(xmax * 1.05, 50), sparse=True)
            label = (
                "friction and giving-up chance"
                if kind == "friction"
                else "chance an action stops an attack"
            )
            ax.set_title(f"{label} x{s:g}", fontsize=9, color=INK, loc="left")
            if c == 0:
                ax.set_ylabel("Fraud value stopped (%)", color=MUTED, fontsize=9)
            if r == len(kinds) - 1:
                ax.set_xlabel("Friction points per 1,000 genuine", color=MUTED, fontsize=8)
    h, lab = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=5, frameon=False, fontsize=8)
    fig.suptitle("Sensitivity of the trade-off to the cost assumptions", x=0.01, ha="left",
                 fontsize=12, color=INK)
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    fig.savefig(out)
    plt.close(fig)
