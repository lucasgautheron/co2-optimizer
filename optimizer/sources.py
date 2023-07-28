from abc import ABC, abstractmethod

import pandas as pd
import numpy as np

from .resources import RTEAPI
import yaml

from os.path import join as opj

from .utils import (
    interp,
    str_to_datetime,
    datetime_to_str,
    now,
)
from datetime import timedelta


# TODO:
# - add opportunity costs


class PowerSource(ABC):
    def __init__(self):
        self.read_config()

    def read_config(self):
        name = self.__class__.__name__

        with open("config/sources.yml", "r") as stream:
            data = yaml.safe_load(stream)

        self.carbon_intensity = data[name]["carbon_intensity"]
        self.marginal_cost = data[name]["marginal_cost"]

        if "installed_capacity" in data[name]:
            self.installed_capacity = data[name]["installed_capacity"]

        if "rte_production_type" in data[name]:
            self.rte_production_type = data[name]["rte_production_type"]

        if "color" in data[name]:
            self.color = data[name]["color"]

    @abstractmethod
    def get_availability(self, start, end):
        pass

    def retrieve_unavailabilities(self, production_type, start, end):
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)

        units = {}

        periods = pd.date_range(start=start_dtime, end=end_dtime, freq="1W")
        if len(periods) <= 1:
            periods = [(start_dtime, end_dtime)]
        else:
            periods = zip(periods[:-1], periods[1:])

        api = RTEAPI()

        for t0, t1 in periods:
            start_rq = datetime_to_str(t0)
            end_rq = datetime_to_str(t1)

            url = f"http://digital.iservices.rte-france.com/open_api/unavailability_additional_information/v4/generation_unavailabilities?date_type=APPLICATION_DATE&start_date={start_rq}&end_date={end_rq}&last_version=true"

            res = api.request(url)

            try:
                unvailabilities = res.json()["generation_unavailabilities"]
            except:
                print(
                    f"no unavailabilities found (start_date={start_rq}&end_date={end_rq}&last_version=true)"
                )
                return {}

            for unavailability in unvailabilities:
                if unavailability["production_type"] not in production_type:
                    continue

                if unavailability["status"] == "DISMISSED":
                    continue

                unit = unavailability["unit"]["eic_code"]

                if unit not in units:
                    units[unit] = np.zeros(n_bins)

                t_begin, t_end, values = RTEAPI.values_hist(
                    unavailability["values"],
                    start_dtime,
                    end_dtime,
                    key="unavailable_capacity",
                )

                for i in range(len(t_begin)):
                    units[unit][t_begin[i] : t_end[i]] = np.maximum(
                        units[unit][t_begin[i] : t_end[i]], values[i]
                    )

        return units

    def prediction_forecast(
        self,
        production_type: str,
        start: str = None,
        end: str = None,
        interpolation: int = -1,
    ):
        """recover RTE prediction forecast

        :param production_type: Production type (e.g.: SOLAR, WIND, ...)
        :type production_type: str
        :param start: start time, defaults to None
        :type start: str, optional
        :param end: end time, defaults to None
        :type end: str, optional
        :param interp: interpolation offset, defaults to -1
        :type interp: int, optional
        :return: prediction forecast for each hour between start and end.
        :rtype: np.ndarray
        """
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)

        start_hour = start_dtime.replace(minute=0, second=0)

        forecasts = []
        availability = np.zeros(n_bins)
        data_points = np.zeros(n_bins)

        api = RTEAPI()

        future = end_dtime > now()
        if future:
            res = api.request(
                f"http://digital.iservices.rte-france.com/open_api/generation_forecast/v2/forecasts?production_type={production_type}",
                cache_expiration=datetime_to_str(start_hour + timedelta(hours=1)),
            )
            try:
                forecasts = res.json()["forecasts"]
            except:
                print(f"no forecast found (future)")
        else:
            start_rq_dtime = (start_dtime - timedelta(days=1)).replace(
                hour=0, minute=0, second=0
            )
            end_rq_dtime = (end_dtime + timedelta(days=1)).replace(
                hour=0, minute=0, second=0
            )

            periods = pd.date_range(start=start_rq_dtime, end=end_rq_dtime, freq="2d")
            periods = list(zip(periods[:-1], periods[1:])) + list(
                zip(periods[:-1] + timedelta(days=1), periods[1:] + timedelta(days=1))
            )

            for t0, t1 in periods:
                start_rq = datetime_to_str(t0)
                end_rq = datetime_to_str(t1)

                res = api.request(
                    f"http://digital.iservices.rte-france.com/open_api/generation_forecast/v2/forecasts?production_type={production_type}&start_date={start_rq}&end_date={end_rq}",
                )
                try:
                    forecasts += res.json()["forecasts"]
                except:
                    print(
                        f"no forecast found (production_type={production_type}&start_date={start_rq}&end_date={end_rq})"
                    )

        for forecast in forecasts:
            t_begin, t_end, values = RTEAPI.values_hist(
                forecast["values"], start_dtime, end_dtime
            )

            for i in range(len(t_begin)):
                availability[t_begin[i] : t_end[i]] += values[i]
                data_points[t_begin[i] : t_end[i]] += 1

        availability /= data_points

        if isinstance(interpolation, int):
            for i in range(len(availability)):
                if np.isnan(availability[i]):
                    availability[i] = availability[i + interpolation]

        availability = interp(availability, kind="linear")
        return availability

    def get_production(self, start, end):
        start_dt = str_to_datetime(start)
        end_dt = str_to_datetime(end)

        n_bins = int((end_dt - start_dt).total_seconds() / 3600)

        production = np.zeros(n_bins)
        data_points = np.zeros(n_bins)

        periods = pd.date_range(start=start_dt, end=end_dt, freq="1W")
        if len(periods) <= 1:
            periods = [(start_dt, end_dt)]
        else:
            periods = zip(periods[:-1], periods[1:])

        api = RTEAPI()

        for t0, t1 in periods:
            start_rq = datetime_to_str(t0)
            end_rq = datetime_to_str(t1)

            res = api.request(
                f"http://digital.iservices.rte-france.com/open_api/actual_generation/v1/actual_generations_per_production_type?production_type={self.rte_production_type}&start_date={start_rq}&end_date={end_rq}",
            )

            try:
                data = res.json()["actual_generations_per_production_type"]
            except:
                print(
                    f"no production data found for production_type={self.rte_production_type}&start_date={start_rq}&end_date={end_rq}"
                )
                continue

            for row in data:
                if row["production_type"] != self.rte_production_type:
                    continue

                t_begin, t_end, values = RTEAPI.values_hist(
                    row["values"], start_dt, end_dt
                )

                for i in range(len(t_begin)):
                    production[t_begin[i] : t_end[i]] += values[i]
                    data_points[t_begin[i] : t_end[i]] += 1

        production /= data_points
        return production


class WindPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        return self.prediction_forecast("WIND", start, end, interpolation="linear")


class SolarPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        return self.prediction_forecast("SOLAR", start, end, interpolation=-24)


class NuclearPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)

        availability = [self.installed_capacity] * n_bins

        units_unavailabilities = self.retrieve_unavailabilities("NUCLEAR", start, end)

        for unit in units_unavailabilities:
            availability -= units_unavailabilities[unit]

        return availability


class GasPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)
        availability = [self.installed_capacity] * n_bins

        units_unavailabilities = self.retrieve_unavailabilities(
            "FOSSIL_GAS", start, end
        )

        for unit in units_unavailabilities:
            availability -= units_unavailabilities[unit]

        return availability


class CoalPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)
        availability = [self.installed_capacity] * n_bins

        units_unavailabilities = self.retrieve_unavailabilities(
            "FOSSIL_HARD_COAL", start, end
        )

        for unit in units_unavailabilities:
            availability -= units_unavailabilities[unit]

        return availability


class OilPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)
        availability = [self.installed_capacity] * n_bins

        units_unavailabilities = self.retrieve_unavailabilities(
            "FOSSIL_OIL", start, end
        )

        for unit in units_unavailabilities:
            availability -= units_unavailabilities[unit]

        return availability

class BiomassPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)
        availability = [self.installed_capacity] * n_bins

        units_unavailabilities = self.retrieve_unavailabilities("BIOMASS", start, end)

        for unit in units_unavailabilities:
            availability -= units_unavailabilities[unit]

        return availability


# should be forced to production at T-1
class HydroPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)

        past_start = datetime_to_str(start_dtime - timedelta(days=2))
        past_end = datetime_to_str(end_dtime - timedelta(days=2))

        availability = self.get_production(past_start, past_end)
        availability = interp(availability, kind="nearest")

        return availability


# has opportunity costs due to storage
class ReservoirHydroPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)
        availability = [self.installed_capacity] * n_bins

        units_unavailabilities = self.retrieve_unavailabilities(
            "HYDRO_WATER_RESERVOIR",
            start,
            end,
        )

        for unit in units_unavailabilities:
            availability -= units_unavailabilities[unit]

        return availability


class StoredHydroPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)
        availability = [self.installed_capacity] * n_bins

        units_unavailabilities = self.retrieve_unavailabilities(
            self.rte_production_type,
            start,
            end,
        )

        for unit in units_unavailabilities:
            availability -= units_unavailabilities[unit]

        return availability


class ImportedPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)

        availability = [self.installed_capacity] * n_bins
        return availability

    def get_production(self, start, end):
        start_dt = str_to_datetime(start)
        end_dt = str_to_datetime(end)

        n_bins = int((end_dt - start_dt).total_seconds() / 3600)

        exchanges = np.zeros((2, n_bins))
        data_points = np.zeros((2, n_bins))

        periods = pd.date_range(start=start_dt, end=end_dt, freq="2W")
        if len(periods) <= 1:
            periods = [(start_dt, end_dt)]
        else:
            periods = zip(periods[:-1], periods[1:])

        api = RTEAPI()

        for t0, t1 in periods:
            start_rq = datetime_to_str(t0)
            end_rq = datetime_to_str(t1)

            url = f"http://digital.iservices.rte-france.com/open_api/physical_flow/v1/physical_flows?start_date={start_rq}&end_date={end_rq}"

            res = api.request(url)

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

                t_begin, t_end, values = RTEAPI.values_hist(
                    row["values"], start_dt, end_dt
                )

                for i in range(len(t_begin)):
                    is_export = 0 if receiver == "France" else 1
                    exchanges[is_export, t_begin[i] : t_end[i]] += values[i]
                    data_points[is_export, t_begin[i] : t_end[i]] += 1

        return exchanges / data_points
