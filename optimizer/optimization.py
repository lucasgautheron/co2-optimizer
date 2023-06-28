import cvxpy as cp
import numpy as np

from .sources import (
    WindPower,
    SolarPower,
    NuclearPower,
    GasPower,
    CoalPower,
    HydroPower,
    StoredHydroPower,
    ReservoirHydroPower,
    ImportedPower,
)
from .production import ProductionPrediction


class Optimizer:
    def __init__(self):
        self.sources = [
            WindPower(),
            SolarPower(),
            NuclearPower(),
            GasPower(),
            CoalPower(),
            HydroPower(),
            ReservoirHydroPower(),
            ImportedPower(),
        ]

        self.prediction = ProductionPrediction(self.sources)

    def optimize(self, min_time, max_time, start=None, end=None):
        production = self.prediction.dispatch(start, end)

        carbon_intensity = np.array(
            [source.carbon_intensity for source in self.sources]
        )

        ci = carbon_intensity @ production
        ci /= production.sum(axis=0)

        n_bins = len(ci)

        x = cp.Variable(n_bins, integer=True)

        constraints = [x <= 1, x >= 0, cp.sum(x[:max_time]) >= min_time]

        prob = cp.Problem(
            cp.Minimize(cp.sum(ci @ x)),
            constraints,
        )

        prob.solve()
        return x.value
