from optimizer.production import LinearCostModel
from optimizer.sources import *

from datetime import datetime, timedelta
import pytz
from optimizer.utils import str_to_datetime, datetime_to_str

import numpy as np

from matplotlib import pyplot as plt

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--start", default=None)
parser.add_argument("--end", default=None)
args = parser.parse_args()

if args.start is None:
    now = datetime.now(pytz.timezone("Europe/Paris")).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    start = datetime_to_str(now - timedelta(days=365))
    end = datetime_to_str(now)
else:
    start = f"{args.start}T00:00:00+01:00"
    end = f"{args.end}T00:00:00+01:00"

sources = [
    WindPower(),
    SolarPower(),
    NuclearPower(),
    GasPower(),
    CoalPower(),
    BiomassPower(),
    HydroPower(),
    ReservoirHydroPower(),
    ImportedPower(),
]

model = LinearCostModel(sources)
model.train(start, end)
