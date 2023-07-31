import cvxpy as cp
import numpy as np

from .sources import (
    WindPower,
    SolarPower,
    NuclearPower,
    GasPower,
    CoalPower,
    OilPower,
    BiomassPower,
    HydroPower,
    StoredHydroPower,
    ReservoirHydroPower,
    ImportedPower,
)
from .production import MeritOrderModel


class Optimizer:
    def __init__(self, model=MeritOrderModel):
        self.model = model()

    def optimize(self, min_time, max_time, start=None, end=None, carbon_intensity=None):
        production = self.model.dispatch(start, end)

        if carbon_intensity is None:
            sources_carbon_intensity = np.array(
                [source.carbon_intensity for source in self.sources]
            )

            carbon_intensity = sources_carbon_intensity @ production
            carbon_intensity /= production.sum(axis=0)

        n_bins = len(carbon_intensity)

        x = cp.Variable(n_bins, integer=True)

        constraints = [x <= 1, x >= 0, cp.sum(x[:max_time]) >= min_time]

        prob = cp.Problem(
            cp.Minimize(cp.sum(carbon_intensity @ x)),
            constraints,
        )

        prob.solve()
        return x.value
