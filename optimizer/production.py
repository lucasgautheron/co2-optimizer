from abc import ABC, abstractmethod

import cvxpy as cp
import numpy as np

from .resources import RTEAPI

from .utils import str_to_datetime, datetime_to_str, now, interp
from datetime import timedelta

import pandas as pd


class ProductionModel(ABC):
    def __init(self):
        pass

    def get_consumption(self, start, end):
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)

        start_rq = datetime_to_str(start_dtime.replace(hour=0, minute=0, second=0))
        end_rq = datetime_to_str(
            (end_dtime + timedelta(days=1)).replace(hour=0, minute=0, second=0)
        )

        consumption = np.zeros(n_bins)
        data_points = np.zeros(n_bins)

        api = RTEAPI()
        res = api.request(
            f"http://digital.iservices.rte-france.com/open_api/consumption/v1/short_term?start_date={start_rq}&end_date={end_rq}",
        )

        data = res.json()

        for forecast in data["short_term"]:
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
        consumption = interp(consumption, kind="nearest")
        return consumption

    @abstractmethod
    def dispatch(self, start, end):
        pass


class MeritOrderModel(ProductionModel):
    def __init__(self, sources: list):
        self.sources = sources

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


class NNModel(ProductionModel):
    def __init__(self, sources: list):
        self.sources = sources
        self.T = 48

    def train(self, start, end):
        n_sources = len(self.sources)
        consumption = self.get_consumption(start, end)

        start_dt = str_to_datetime(start)
        end_dt = str_to_datetime(end)
        n_bins = int((end_dt - start_dt).total_seconds() / 3600)

        production_history = np.array(
            [self.sources[i].get_production(start, end) for i in range(n_sources)]
        )

        availability = np.array(
            [self.sources[i].get_availability(start, end) for i in range(n_sources)]
        )

        X = []
        y = []

        for i in range(n_bins - self.T):
            _x = np.zeros((self.T, n_sources + 1))
            _x[:, :n_sources] = availability[:, i : i + self.T].T
            _x[:, -1] = consumption[i : i + self.T].T
            _y = (
                production_history[:, i : i + self.T].T
                / availability[:, i : i + self.T].T
            )

            _y[:, :2] = 1

            print(_y.shape)

            if not np.all(~np.isnan(_x)) or not np.all(~np.isnan(_y)):
                print("x:", _x)
                print("y:", _y)
                continue

            X.append(_x)
            y.append(_y)

        print(len(X))

    def save(self):
        pass

    def load(self):
        pass

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
