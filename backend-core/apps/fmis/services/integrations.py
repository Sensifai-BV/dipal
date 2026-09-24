import requests
from abc import ABC, abstractmethod
from typing import Tuple



class IntegrationProvider(ABC):


    @abstractmethod
    def test_connection(self, base_url: str, token: str, extra_headers: dict) -> Tuple[bool, str]:
        pass


class GenericProvider(IntegrationProvider):

    def test_connection(self, base_url: str, token: str, extra_headers: dict) -> Tuple[bool, str]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            **extra_headers
        }
        try:
            response = requests.get(base_url, headers=headers, timeout=10)
            if 200 <= response.status_code < 300:
                return True, "Connection Successful (Generic)"
            return False, f"Server returned {response.status_code}"
        except requests.RequestException as e:
            return False, str(e)


class FarmBProvider(IntegrationProvider):

    def test_connection(self, base_url: str, token: str, extra_headers: dict) -> Tuple[bool, str]:
        headers = {
            "Authorization": f"Bearer {token}",
            "X-FarmB-Version": "2.0",
            **extra_headers
        }
        clean_url = base_url.rstrip('/')
        target_url = f"{clean_url}/v1/api/ping"

        try:
            response = requests.get(target_url, headers=headers, timeout=15)
            if response.status_code == 200:
                return True, "Connected to Farm-b successfully"
            elif response.status_code == 401:
                return False, "Invalid Farm-b Token"
            return False, f"Farm-b Error: {response.status_code}"
        except requests.Timeout:
            return False, "Farm-b API Timed out"
        except requests.RequestException as e:
            return False, f"Connection Error: {str(e)}"


class LeafProvider(IntegrationProvider):

    def test_connection(self, base_url: str, token: str, extra_headers: dict) -> Tuple[bool, str]:
        headers = {
            "Authorization": f"Bearer {token}",
            **extra_headers
        }
        clean_url = base_url.rstrip('/')
        target_url = f"{clean_url}/users/me"

        try:
            response = requests.get(target_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return True, f"Connected as {data.get('name', 'Leaf User')}"
            return False, f"Leaf API Error: {response.text[:100]}"
        except requests.RequestException as e:
            return False, str(e)


class TimberleeProvider(IntegrationProvider):

    def test_connection(self, base_url: str, token: str, extra_headers: dict) -> Tuple[bool, str]:
        return GenericProvider().test_connection(base_url, token, extra_headers)



class IntegrationFactory:
    _providers = {
        'farm_b': FarmBProvider,
        'leaf': LeafProvider,
        'timberlee': TimberleeProvider,
        'generic': GenericProvider
    }

    @classmethod
    def get_provider(cls, provider_name: str) -> IntegrationProvider:
        provider_class = cls._providers.get(provider_name, GenericProvider)
        return provider_class()

    @staticmethod
    def run_test(provider_name: str, base_url: str, token: str, extra_headers: dict = None) -> Tuple[bool, str]:
        if extra_headers is None:
            extra_headers = {}

        provider = IntegrationFactory.get_provider(provider_name)
        return provider.test_connection(base_url, token, extra_headers)
