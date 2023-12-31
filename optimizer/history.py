import cvxpy as cp
import numpy as np

from .resources import RTEAPI, ElectricityMapsAPI

from .utils import str_to_datetime, datetime_to_str, now, interp
from datetime import timedelta

import pandas as pd


class History:
    def __init__(self):
        self.api = RTEAPI()

    def retrieve_consumption(self, start, end) -> pd.DataFrame:
        start_dt = str_to_datetime(start)
        end_dt = str_to_datetime(end)

        periods = pd.date_range(start=start_dt, end=end_dt, freq="1W")
        periods = zip(periods[:-1], periods[1:])

        stats = []

        for t0, t1 in periods:
            start_rq = datetime_to_str(t0)
            end_rq = datetime_to_str(t1)

            res = self.api.request(
                f"http://digital.iservices.rte-france.com/open_api/consumption/v1/short_term?start_date={start_rq}&end_date={end_rq}",
            )

            data = res.json()["short_term"]

            for row in data:
                for v in row["values"]:
                    stats.append(
                        {
                            "start_date": v["start_date"],
                            "end_date": v["end_date"],
                            "value": v["value"],
                        }
                    )

        return pd.DataFrame(stats).sort_values("start_date")

    def retrieve_production(self, start, end) -> pd.DataFrame:
        start_dt = str_to_datetime(start)
        end_dt = str_to_datetime(end)

        periods = pd.date_range(start=start_dt, end=end_dt, freq="3M")
        periods = zip(periods[:-1], periods[1:])

        stats = []

        for t0, t1 in periods:
            start_rq = datetime_to_str(t0)
            end_rq = datetime_to_str(t1)

            res = self.api.request(
                f"http://digital.iservices.rte-france.com/open_api/actual_generation/v1/actual_generations_per_production_type?start_date={start_rq}&end_date={end_rq}",
            )

            data = res.json()["actual_generations_per_production_type"]

            for row in data:
                production_type = row["production_type"]
                for v in row["values"]:
                    stats.append(
                        {
                            "production_type": production_type,
                            "start_date": v["start_date"],
                            "end_date": v["end_date"],
                            "value": v["value"],
                        }
                    )

        return pd.DataFrame(stats).sort_values(["production_type", "start_date"])

    def retrieve_unavailability(self, start, end) -> pd.DataFrame:
        start_dt = str_to_datetime(start)
        end_dt = str_to_datetime(end)
        n_bins = int((end_dt - start_dt).total_seconds() / 3600)
        bins = pd.date_range(start=start_dt, end=end_dt, freq="1h")[:-1]

        assert n_bins == len(bins)

        periods = pd.date_range(start=start_dt, end=end_dt, freq="2W")
        periods = zip(periods[:-1], periods[1:])

        units = {}
        unit_production_type = {}

        for t0, t1 in periods:
            start_rq = datetime_to_str(t0)
            end_rq = datetime_to_str(t1)

            url = f"http://digital.iservices.rte-france.com/open_api/unavailability_additional_information/v4/generation_unavailabilities?date_type=APPLICATION_DATE&start_date={start_rq}&end_date={end_rq}&last_version=true"

            api = RTEAPI()
            res = api.request(url)

            try:
                data = res.json()
            except:
                print(f"request failed: {url}")
                print(res.content)
                continue

            try:
                unvailabilities = data["generation_unavailabilities"]
            except:
                print("empty response:")
                print(data)
                continue

            for unavailability in unvailabilities:
                if unavailability["status"] == "DISMISSED":
                    continue

                unit = unavailability["unit"]["eic_code"]

                if unit not in units:
                    units[unit] = np.zeros(n_bins)

                unit_production_type[unit] = unavailability["production_type"]

                for v in unavailability["values"]:
                    unavail_start_dtime = str_to_datetime(v["start_date"])
                    unavail_end_dtime = str_to_datetime(v["end_date"])

                    t_begin = int(
                        (unavail_start_dtime - start_dt).total_seconds() / 3600
                    )
                    t_end = int((unavail_end_dtime - start_dt).total_seconds() / 3600)

                    units[unit][t_begin:t_end] = np.maximum(
                        units[unit][t_begin:t_end], v["unavailable_capacity"]
                    )

        units = pd.concat(
            [
                pd.DataFrame(
                    {
                        "unit": [unit] * n_bins,
                        "production_type": [unit_production_type[unit]] * n_bins,
                        "t": bins,
                        "unavailability": units[unit],
                    }
                )
                for unit in units
            ]
        )

        unavailability = units.groupby(["production_type", "t"]).agg(
            unavailability=("unavailability", "sum")
        )
        return unavailability

    def retrieve_imports(self, start, end) -> pd.DataFrame:
        start_dt = str_to_datetime(start)
        end_dt = str_to_datetime(end)

        periods = pd.date_range(start=start_dt, end=end_dt, freq="2W")
        periods = zip(periods[:-1], periods[1:])

        stats = []

        for t0, t1 in periods:
            start_rq = datetime_to_str(t0)
            end_rq = datetime_to_str(t1)

            url = f"http://digital.iservices.rte-france.com/open_api/physical_flow/v1/physical_flows?start_date={start_rq}&end_date={end_rq}"

            res = self.api.request(url)

            try:
                data = res.json()
            except:
                print(f"request failed: {url}")
                print(res.status_code)
                print(res.content)
                continue

            data = res.json()["physical_flows"]

            for row in data:
                sender = row["sender_country_name"]
                receiver = row["receiver_country_name"]

                for v in row["values"]:
                    stats.append(
                        {
                            "sender": sender,
                            "receiver": receiver,
                            "start_date": v["start_date"],
                            "end_date": v["end_date"],
                            "value": v["value"],
                        }
                    )

        return pd.DataFrame(stats).sort_values(["sender", "receiver", "start_date"])

    def retrieve_carbon_intensity(self):
        from datetime import datetime

        expiration = now().replace(minute=0, second=0) + timedelta(days=1)

        api = ElectricityMapsAPI()
        res = api.request(
            "carbon-intensity/history?zone=FR",
            cache_expiration=datetime_to_str(expiration),
        )

        data = res.json()

        print(data)

        history = pd.DataFrame(data["history"])

        print(history)

        start = datetime.strptime(
            history["datetime"].min()[:19], "%Y-%m-%dT%H:%M:%S"
        ).strftime("%Y-%m-%d_%H-%M")
        end = datetime.strptime(
            history["datetime"].max()[:19], "%Y-%m-%dT%H:%M:%S"
        ).strftime("%Y-%m-%d_%H-%M")

        history.to_csv(f"data/carbon-history/{start}_{end}.csv")
