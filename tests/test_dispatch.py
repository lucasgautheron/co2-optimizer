import pytest

from optimizer.sources import (
    WindPower,
    SolarPower,
    NuclearPower,
    GasPower,
    CoalPower,
    BiomassPower,
    HydroPower,
    ReservoirHydroPower,
    StoredHydroPower,
    ImportedPower,
)

from optimizer.production import ProductionPrediction

from datetime import datetime
import numpy as np

from matplotlib import pyplot as plt


@pytest.fixture(scope="function")
def sources(request):
    sources = {
        "wind": WindPower(),
        "solar": SolarPower(),
        "nuclear": NuclearPower(),
        "gas": GasPower(),
        "hydro": HydroPower(),
        "biomass": BiomassPower(),
        "reservoir_hydro": ReservoirHydroPower(),
        "imports": ImportedPower(),
    }
    yield sources


@pytest.mark.parametrize(
    "start,end",
    [
        # ("2020-01-01T00:00:00+01:00", "2020-01-02T00:00:00+01:00"),
        ("2023-06-01T00:00:00+01:00", "2023-06-03T00:00:00+01:00"),
    ],
)
def test_consumption(start, end):
    return
    start_dtime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
    end_dtime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")
    interval_duration = int((end_dtime - start_dtime).total_seconds() / 3600)

    prediction = ProductionPrediction([])
    consumption = prediction.get_consumption(start, end)

    print(consumption)

    assert (
        len(consumption) == interval_duration
    ), "consumption must have as many bins as they are hours in the requested time-period"


@pytest.mark.parametrize(
    "start,end",
    [
        # ("2020-01-01T00:00:00+01:00", "2020-01-02T00:00:00+01:00"),
        ("2022-12-01T00:00:00+01:00", "2022-12-03T00:00:00+01:00"),
    ],
)
def test_dispatch(sources, start, end):
    start_dtime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
    end_dtime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")
    interval_duration = int((end_dtime - start_dtime).total_seconds() / 3600)
    n_sources = len(sources)

    prediction = ProductionPrediction(list(sources.values()))
    production = prediction.dispatch(start, end)

    assert production.shape[0] == len(
        sources
    ), "production must have as many columns as sources"

    assert (
        production.shape[1] == interval_duration
    ), "production must have as many rows as hours"

    carbon_intensity = np.array(
        [sources[source].carbon_intensity for source in sources]
    )

    fig, ax = plt.subplots()

    t = np.arange(interval_duration)
    total = np.zeros(interval_duration)

    n = 0

    for source in sources:
        color = sources[source].color
        ax.bar(t, production[n], bottom=total, color=color, label=source, width=1.0)
        total += production[n]
        n += 1

    ax.set_ylabel("MWh")

    ci = carbon_intensity @ production
    ci /= production.sum(axis=0)

    ax2 = ax.twinx()  # instantiate a second axes that shares the same x-axis

    ax2.set_ylabel(
        "kgCO$_2$/MWh", color="black"
    )  # we already handled the x-label with ax1
    ax2.plot(t, ci, color="black")
    ax2.tick_params(axis="y", labelcolor="black")

    fig.legend(ncol=2)
    fig.savefig("output/production.png", bbox_inches="tight")
