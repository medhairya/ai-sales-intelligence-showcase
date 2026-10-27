"""Render assets/token_bucket.png by driving the real TokenBucketLimiter.

Run from the repo root:  python assets/src/token_bucket_plot.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.rate_limiter import TokenBucketLimiter  # noqa: E402


class Clock:
    t = 0.0

    def __call__(self) -> float:
        return self.t


CAPACITY, RATE = 20, 1.0

# Traffic: a burst of 30 requests at t=5s, steady 3 req/s from 25-45s, then idle.
BURST = [5.0 + i * 0.05 for i in range(30)]
STEADY = [25.0 + i / 3 for i in range(60)]
events = sorted(BURST + STEADY)

clock = Clock()
rl = TokenBucketLimiter(CAPACITY, RATE, clock=clock)

allowed_t, blocked_t = [], []
for t in events:
    clock.t = t
    (allowed_t if rl.check("client").allowed else blocked_t).append(t)

# Sample bucket level over time by replaying the same traffic.
clock2 = Clock()
rl2 = TokenBucketLimiter(CAPACITY, RATE, clock=clock2)
ts, levels = [], []
ev_iter = iter(events)
next_ev = next(ev_iter, None)
t = 0.0
while t <= 60.0:
    while next_ev is not None and next_ev <= t:
        clock2.t = next_ev
        rl2.check("client")
        next_ev = next(ev_iter, None)
    clock2.t = t
    b = rl2._buckets.get("client")
    level = CAPACITY if b is None else min(CAPACITY, b.tokens + (t - b.updated_at) * RATE)
    ts.append(t)
    levels.append(level)
    t += 0.05

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(9, 4.6), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
)

ax1.fill_between(ts, levels, color="#ECECFF")
ax1.plot(ts, levels, color="#5B5BD6", lw=1.8, label="tokens in bucket")
ax1.axhline(CAPACITY, color="#999", ls="--", lw=1)
ax1.text(60, CAPACITY + 0.5, f"capacity C = {CAPACITY}", ha="right", color="#666", fontsize=9)
ax1.set_ylabel("tokens")
ax1.set_ylim(0, CAPACITY + 3)
burst_blocked = sum(1 for t in blocked_t if t < 10)
steady_blocked = sum(1 for t in blocked_t if t >= 20)
arrow = {"arrowstyle": "->", "color": "#444"}
ax1.annotate(f"burst of {len(BURST)} requests:\n"
             f"{len(BURST) - burst_blocked} served, {burst_blocked} get 429",
             xy=(6.6, 0.5), xytext=(9, 13), fontsize=9, arrowprops=arrow)
ax1.annotate(f"3 req/s > refill r = 1/s:\nbucket drains, {steady_blocked} throttled",
             xy=(40, 0.5), xytext=(28.5, 15.5), fontsize=9, arrowprops=arrow)
ax1.annotate("idle: refills at r", xy=(53, 8), xytext=(50, 15), fontsize=9,
             arrowprops=arrow)
for s in ("top", "right"):
    ax1.spines[s].set_visible(False)

ax2.eventplot([allowed_t], lineoffsets=1, colors="#2EA44F", linelengths=0.7)
ax2.eventplot([blocked_t], lineoffsets=0, colors="#D73A49", linelengths=0.7)
ax2.set_yticks([0, 1], ["429", "200"])
ax2.set_ylim(-0.6, 1.6)
ax2.set_xlabel("time (s)")
ax2.set_xlim(0, 60)
for s in ("top", "right"):
    ax2.spines[s].set_visible(False)

fig.suptitle(
    f"Token bucket in action (C = {CAPACITY}, r = {RATE:g}/s): "
    f"{len(allowed_t)} allowed, {len(blocked_t)} rate-limited",
    fontsize=11,
)
fig.tight_layout()
out = ROOT / "assets" / "token_bucket.png"
fig.savefig(out, dpi=160)
print(f"wrote {out}  allowed={len(allowed_t)} blocked={len(blocked_t)}")
