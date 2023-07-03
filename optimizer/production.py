import cvxpy as cp
import numpy as np

from .rte import RTEAPIClient

from .utils import str_to_datetime, datetime_to_str, now


class ProductionPrediction:
    def __init__(self, sources: list):
        self.sources = sources

    def get_consumption(self, start, end):
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)

        start_rq = datetime_to_str(start_dtime.replace(hour=0, minute=0, second=0))

        consumption = np.zeros(n_bins)
        data_points = np.zeros(n_bins)

        api = RTEAPIClient()
        res = api.request(
            f"http://digital.iservices.rte-france.com/open_api/consumption/v1/short_term?start_date={start_rq}&end_date={end}",
        )

        data = res.json()

        for forecast in data["short_term"]:
            print(forecast["type"], forecast["start_date"], forecast["end_date"])

            t_begin = np.array(
                [
                    (str_to_datetime(v["start_date"]) - start_dtime).total_seconds()
                    / 3600
                    for v in forecast["values"]
                ]
            ).astype(int)

            t_end = np.array(
                [
                    (str_to_datetime(v["end_date"]) - start_dtime).total_seconds()
                    / 3600
                    for v in forecast["values"]
                ]
            ).astype(int)

            values = np.array([v["value"] for v in forecast["values"]])

            for i in range(len(t_begin)):
                consumption[t_begin[i] : t_end[i]] += values[i]
                data_points[t_begin[i] : t_end[i]] += 1

        consumption = consumption / data_points
        consumption[np.isnan(consumption)] = consumption[~np.isnan(consumption)].max()
        return consumption

    def dispatch(self, start, end):
        consumption = self.get_consumption(start, end)

        n_bins = len(consumption)
        n_sources = len(self.sources)

        availability = np.array(
            [self.sources[i].get_availability(start, end) for i in range(n_sources)]
        )
        marginal_cost = np.array(
            [self.sources[i].marginal_cost for i in range(n_sources)]
        )

        print(consumption)
        print(availability.sum(axis=0))
        print(availability)

        x = cp.Variable((n_sources, n_bins))

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

        prob.solve()
        production = x.value

        return production
