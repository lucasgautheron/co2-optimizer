from os import getenv
import requests

import base64


class RTEAPIClient:
    def __init__(self):
        self.api_client = getenv("RTE_API_CLIENT")
        self.api_secret = getenv("RTE_API_SECRET")

        credentials = f"{self.api_client}:{self.api_secret}"
        code = base64.b64encode(credentials.encode("ascii"))
        code = code.decode("ascii")
        print(code)

        res = requests.post(
            f"https://digital.iservices.rte-france.com/token/oauth/",
            headers={
                "Authorization": f"Basic {code}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        data = res.json()
        print(data)
        self.access_token = data["access_token"]

    def request(self, url):
        res = requests.get(
            url, headers={"Authorization": f"Bearer {self.access_token}"}
        )
        return res
