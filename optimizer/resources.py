from abc import ABC, abstractmethod

from datetime import datetime
from os import getenv
import re
import requests

import base64
import pickle

import hashlib

from .utils import str_to_datetime, now
from os.path import exists, join as opj


class Resource:
    def __init__(self, fetch_cache: bool = True, debug: bool = False):
        self.fetch_cache = fetch_cache
        self.debug = debug

    def retrieve_cache(self, resource):
        hash = hashlib.md5(resource.encode("utf-8")).hexdigest()

        cached_file = opj(".cache", f"{hash}.pickle")

        if not exists(cached_file):
            return None

        cache_expiration_file = opj(".cache", f"{hash}.expires")

        if exists(cache_expiration_file):
            expiration = str_to_datetime(open(cache_expiration_file, "r").read())
            if now() > expiration:
                return None

        with open(cached_file, "rb") as fp:
            res = pickle.load(fp)
            return res

    def write_cache(self, resource, data, cache_expiration=None):
        hash = hashlib.md5(resource.encode("utf-8")).hexdigest()

        with open(opj(".cache", f"{hash}.pickle"), "wb") as fp:
            pickle.dump(data, fp)

        if cache_expiration is not None:
            with open(opj(".cache", f"{hash}.expires"), "w") as fp:
                fp.write(cache_expiration)

    @abstractmethod
    def request(self, resource, cache_expiration=None):
        pass


class RTEAPI(Resource):
    def __init__(self, fetch_cache: bool = True, debug: bool = False):
        super().__init__(fetch_cache=fetch_cache, debug=debug)
        self.access_token = None

    def auth(self):
        self.api_client = getenv("RTE_API_CLIENT")
        self.api_secret = getenv("RTE_API_SECRET")

        credentials = f"{self.api_client}:{self.api_secret}"
        code = base64.b64encode(credentials.encode("ascii"))
        code = code.decode("ascii")

        res = requests.post(
            f"https://digital.iservices.rte-france.com/token/oauth/",
            headers={
                "Authorization": f"Basic {code}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        data = res.json()
        self.access_token = data["access_token"]

    def request(self, resource, cache_expiration=None):
        if self.fetch_cache:
            res = self.retrieve_cache(resource)

        if res is not None:
            return res

        if self.access_token is None:
            self.auth()

        res = requests.get(
            resource, headers={"Authorization": f"Bearer {self.access_token}"}
        )

        if res.status_code == 200:
            self.write_cache(resource, res, cache_expiration)

        if self.debug:
            print(f"request: {resource}")
            print(f"status: {res.status_code}")

            try:
                print(res.json())
            except:
                pass

        return res

class EMAPI:
    def __init__(self, base_url=None, fetch_cache: bool = True, debug: bool = False):
        self.fetch_cache = fetch_cache
        self.debug = debug

        if base_url is None:
            self.api_base_url = getenv("EM_API_BASE")
        else:
            self.api_base_url = base_url

        self.api_key = getenv("EM_API_PRIMARY_KEY")

    def request(self, resource, cache_expiration=None):
        if self.fetch_cache:
            res = self.retrieve_cache(resource)

        if res is not None:
            return res

        url = f"https://api-access.electricitymaps.com/{self.api_base_url}/{url}"

        res = requests.get(url, headers={"auth-token": self.api_key})

        if res.status_code == 200:
            self.write_cache(resource, res, cache_expiration)

        if self.debug:
            print(f"request: {url}")
            print(f"status: {res.status_code}")

            try:
                print(res.json())
            except:
                pass

        return res
