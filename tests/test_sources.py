import pytest

from optimizer.sources import (
    WindPower,
    SolarPower,
    NuclearPower,
    GasPower,
    CoalPower,
    HydroPower,
    StoredHydroPower,
    ReservoirHydroPower,
    ImportedPower
)

from datetime import datetime
import numpy as np

@pytest.fixture(scope="function")
def sources(request):
    sources = {
        "wind": WindPower(),
        "solar": SolarPower(),
        "nuclear": NuclearPower(),
        "gas": GasPower(),
        "coal": CoalPower(),
        "hydro": HydroPower(),
        "imports": ImportedPower()
    }
    yield sources


@pytest.mark.parametrize(
    "start,end",
    [
        # ("2020-01-01T00:00:00+01:00", "2020-01-02T00:00:00+01:00"),
        ("2023-03-02T00:00:00+01:00", "2023-03-04T00:00:00+01:00"),
    ],
)
def test_availability(sources, start, end):
    start_dtime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
    end_dtime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")
    interval_duration = int((end_dtime - start_dtime).total_seconds() / 3600)

    for source in ["solar", "wind", "nuclear", "gas", "hydro", "imports"]:
        availability = sources[source].get_availability(start, end)
        print(source, availability)

        assert (
            len(availability) == interval_duration
        ), f"{source} availability must have as many bins as they are hours in the requested time-period"


def test_carbon_intensity(sources):
    sources_by_ascending_ci = ["nuclear", "hydro", "wind", "solar", "gas", "coal"]
    carbon_intensity = [
        sources[source].carbon_intensity for source in sources_by_ascending_ci
    ]

    assert np.all(
        np.diff(carbon_intensity) > 0
    ), "carbon intensity must be such that " + "<".join(sources_by_ascending_ci)


def test_marginal_cost(sources):
    ascending_merit_order = ["solar", "wind", "hydro", "nuclear", "gas", "coal"]
    marginal_cost = [sources[source].marginal_cost for source in ascending_merit_order]

    assert np.all(
        np.diff(marginal_cost) >= 0
    ), "marginal cost must follow merit order " + "<=".join(ascending_merit_order)
