from abc import ABC, abstractmethod

import numpy as np

from .rte import RTEAPIClient
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

        if "color" in data[name]:
            self.color = data[name]["color"]

    @abstractmethod
    def get_availability(self, start, end):
        pass

    def retrieve_unavailabilities(self, production_type, start, end):
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)

        api = RTEAPIClient()
        res = api.request(
            f"http://digital.iservices.rte-france.com/open_api/unavailability_additional_information/v4/generation_unavailabilities?status=ACTIVE&date_type=APPLICATION_DATE&start_date={start}&end_date={end}&last_version=true",
        )

        unvailabilities = res.json()["generation_unavailabilities"]

        units = {}

        for unavailability in unvailabilities:
            if unavailability["production_type"] not in production_type:
                continue

            unit = unavailability["unit"]["eic_code"]

            if unit not in units:
                units[unit] = np.zeros(n_bins)

            for v in unavailability["values"]:
                unavail_start_dtime = str_to_datetime(v["start_date"])
                unavail_end_dtime = str_to_datetime(v["end_date"])

                t_begin = int(
                    (unavail_start_dtime - start_dtime).total_seconds() / 3600
                )
                t_end = int((unavail_end_dtime - start_dtime).total_seconds() / 3600)

                units[unit][t_begin:t_end] = np.maximum(
                    units[unit][t_begin:t_end], v["unavailable_capacity"]
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

        availability = np.zeros(n_bins)
        data_points = np.zeros(n_bins)

        api = RTEAPIClient()

        future = end_dtime > now()
        if future:
            res = api.request(
                f"http://digital.iservices.rte-france.com/open_api/generation_forecast/v2/forecasts?production_type={production_type}",
            )
        else:
            res = api.request(
                f"http://digital.iservices.rte-france.com/open_api/generation_forecast/v2/forecasts?production_type={production_type}&start_date={start_rq}&end_date={end}",
            )

        data = res.json()

        for forecast in data["forecasts"]:
            t_begin = np.array(
                [
                    (str_to_datetime(v["start_date"]) - start_dtime).total_seconds()
                    / 3600
                    for v in forecast["values"]
                ]
            ).astype(int)

            t_end = np.array(
                [
                    (str_to_datetime(v["end_date"]) - start_dtime).total_seconds()
                    / 3600
                    for v in forecast["values"]
                ]
            ).astype(int)

            values = np.array([v["value"] for v in forecast["values"]])

            for i in range(len(t_begin)):
                availability[t_begin[i] : t_end[i]] += values[i]
                data_points[t_begin[i] : t_end[i]] += 1

        availability /= data_points

        if isinstance(interpolation, int):
            for i in range(len(availability)):
                if np.isnan(availability[i]):
                    availability[i] = availability[i + interpolation]

        availability = interp(
            availability, kind="linear"
        )
        return availability


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
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)

        availability = np.zeros(n_bins)
        data_points = np.zeros(n_bins)

        past_start = datetime_to_str(
            start_dtime
            - timedelta(days=(end_dtime - start_dtime).total_seconds() / 86400)
        )
        past_end = start

        api = RTEAPIClient()
        res = api.request(
            f"http://digital.iservices.rte-france.com/open_api/actual_generation/v1/actual_generations_per_production_type?start_date={past_start}&end_date={past_end}",
        )

        data = res.json()

        for production in data["actual_generations_per_production_type"]:
            if production["production_type"] != "HYDRO_RUN_OF_RIVER_AND_POUNDAGE":
                continue

            t_begin = np.array(
                [
                    (str_to_datetime(v["start_date"]) - start_dtime).total_seconds()
                    / 3600
                    for v in production["values"]
                ]
            ).astype(int)

            t_end = np.array(
                [
                    (str_to_datetime(v["end_date"]) - start_dtime).total_seconds()
                    / 3600
                    for v in production["values"]
                ]
            ).astype(int)

            values = np.array([v["value"] for v in production["values"]])

            for i in range(len(t_begin)):
                availability[t_begin[i] : t_end[i]] += values[i]
                data_points[t_begin[i] : t_end[i]] += 1

        availability = availability / data_points
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
        return super().get_availability(start, end)


class ImportedPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        start_dtime = str_to_datetime(start)
        end_dtime = str_to_datetime(end)
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)

        availability = [self.installed_capacity] * n_bins
        return availability
