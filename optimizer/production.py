import cvxpy as cp
import numpy as np

from .sources import (
    WindPower,
    SolarPower,
    NuclearPower,
    GasPower,
    CoalPower,
    HydroPower,
    ReservoirHydroPower,
    StoredHydroPower,
)

from .rte import RTEAPIClient

from datetime import datetime


class ProductionPrediction:
    def __init__(self, sources: list):
        self.sources = sources

    def get_consumption(self, start, end):
        start_dtime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
        end_dtime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)

        consumption = np.zeros(n_bins)
        data_points = np.zeros(n_bins)

        api = RTEAPIClient()

        res = api.request(
            f"http://digital.iservices.rte-france.com/open_api/consumption/v1/short_term?start_date={start}&end_date={end}",
        )

        data = res.json()

        for forecast in data["short_term"]:
            t_begin = np.array(
                [
                    (
                        datetime.strptime(v["start_date"], "%Y-%m-%dT%H:%M:%S%z")
                        - start_dtime
                    ).total_seconds()
                    / 3600
                    for v in forecast["values"]
                ]
            ).astype(int)

            t_end = np.array(
                [
                    (
                        datetime.strptime(v["end_date"], "%Y-%m-%dT%H:%M:%S%z")
                        - start_dtime
                    ).total_seconds()
                    / 3600
                    for v in forecast["values"]
                ]
            ).astype(int)

            values = np.array([v["value"] for v in forecast["values"]])

            for i in range(len(t_begin)):
                consumption[t_begin[i] : t_end[i]] += values[i]
                data_points[t_begin[i] : t_end[i]] += 1

        return consumption / data_points

    def dispatch(self, start, end):
        consumption = self.get_consumption(start, end)

        n_bins = len(consumption)
        n_sources = len(self.sources)

        x = cp.Variable((n_sources, n_bins))

        availability = np.array(
            [self.sources[i].get_availability(start, end) for i in range(n_sources)]
        )
        marginal_cost = np.array(
            [self.sources[i].marginal_cost for i in range(n_sources)]
        )

        print(availability)
        print(availability.sum(axis=0))
        print(consumption)

        constraints = [
            x >= 0,  # production must be positive
            x
            <= availability,  # production from each source cannot exceed availability at any time
            cp.sum(x, axis=0)
            >= consumption,  # total production must meet demand at any time
        ]

        prob = cp.Problem(
            cp.Minimize(cp.sum(marginal_cost @ x)),
            constraints,
        )

        prob.solve(solver="ECOS")
        production = x.value

        return production
