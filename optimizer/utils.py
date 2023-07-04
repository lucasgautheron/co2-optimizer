from datetime import datetime
import pytz

def now():
    return datetime.now(pytz.timezone("Europe/Paris"))


def str_to_datetime(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")

def datetime_to_str(dt):
    s = datetime.strftime(dt, "%Y-%m-%dT%H:%M:%S%z")
    s = "{0}:{1}".format(s[:-2], s[-2:])
    return s

import numpy as np

def interpolate_nan(x):
    mask = np.isnan(x)
    x[mask] = np.interp(np.flatnonzero(mask), np.flatnonzero(~mask), x[~mask])
    return x