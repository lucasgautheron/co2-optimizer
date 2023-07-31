from optimizer.production import LinearCostModel

from datetime import datetime, timedelta
import pytz
from optimizer.utils import str_to_datetime, datetime_to_str

import numpy as np
from scipy.stats import spearmanr, pearsonr

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

model = LinearCostModel()
X, prediction = model.train(start, end)

n_sources = len(model.sources)
availability = X[:, :n_sources].T
consumption = X[:, n_sources + 1].T
truth = X[:, n_sources + 1 :].T
prediction = prediction.T

ci = [source.carbon_intensity for source in model.sources]

print(prediction.shape)
print(truth.shape)

# fig, axes = plt.subplots(nrows=2, ncols=1, sharex=True, sharey=True)

# t = range(prediction.shape[1])
# total_prediction = np.zeros(prediction.shape[1])
# total_truth = np.zeros(prediction.shape[1])

# n = 0
# for source in model.sources:
#     color = source.color
#     axes[0].bar(
#         t,
#         prediction[n],
#         bottom=total_prediction,
#         color=color,
#         label=source.__class__.__name__,
#         width=1.0,
#     )
#     total_prediction += prediction[n]
#     n += 1

# n = 0
# for source in model.sources:
#     color = source.color
#     axes[1].bar(
#         t,
#         truth[n],
#         bottom=total_truth,
#         color=color,
#         label=source.__class__.__name__,
#         width=1.0,
#     )
#     total_truth += truth[n]
#     n += 1

# fig.subplots_adjust(wspace=0, hspace=0)
# fig.savefig("output/train.png", bbox_inches="tight", dpi=200)
# fig.savefig("output/train.eps", bbox_inches="tight")

ci_prediction = (ci @ prediction) / prediction.sum(axis=0)

print(ci_prediction.shape)
ci_truth = (ci @ truth) / truth.sum(axis=0)

for duration in [24, 48]:
    R = []
    for t in range(len(ci_prediction) - duration):
        R.append(
            spearmanr(
                ci_prediction[t : t + duration], ci_truth[t : t + duration]
            ).statistic
        )

    fig, ax = plt.subplots()
    ax.hist(R, bins=np.linspace(-1, 1, 20), histtype="step", density=True)
    ax.axvline(x=np.mean(R), color="red")
    ax.set_xlabel("Spearman $R$")
    ax.set_title(
        f"Correlation between model emissions and actual emissions\n$T={duration},\mu(R)={np.mean(R):.2f}$"
    )
    fig.savefig(f"output/spearman_{duration}.png", bbox_inches="tight")

fig, ax = plt.subplots()
nan = np.isnan(ci_prediction) | np.isnan(ci_truth)
R = pearsonr(ci_prediction[~nan], ci_truth[~nan]).statistic
ax.plot(ci_prediction, label=f"model carbon intensity (R={R:.2f})", lw=0.25)
ax.plot(ci_truth, label="actual carbon intensity", lw=0.25)
ax.set_xlabel("time")
fig.legend()
fig.savefig(f"output/ci.png", bbox_inches="tight", dpi=720)

for k, source in enumerate(model.sources):
    pred = prediction[k] / X[:, k]
    obs = X[:, k + n_sources + 1] / X[:, k]
    nan = np.isnan(pred) | np.isnan(obs)

    R = pearsonr(pred[~nan], obs[~nan]).statistic
    fig, ax = plt.subplots()
    ax.plot(pred, lw=0.25, label=f"model (R={R:.2f})")
    ax.plot(obs, lw=0.25, label="truth")
    ax.set_ylim(-0.1, 1.1)
    ax.set_title(source.__class__.__name__)
    ax.set_ylabel("Production / Available Capacity")
    ax.set_xlabel("Time (Hours)")
    fig.legend()
    fig.savefig(f"output/train_predict_{source.__class__.__name__}.png", dpi=720)
