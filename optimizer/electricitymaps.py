from os import getenv
import requests

import base64
import pickle

import hashlib

from .utils import str_to_datetime, now

from os.path import exists, join as opj


class EMAPIClient:
    def __init__(self, base_url=None, fetch_cache: bool = True, debug: bool = False):
        self.fetch_cache = fetch_cache
        self.debug = debug

        if base_url is None:
            self.api_base_url = getenv("EM_API_BASE")
        else:
            self.api_base_url = base_url

        self.api_key = getenv("EM_API_PRIMARY_KEY")

    def retrieve_cache(self, hash):
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

    def request(self, url, cache_expiration=None):
        hash = hashlib.md5(url.encode("utf-8")).hexdigest()

        if self.fetch_cache:
            res = self.retrieve_cache(hash)

        if res is not None:
            return res

        url = f"https://api-access.electricitymaps.com/{self.api_base_url}/{url}"

        res = requests.get(url, headers={"auth-token": self.api_key})

        if res.status_code == 200:
            with open(opj(".cache", f"{hash}.pickle"), "wb") as fp:
                pickle.dump(res, fp)

            if cache_expiration is not None:
                with open(opj(".cache", f"{hash}.expires"), "w") as fp:
                    fp.write(cache_expiration)

        if self.debug:
            print(f"request: {url}")
            print(f"status: {res.status_code}")

            try:
                print(res.json())
            except:
                pass

        return res