from abc import ABC, abstractmethod
from itertools import product

import cvxpy as cp
import numpy as np
from scipy.optimize import minimize

from .sources import *
from .resources import RTEAPI

from .utils import str_to_datetime, datetime_to_str, interp
from datetime import timedelta

import pandas as pd


class ProductionModel(ABC):
    def __init(self):
        pass

    def get_consumption(self, start, end):
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)

        start_rq_dtime = (start_dtime - timedelta(days=1)).replace(
            hour=0, minute=0, second=0
        )
        end_rq_dtime = (end_dtime + timedelta(days=1)).replace(
            hour=0, minute=0, second=0
        )

        consumption = np.zeros(n_bins)
        data_points = np.zeros(n_bins)

        api = RTEAPI()

        periods = pd.date_range(start=start_rq_dtime, end=end_rq_dtime, freq="2d")
        if len(periods) <= 1:
            periods = [(start_rq_dtime, end_rq_dtime)]
        else:
            periods = list(zip(periods[:-1], periods[1:])) + list(
                zip(periods[:-1] + timedelta(days=1), periods[1:] + timedelta(days=1))
            )

        for t0, t1 in periods:
            start_rq = datetime_to_str(t0)
            end_rq = datetime_to_str(t1)

            res = api.request(
                f"http://digital.iservices.rte-france.com/open_api/consumption/v1/short_term?start_date={start_rq}&end_date={end_rq}",
            )

            data = res.json()

            if "short_term" not in data:
                continue

            for forecast in data["short_term"]:
                t_begin, t_end, values = RTEAPI.values_hist(
                    forecast["values"], start_dtime, end_dtime
                )

                for i in range(len(t_begin)):
                    consumption[t_begin[i] : t_end[i]] += values[i]
                    data_points[t_begin[i] : t_end[i]] += 1

        consumption = consumption / data_points
        consumption = interp(consumption, kind="nearest")
        return consumption

    @abstractmethod
    def dispatch(self, start, end):
        pass

    def plot(self, start, end, ax):
        carbon_intensity = [source.carbon_intensity for source in self.sources]
        production = self.dispatch(start, end)

        t = range(production.shape[1])
        hours = [
            (
                str_to_datetime(start).replace(tzinfo=None) + timedelta(hours=int(h))
            ).strftime("%H:%M")
            for h in np.arange(production.shape[1])
        ]

        total = np.zeros(production.shape[1])

        n = 0
        for source in self.sources:
            color = source.color
            ax.bar(
                t,
                production[n],
                bottom=total,
                color=color,
                label=source.__class__.__name__,
                width=1.0,
            )
            total += production[n]
            n += 1

        ax.set_ylabel("MWh")

        ci = carbon_intensity @ production
        ci /= production.sum(axis=0)

        ax2 = ax.twinx()  # instantiate a second axes that shares the same x-axis

        ax2.set_ylabel(
            "kgCO$_2$/MWh", color="black"
        )  # we already handled the x-label with ax1
        ax2.plot(t, ci, color="black", label="kgCO$_2$/MWh")
        ax2.tick_params(axis="y", labelcolor="black")
        ax.set_xticks(t[::4])
        ax.set_xticklabels([hours[i] for i in t[::4]], rotation=90)

        return ax, ax2


class MeritOrderModel(ProductionModel):
    def __init__(self):
        self.sources = [
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


class LinearCostModel(ProductionModel):
    def __init__(self):
        self.sources = [
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
        self.T = 48

    def solve(x, c, min_load, storage_capacity, theta):
        n_sources = x.shape[1] - 1

        parametrize = (c > 0) & (storage_capacity == 0)
        n_param_sources = np.sum(parametrize)
        linear_costs = theta[:n_param_sources] * c[parametrize]

        units_min_prod = np.zeros((n_param_sources, n_param_sources))
        np.fill_diagonal(
            units_min_prod,
            theta[n_param_sources : 2 * n_param_sources],
        )
        units_rampup_costs = theta[2 * n_param_sources :] * c[parametrize]

        pred = cp.Variable((x.shape[0], n_sources))
        activ = cp.Variable((x.shape[0], n_sources))
        store = cp.Variable((x.shape[0], np.sum(storage_capacity > 0)))

        # input (from MW to GW)
        available = x[:, :n_sources] / 1000
        consumption = x[:, n_sources] / 1000

        constraints = [
            activ >= 0,
            activ <= 1,
            # pred >= cp.multiply(activ, x[:, :n_sources] / 1000) @ units_min_prod,
            pred <= cp.multiply(activ, available),  # prod < avail
            cp.sum(pred, axis=1)
            >= consumption + cp.sum(store, axis=1),  # production >= demand + storage,
            store >= 0,
            store <= available[:, storage_capacity > 0],
        ]

        constraints += [
            pred[:, parametrize]
            >= cp.multiply(activ[:, parametrize], available[:, parametrize] / 1000)
            @ units_min_prod
        ]

        constraints += [
            pred[:, i] >= available[:, i] * min_load[i] for i in range(n_sources)
        ]

        print(storage_capacity)

        constraints += [
            cp.cumsum(store * 0.75 - pred[:, storage_capacity > 0], axis=0) >= 0,
            cp.cumsum(store * 0.75 - pred[:, storage_capacity > 0], axis=0)
            <= storage_capacity[storage_capacity > 0] / 1000,
            pred[:, storage_capacity > 0] + store
            <= cp.multiply(
                activ[:, storage_capacity > 0],
                available[:, storage_capacity > 0],
            ),
        ]

        prob = cp.Problem(
            cp.Minimize(
                cp.sum(
                    cp.abs(pred) @ c + cp.square(pred[:, parametrize]) @ linear_costs
                )  # production costs
                + cp.sum(
                    cp.pos(cp.diff(activ[:, parametrize], axis=0)) @ units_rampup_costs
                )  # activation costs
            ),
            constraints,
        )

        try:
            prob.solve(solver="ECOS", verbose=True)
            # prob.solve()
            pred = pred.value
        except:
            pred = np.zeros((x.shape[0], n_sources))
        return 1000 * pred

    def objective(x, c, min_load, storage_capacity, theta):
        n_sources = int((x.shape[1] - 1) / 2)
        pred = LinearCostModel.solve(
            x[:, : n_sources + 1], c, min_load, storage_capacity, theta
        )

        loss = (
            np.sum((pred / 1000 - x[:, n_sources + 1 :] / 1000) ** 2)
            / pred.shape[0]
            / pred.shape[1]
        )
        print(theta)
        print(loss)

        print(pred.mean(axis=0) / 1000)
        print(np.maximum(0, x[:, n_sources + 1 :]).mean(axis=0) / 1000)

        return loss

    def train(self, start, end):
        n_sources = len(self.sources)
        consumption = self.get_consumption(start, end)

        start_dt = str_to_datetime(start)
        end_dt = str_to_datetime(end)
        n_bins = int((end_dt - start_dt).total_seconds() / 3600)

        production_history = [
            source.get_production(start, end) for source in self.sources
        ]

        imports = production_history[-1][0, :]
        exports = production_history[-1][1, :]
        production_history[-1] = imports
        production_history = np.array(production_history)

        availability = np.array(
            [source.get_availability(start, end) for source in self.sources]
        )

        marginal_cost = np.array([source.marginal_cost for source in self.sources])
        min_load = np.array([source.min_load for source in self.sources])
        storage_capacity = np.array(
            [source.storage_capacity for source in self.sources]
        )

        X = np.zeros((n_bins, 2 * n_sources + 1))
        X[:, :n_sources] = availability.T
        X[:, n_sources] = consumption.T + exports
        X[:, n_sources + 1 :] = np.maximum(0, production_history.T)
        X[:, n_sources + 1 :] = np.minimum(availability.T, X[:, n_sources + 1 :])

        X[:, :3] = production_history.T[:, :3]
        X[:, n_sources + 1 : n_sources + 1 + 3] = production_history.T[:, :3]

        # from matplotlib import pyplot as plt

        # for k in range(n_sources):
        #     plt.clf()
        #     plt.plot(X[:, k + n_sources + 1] / X[:, k], lw=0.25)
        #     plt.ylim(-0.1, 1.1)
        #     plt.title(self.sources[k].__class__.__name__)
        #     plt.ylabel("Production / Available Capacity")
        #     plt.xlabel("Time (Hours)")
        #     plt.savefig(
        #         f"output/train_{self.sources[k].__class__.__name__}.png", dpi=720
        #     )

        # remove problematic data from the training set
        X = X[~np.isnan(X).any(axis=1)]

        from functools import partial

        parametrize = (marginal_cost > 0) & (storage_capacity == 0)
        n_param_sources = np.sum(parametrize)
        theta0 = np.zeros(3 * n_param_sources)

        # marginal cost increase / added GW
        theta0[:n_param_sources] = [
            np.random.uniform(0, 1)
            for i, source in enumerate(self.sources)
            if parametrize[i]
        ]

        # minimum unit load-factor
        theta0[n_param_sources : 2 * n_param_sources] = np.array(
            [
                source.min_unit_load
                for i, source in enumerate(self.sources)
                if parametrize[i]
            ]
        )

        # ramp-up costs
        theta0[2 * n_param_sources :] = np.array(
            [
                source.rampup_scale
                for i, source in enumerate(self.sources)
                if parametrize[i]
            ]
        )

        theta0 = np.load("data/theta.npy")
        theta = theta0

        res = minimize(
            partial(
                LinearCostModel.objective, X, marginal_cost, min_load, storage_capacity
            ),
            theta0,
            method="SLSQP",
            bounds=[(0, 2)] * n_param_sources
            + [(0, 1)] * n_param_sources
            + [(0, 24 * 2)] * n_param_sources,
        )

        theta = res.x
        # np.save("data/theta.npy", theta)
        theta = np.load("data/theta.npy")

        prediction = LinearCostModel.solve(
            X[:, : n_sources + 1], marginal_cost, min_load, storage_capacity, theta
        )
        return X, prediction

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
        min_load = np.array([source.min_load for source in self.sources])
        storage_capacity = np.array(
            [source.storage_capacity for source in self.sources]
        )

        theta = np.load("data/theta.npy")

        return LinearCostModel.solve(
            X, marginal_cost, min_load, storage_capacity, theta
        ).T
