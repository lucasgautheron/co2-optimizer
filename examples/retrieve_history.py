from optimizer.production import History

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

hist = History()

# production = hist.retrieve_production(start, end)
# production.to_csv("output/production_history.csv")

unavailability = hist.retrieve_unavailability(start, end)
unavailability.to_csv("output/unavailability_history.csv")
