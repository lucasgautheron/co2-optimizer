from optimizer.production import LinearCostModel
from optimizer.sources import *

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
        hour=0, minute=0, second=0, microsecond=0
    )

    start = datetime_to_str(now - timedelta(days=365))
    end = datetime_to_str(now)
else:
    start = f"{args.start}T00:00:00+01:00"
    end = f"{args.end}T00:00:00+01:00"

sources = [
    WindPower(),
    SolarPower(),
    HydroPower(),
    NuclearPower(),
    GasPower(),
    CoalPower(),
    OilPower(),
    BiomassPower(),
    ReservoirHydroPower(),
    StoredHydroPower(),
    ImportedPower(),
]

model = LinearCostModel(sources)
prediction, truth = model.train(start, end)

print(prediction.shape)
print(truth.shape)

fig, axes = plt.subplots(nrows=2, ncols=1, sharex=True, sharey=True)

t = range(prediction.shape[1])
total_prediction = np.zeros(prediction.shape[1])
total_truth = np.zeros(prediction.shape[1])

n = 0
for source in model.sources:
    color = source.color
    axes[0].bar(
        t,
        prediction[n],
        bottom=total_prediction,
        color=color,
        label=source.__class__.__name__,
        width=1.0,
    )
    total_prediction += prediction[n]
    n += 1

n = 0
for source in model.sources:
    color = source.color
    axes[1].bar(
        t,
        truth[n],
        bottom=total_truth,
        color=color,
        label=source.__class__.__name__,
        width=1.0,
    )
    total_truth += truth[n]
    n += 1

fig.subplots_adjust(wspace=0, hspace=0)
fig.savefig("output/train.png", bbox_inches="tight", dpi=200)
fig.savefig("output/train.eps", bbox_inches="tight")
