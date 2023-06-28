from abc import ABC, abstractmethod


import numpy as np

from .rte import RTEAPIClient
import yaml

from os.path import join as opj

from datetime import datetime


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
        start_dtime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
        end_dtime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")
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
                unavail_start_dtime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
                unavail_end_dtime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")

                t_begin = int(
                    (unavail_start_dtime - start_dtime).total_seconds() / 3600
                )
                t_end = int((unavail_end_dtime - start_dtime).total_seconds() / 3600)

                units[unit][t_begin:t_end] = np.maximum(
                    units[unit][t_begin:t_end], v["unavailable_capacity"]
                )

        return units

    def prediction_forecast(self, production_type, start, end):
        start_dtime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
        end_dtime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)

        availability = np.zeros(n_bins)
        data_points = np.zeros(n_bins)

        api = RTEAPIClient()
        res = api.request(
            f"http://digital.iservices.rte-france.com/open_api/generation_forecast/v2/forecasts?production_type={production_type}&start_date={start}&end_date={end}",
        )

        data = res.json()

        for forecast in data["forecasts"]:
            t_begin = np.array(
                [
                    (
                        datetime.strptime(v["start_date"], "%Y-%m-%dT%H:%M:%S%z")
                        - start_dtime
                    ).total_seconds()
                    / 3600
                    for v in forecast["values"]
                ]
            ).astype(int)

            t_end = np.array(
                [
                    (
                        datetime.strptime(v["end_date"], "%Y-%m-%dT%H:%M:%S%z")
                        - start_dtime
                    ).total_seconds()
                    / 3600
                    for v in forecast["values"]
                ]
            ).astype(int)

            values = np.array([v["value"] for v in forecast["values"]])

            for i in range(len(t_begin)):
                availability[t_begin[i] : t_end[i]] += values[i]
                data_points[t_begin[i] : t_end[i]] += 1

        availability /= data_points
        return availability


class WindPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        return self.prediction_forecast("WIND", start, end)


class SolarPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        return self.prediction_forecast("SOLAR", start, end)


class NuclearPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        start_dtime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
        end_dtime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")
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
        start_dtime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
        end_dtime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")
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
        start_dtime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
        end_dtime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)
        availability = [self.installed_capacity] * n_bins

        units_unavailabilities = self.retrieve_unavailabilities(
            "FOSSIL_HARD_COAL", start, end
        )

        for unit in units_unavailabilities:
            availability -= units_unavailabilities[unit]

        return availability


class HydroPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        start_dtime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
        end_dtime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)
        availability = [self.installed_capacity] * n_bins

        units_unavailabilities = self.retrieve_unavailabilities(
            "HYDRO_RUN_OF_RIVER_AND_POUNDAGE",
            start,
            end,
        )

        for unit in units_unavailabilities:
            availability -= units_unavailabilities[unit]

        return availability


# has opportunity costs due to storage
class ReservoirHydroPower(PowerSource):
    def __init__(self):
        super().__init__()

    def get_availability(self, start, end):
        start_dtime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
        end_dtime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")
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
        start_dtime = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
        end_dtime = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")
        n_bins = int((end_dtime - start_dtime).total_seconds() / 3600)

        availability = [self.installed_capacity] * n_bins
        return availability
