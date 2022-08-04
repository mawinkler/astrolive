import logging
import random
from typing import Callable, Iterable, Tuple

import requests
from requests.exceptions import Timeout

from .const import REQUESTS_TIMEOUTS
from .errors import (AlpacaError, AlpacaHttp400Error, AlpacaHttp500Error,
                     AlpacaHttpError, RequestConnectionError)

log = logging.getLogger(__name__)


class Connector:
    @classmethod
    def create_connector(cls, protocol: str, *args, **kwargs) -> "Connector":
        """Factory method, crates specialized Connector instance"""

        connector = _connector_classes[protocol](*args, **kwargs)
        return connector

    def get(self, component: "Component", variable: str, **data):
        raise NotImplementedError

    def put(self, component: "Component", variable: str, **data):
        raise NotImplementedError

    def call(self, component: "Component", function: str, **data):
        raise NotImplementedError

    def subscribe(self, variables: Iterable[Tuple[str, str]], callback: Callable):
        raise NotImplementedError


class AlpacaConnector(Connector):
    def __init__(self) -> None:
        self.client_id = random.randint(0, 4294967295)
        self.session_id = 0
        log.info("Alpaca connector created, ClientId=%d", self.client_id)
        super().__init__()

    def connect(*args, **kwargs):
        pass

    def configure_components(self):
        pass

    def scan_connection(self, address: str = "http://localhost:11111/api/v1"):
        properties = [
            "name",
            "description",
            "connected",
            "driverinfo",
            "driverversion",
            "interfaceversion",
        ]
        from .observatory import _component_classes

        alpaca_devices = _component_classes.keys()
        devices = []
        for device in alpaca_devices:
            i = 0
            try:
                while True:
                    info = {"device": device, "devicenumber": i}
                    for prop in properties:
                        url = "/".join([address, device, str(i), prop])
                        r = self._get(url)
                        info[prop] = r
                    i += 1
                    devices.append(info)
            except AlpacaHttpError:
                pass
        return devices

    def get(self, component: "Component", variable: str, **data):
        """Send an HTTP GET request to an Alpaca server and check response for errors.

        Args:
            component (Component): Calling component
            variable (str): Attribute to get from server.
        """

        url = self._url(component=component, variable=variable)
        return self._get(url, **data)

    def _get(self, url, **data):
        data.update(self._base_data_for_request())
        try:
            response = requests.get(url, params=data, timeout=REQUESTS_TIMEOUTS)
            self.__check_error(response)
        except Timeout as exc:
            # log.error('Timeout has been raised.')
            raise RequestConnectionError from exc
        except IOError as exc:
            log.error(f"Connection to {url} failed")
            raise RequestConnectionError from exc

        return response.json()["Value"]

    def put(self, component: "Component", variable: str, **data):
        """Send an HTTP PUT request to an Alpaca server and check response for errors.

        Args:
            component (Component): Calling component
            variable (str): Attribute to set on server.
            **data: Data to send with request.
        """
        url = self._url(component=component, variable=variable)
        return self._put(url, **data)

    def _put(self, url, **data):
        data.update(self._base_data_for_request())
        try:
            response = requests.put(url, data=data, timeout=REQUESTS_TIMEOUTS)
            self.__check_error(response)
        except Timeout as exc:
            # log.error('Timeout has been raised.')
            raise RequestConnectionError from exc

        return response.json()

    def _base_data_for_request(self):
        self.session_id += 1
        return {"ClientID": self.client_id, "ClientTransactionID": self.session_id}

    @staticmethod
    def _url(component: "Component", variable: str):
        url = "/".join(
            [
                component.get_option_recursive("address"),
                component.component_options["kind"],
                str(component.component_options.get("device_number", 0)),
                variable,
            ]
        )
        return url

    @staticmethod
    def __check_error(response: requests.Response):
        """Check response from Alpaca server for Errors.

        Args:
            response (Response): Response from Alpaca server to check.
        """
        if response.status_code == 400:
            log.error(f"Alpaca HTTP 400 error, ({response.text}) for {response.url}")
            raise AlpacaHttp400Error(response.text)
        elif response.status_code == 500:
            log.error(f"Alpaca HTTP 500 error, ({response.text}) for {response.url}")
            raise AlpacaHttp500Error(response.text)
        j = response.json()
        if j["ErrorNumber"] != 0:
            log.error(f'Alpaca error, code={j["ErrorNumber"]}, msg={j["ErrorMessage"]}')
            raise AlpacaError(j["ErrorNumber"], j["ErrorMessage"])


_connector_classes = {"alpaca": AlpacaConnector}
