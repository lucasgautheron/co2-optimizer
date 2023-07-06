from datetime import datetime, timedelta
from itertools import product
import pytz
from optimizer.utils import str_to_datetime, datetime_to_str

import numpy as np
import pandas as pd

from matplotlib import pyplot as plt

production = pd.read_csv("output/production_history.csv")
production["start_date"] = pd.to_datetime(
    production["start_date"], format="%Y-%m-%dT%H:%M:%S%z", utc=True
)

production = production[
    (production["start_date"] >= "2023-03-01")
    & (production["start_date"] < "2024-03-01")
]

imports = pd.read_csv("output/imports_history.csv")
imports = imports[
    imports["receiver"].str.contains("France")
    | imports["sender"].str.contains("France")
]
imports["import"] = imports["receiver"].str.contains("France")
imports.loc[imports["import"] == False, "value"] = -imports.loc[
    imports["import"] == False, "value"
]
imports["start_date"] = pd.to_datetime(
    imports["start_date"], format="%Y-%m-%dT%H:%M:%S%z", utc=True
)
imports = imports[
    (imports["start_date"] >= production["start_date"].min())
    & (imports["start_date"] <= production["start_date"].max())
]
imports = imports.groupby(["start_date", "import"]).agg({"value": "sum"}).reset_index()
imports.set_index("start_date", inplace=True)

fig, ax = plt.subplots(
    nrows=1, ncols=1, sharex=True, figsize=(7.5, 7.5)  # , height_ratios=[3, 1]
)

total_positive = None
total_negative = None

imports.sort_values("import", inplace=True)
for is_import, values in imports.groupby("import"):
    positive = is_import
    bottom = total_positive if positive else total_negative

    values = (
        values.resample("1H").agg({"value": "mean"})
        # .resample("1d")
        # .agg({"value": "sum"})
    )

    if bottom is not None and len(bottom) != len(values):
        continue

    ax.bar(
        values.index,
        values["value"],
        bottom=bottom,
        label="imports" if is_import else "exports",
        width=1.0/24.0,
    )
    # ax.plot(
    #     values.index,
    #     values["value"]+(0 if bottom is None else bottom),
    #     label="imports" if is_import else "exports",
    # )
    if bottom is None:
        if positive:
            total_positive = values["value"].values
        else:
            total_negative = values["value"].values
    else:
        if positive:
            total_positive += values["value"].values
        else:
            total_negative += values["value"].values


production.set_index("start_date", inplace=True)
production.index = pd.to_datetime(production.index)
production.loc[
    (production["production_type"] == "HYDRO_PUMPED_STORAGE")
    & (production["value"] < 0),
    "production_type",
] = "HYDRO_PUMPED"

for production_type, values in production.groupby("production_type", sort=False):
    if production_type == "TOTAL":
        continue

    positive = production_type != "HYDRO_PUMPED"
    bottom = total_positive if positive else total_negative

    if production_type == "HYDRO_PUMPED":
        values = values.reindex(
            production[production["production_type"] == "TOTAL"].index
        ).fillna(0)

    values = (
        values.resample("1H").agg({"value": "mean"})
        # .resample("1d")
        # .agg({"value": "sum"})
    )

    if bottom is not None and len(bottom) != len(values):
        continue

    ax.bar(
        values.index,
        values["value"],
        bottom=bottom,
        label=production_type,
        width=1.0/24.0,
    )
    # ax.plot(
    #     values.index,
    #     values["value"]+(0 if bottom is None else bottom),
    #     label=production_type,
    # )
    if bottom is None:
        if positive:
            total_positive = values["value"].values
        else:
            total_negative = values["value"].values
    else:
        if positive:
            total_positive += values["value"].values
        else:
            total_negative += values["value"].values


fig.legend()
plt.show()
