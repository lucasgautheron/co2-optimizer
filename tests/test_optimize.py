import pytest

from optimizer.optimization import Optimizer

from datetime import datetime
import numpy as np

from matplotlib import pyplot as plt


@pytest.mark.parametrize(
    "start,end,max_time",
    [
        # ("2020-01-01T00:00:00+01:00", "2020-01-02T00:00:00+01:00"),
        ("2022-12-01T00:00:00+01:00", "2022-12-03T00:00:00+01:00", 12),
        ("2022-12-01T00:00:00+01:00", "2022-12-03T00:00:00+01:00", 24),
        ("2022-12-01T00:00:00+01:00", "2022-12-03T00:00:00+01:00", 48),
    ],
)
def test_optimize(start, end, max_time):
    optimizer = Optimizer()
    command = optimizer.optimize(min_time=12, max_time=max_time, start=start, end=end)

    fig, ax = plt.subplots()
    t = np.arange(len(command))
    ax.plot(t, command, color="black")
    fig.savefig(f"output/command_{max_time}.png", bbox_inches="tight")
