from os import getenv
import re
import requests

import base64
import pickle

import hashlib

from os.path import exists, join as opj


class RTEAPIClient:
    def __init__(self, fetch_cache: bool = True, debug: bool = True):
        self.fetch_cache = fetch_cache
        self.debug = debug
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

    def request(self, url):
        hash = hashlib.md5(url.encode("utf-8")).hexdigest()
        cached_file = opj(".cache", f"{hash}.pickle")

        if self.fetch_cache and exists(cached_file):
            with open(cached_file, "rb") as fp:
                res = pickle.load(fp)
                return res

        if self.access_token is None:
            self.auth()

        res = requests.get(
            url, headers={"Authorization": f"Bearer {self.access_token}"}
        )

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
