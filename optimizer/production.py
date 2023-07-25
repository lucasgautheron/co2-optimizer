from abc import ABC, abstractmethod

import cvxpy as cp
import numpy as np
from scipy.optimize import minimize

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

        start_rq_dtime = start_dtime.replace(hour=0, minute=0, second=0)
        end_rq_dtime = (end_dtime + timedelta(days=1)).replace(
            hour=0, minute=0, second=0
        )

        consumption = np.zeros(n_bins)
        data_points = np.zeros(n_bins)

        api = RTEAPI()

        periods = pd.date_range(start=start_rq_dtime, end=end_rq_dtime, freq="2d")
        if len(periods) == 0:
            periods = [(start_rq_dtime, end_rq_dtime)]
        else:
            periods = zip(periods[:-1], periods[1:])

        for t0, t1 in periods:
            start_rq = datetime_to_str(t0)
            end_rq = datetime_to_str(t1)

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

    def solve(x, c, theta):
        theta = c * theta

        n_sources = x.shape[1] - 1
        pred = cp.Variable((x.shape[0], n_sources))

        constraints = [
            pred >= 0,  # production must be positive
            pred <= x[:, :n_sources]/1000,  # prod < avail
            cp.sum(pred, axis=1)
            >= x[:, n_sources]/1000,  # total production must meet demand at any time,
        ]

        prob = cp.Problem(
            cp.Minimize(cp.sum(pred @ c + cp.square(pred) @ theta)),
            constraints,
        )

        # prob.solve(solver="SCS", verbose=True)
        prob.solve()
        return pred.value

    def objective(x, c, theta):
        n_sources = int((x.shape[1] - 1) / 2)
        pred = NNModel.solve(x[:, : n_sources + 1], c, theta)

        loss = np.sum(((pred/1000 - x[:, n_sources + 1 :]/1000)) ** 2)
        print(loss)
        return loss

    def train(self, start, end):
        n_sources = len(self.sources)
        consumption = self.get_consumption(start, end)

        start_dt = str_to_datetime(start)
        end_dt = str_to_datetime(end)
        n_bins = int((end_dt - start_dt).total_seconds() / 3600)

        production_history = np.array(
            [source.get_production(start, end) for source in self.sources]
        )

        availability = np.array(
            [source.get_availability(start, end) for source in self.sources]
        )

        marginal_cost = np.array([source.marginal_cost for source in self.sources])

        X = np.zeros((n_bins, 2 * n_sources + 1))
        X[:, :n_sources] = availability.T
        X[:, n_sources] = consumption.T
        X[:, n_sources + 1 :] = np.minimum(availability.T, production_history.T)
        X = X[~np.isnan(X).any(axis=1)]

        from functools import partial

        theta0 = np.zeros(n_sources)
        theta0[2:] += 0.05

        res = minimize(
            partial(NNModel.objective, X, marginal_cost),
            theta0,
            method="SLSQP",
            bounds=[(0, 1)] * n_sources,
        )

        theta = res.x
        np.save("data/theta.npy", theta)

    def save(self):
        pass

    def load(self):
        pass

    def dispatch(self, start, end):
        consumption = self.get_consumption(start, end)

        n_bins = len(consumption)
        n_sources = len(self.sources)

        X = np.zeros((n_bins, n_sources + 1))

        X[:, :-1] = np.array(
            [source.get_availability(start, end) for source in self.sources]
        ).T
        X[:, -1] = consumption.T

        marginal_cost = np.array([source.marginal_cost for source in self.sources])

        theta = np.load("data/theta.npy")

        for i, source in enumerate(self.sources):
            print(source.__class__.__name__)
            print(theta[i])

        return NNModel.solve(X, marginal_cost, theta).T
