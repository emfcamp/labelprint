from typing import Optional
import requests


class SnipeItError(Exception):
    pass


class SnipeIt:
    def __init__(self, url: Optional[str], token: Optional[str]):
        self.url = url
        self.token = token

    def fetch(self, url: str) -> dict:
        response = requests.get(
            f"{self.url}/api/v1/{url}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "accept": "application/json",
            },
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "error":
            raise SnipeItError(data["messages"])
        return data

    def get_asset(self, asset_id: int) -> dict:
        return self.fetch(f"hardware/{asset_id}")

    def get_asset_by_tag(self, asset_tag: str) -> dict:
        return self.fetch(f"hardware/bytag/{asset_tag}")
