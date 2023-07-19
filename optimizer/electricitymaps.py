from os import getenv
import requests

import base64
import pickle

import hashlib

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

    def request(self, url):
        hash = hashlib.md5(url.encode("utf-8")).hexdigest()
        cached_file = opj(".cache", f"{hash}.pickle")

        if self.fetch_cache and exists(cached_file):
            with open(cached_file, "rb") as fp:
                res = pickle.load(fp)
                return res

        url = f"https://api-access.electricitymaps.com/{self.api_base_url}/{url}"

        res = requests.get(url, headers={"auth-token": self.api_key})

        if res.status_code == 200:
            with open(cached_file, "wb") as fp:
                pickle.dump(res, fp)

        if self.debug:
            print(f"request: {url}")
            print(f"status: {res.status_code}")

            try:
                print(res.json())
            except:
                pass

        return res
