from optimizer.optimization import Optimizer

from datetime import datetime, timedelta
import pytz
from optimizer.utils import str_to_datetime, datetime_to_str

import numpy as np

from matplotlib import pyplot as plt

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--start", default=None)
parser.add_argument("--end", default=None)
args = parser.parse_args()

if args.start is None:
    now = datetime.now(pytz.timezone("Europe/Paris")).replace(
        minute=0, second=0, microsecond=0
    )

    start = datetime_to_str(now)
    end = datetime_to_str(now + timedelta(days=2))
else:
    start = f"{args.start}T00:00:00+01:00"
    end = f"{args.end}T00:00:00+01:00"

optimizer = Optimizer()
production = optimizer.prediction.dispatch(start, end)
carbon_intensity = np.array([source.carbon_intensity for source in optimizer.sources])

t = np.arange(production.shape[1])
hours = [
    (str_to_datetime(start).replace(tzinfo=None) + timedelta(hours=int(h))).strftime(
        "%H:%M"
    )
    for h in np.arange(production.shape[1])
]

total = np.zeros(production.shape[1])

fig, axes = plt.subplots(
    nrows=2, ncols=1, sharex=True, figsize=(7.5, 7.5), height_ratios=[3, 1]
)

n = 0
for source in optimizer.sources:
    color = source.color
    axes[0].bar(
        t,
        production[n],
        bottom=total,
        color=color,
        label=source.__class__.__name__,
        width=1.0,
    )
    total += production[n]
    n += 1

axes[0].set_ylabel("MWh")

ci = carbon_intensity @ production
ci /= production.sum(axis=0)

ax2 = axes[0].twinx()  # instantiate a second axes that shares the same x-axis

ax2.set_ylabel("kgCO$_2$/MWh", color="black")  # we already handled the x-label with ax1
ax2.plot(t, ci, color="black", label="kgCO$_2$/MWh")
ax2.tick_params(axis="y", labelcolor="black")

ref_emissions = None
styles = ["dotted", "dashed", "-"]

for i, max_time in enumerate([12, 24, 48]):
    command = optimizer.optimize(
        min_time=12,
        max_time=max_time,
        start=start,
        end=end,
    )
    emissions = np.dot(ci, command)

    if ref_emissions is None:
        ref_emissions = emissions

    emissions_saved = (1 - emissions / ref_emissions) * 100

    axes[1].plot(
        t,
        command,
        color="red",
        label=f"{max_time}h max ({emissions_saved:.0f}% CO$_2$ saved)",
        ls=styles[i],
    )

axes[1].set_ylabel("Optimal command")
axes[1].set_xticks(t[::4])
axes[1].set_xticklabels([hours[i] for i in t[::4]], rotation=90)

fig.legend(bbox_to_anchor=(0.98, 0.9), loc="upper left")
plt.subplots_adjust(wspace=0, hspace=0)
fig.suptitle("Optimal command for 12h charge time")
fig.savefig(
    f"output/all_{start[:4+1+2+1+2]}_{end[:4+1+2+1+2]}.png",
    bbox_inches="tight",
)
fig.savefig(
    f"output/all_{start[:4+1+2+1+2]}_{end[:4+1+2+1+2]}.eps",
    bbox_inches="tight",
)
