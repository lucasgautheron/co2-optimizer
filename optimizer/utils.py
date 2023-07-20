from datetime import datetime
import pytz

import numpy as np
from scipy.interpolate import interp1d


def now():
    return datetime.now(pytz.timezone("Europe/Paris"))


def str_to_datetime(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")


def datetime_to_str(dt):
    s = datetime.strftime(dt, "%Y-%m-%dT%H:%M:%S%z")
    s = "{0}:{1}".format(s[:-2], s[-2:])
    return s


def interp(x, kind="nearest"):
    idx = np.arange(len(x))
    f = interp1d(
        idx[~np.isnan(x)],
        x[~np.isnan(x)],
        fill_value=(x[~np.isnan(x)][0], x[~np.isnan(x)][-1]),
        kind=kind,
        bounds_error=False,
    )
    return f(idx)
