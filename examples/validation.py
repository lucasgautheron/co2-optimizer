import pandas as pd
import numpy as np

from optimizer.optimization import Optimizer
from optimizer.production import MeritOrderModel, LinearCostModel
from optimizer.utils import datetime_to_str

from datetime import timedelta

from glob import glob
from os.path import join as opj

from matplotlib import pyplot as plt


def retrieve_ranges(df, length):
    carbon_intensity = df["carbonIntensity"].values

    i = 0
    while i < len(carbon_intensity) - length:
        if np.all(~np.isnan(carbon_intensity[i : i + length])):
            yield df[i : i + length]
            i += length
        else:
            i += 1


carbon_intensity = pd.concat(
    [pd.read_csv(f) for f in glob("data/carbon-history/*.csv")]
)

carbon_intensity = carbon_intensity.sort_values(
    ["datetime", "updatedAt"]
).drop_duplicates("datetime", keep="last")

carbon_intensity["datetime"] = pd.to_datetime(
    carbon_intensity["datetime"].str[:-4], format="%Y-%m-%dT%H:%M:%S", utc=True
)

carbon_intensity.set_index("datetime", inplace=True)

idx = pd.date_range(
    start=carbon_intensity.index.min(),
    end=carbon_intensity.index.max(),
    freq="1H",
)

carbon_intensity = carbon_intensity.reindex(idx, fill_value=np.nan)

# CHARGE_TIME = 1
MAX_TIMES = [24, 30, 36]

n = 0
for max_time in MAX_TIMES:
    charge_time = int(max_time / 2)
    ranges = retrieve_ranges(carbon_intensity, max_time)

    total_gains = 0
    total_linear_gains = 0
    total_optimum_gains = 0
    total_baseline = 0

    for range in ranges:
        start = datetime_to_str(range.index.min())
        end = datetime_to_str(range.index.min() + timedelta(days=2))

        print(start, end)

        ticks = pd.date_range(start, end, freq="1H")[:-1]
        ci = np.append(range["carbonIntensity"], [0] * (48 - max_time))

        baseline_command = np.zeros(48)
        baseline_command[:charge_time] = 1
        baseline_emissions = np.dot(ci, baseline_command)

        optimum = Optimizer()
        optimum_command = optimum.optimize(charge_time, max_time, start, end, ci)
        optimum_emissions = np.dot(ci, optimum_command)

        model_optimum = Optimizer(model=MeritOrderModel)
        model_command = model_optimum.optimize(charge_time, max_time, start, end)
        model_emissions = np.dot(ci, model_command)

        linear_model_optimum = Optimizer(model=LinearCostModel)
        linear_model_command = linear_model_optimum.optimize(
            charge_time, max_time, start, end
        )
        linear_model_emissions = np.dot(ci, linear_model_command)

        linear_pred = linear_model_optimum.model.dispatch(start, end)

        print(baseline_emissions - model_emissions)
        print(baseline_emissions - linear_model_emissions)
        print(baseline_emissions - optimum_emissions)

        total_baseline += baseline_emissions
        total_gains += baseline_emissions - model_emissions
        total_optimum_gains += baseline_emissions - optimum_emissions

        fig, ax = plt.subplots()
        left_ax, right_ax = model_optimum.model.plot(start, end, ax)
        right_ax.plot(np.arange(len(ci)), ci, label="baseline", color="red")
        fig.legend()
        fig.savefig(f"output/validation_{n}.png")

        fig, ax = plt.subplots()
        left_ax, right_ax = linear_model_optimum.model.plot(start, end, ax)
        right_ax.plot(np.arange(len(ci)), ci, label="baseline", color="red")
        fig.legend()
        fig.savefig(f"output/validation_{n}_linear.png")

        n += 1
    # print(max_time, total_gains / total_baseline, total_optimum_gains / total_baseline)
