"""Define a client to interact with ASCOM Remote."""
import asyncio
import json
import logging
import sys
import traceback
from threading import Thread
from time import sleep
from tokenize import String
from typing import List, Optional

import pandas as pd
from tabulate import tabulate

from .config import Config
from .const import (COLOR_BLUE, COLOR_GREEN, DEVICE_TYPE_FOCUSER,
                    DEVICE_TYPE_OBSERVATORY, DEVICE_TYPE_SWITCH,
                    DEVICE_TYPE_TELESCOPE, DEVICE_TYPE_FILTERWHEEL, FUNCTIONS, ICONS)
from .errors import AlpacaError, DeviceResponseError, RequestConnectionError
from .mqttdevices import Connector as MqttConnector
from .mqtthandler import Connector as MqttHandler
from .observatory import CameraFile, Observatory

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s (%(threadName)s) [%(funcName)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("mqtt").setLevel(logging.DEBUG)


class AstroLive:
    """AstroLive Communication Client."""

    def __init__(
        self,
    ):
        configuration: Optional[Config] = None
        if configuration is None:
            configuration = Config.global_instance()
        self.config = configuration
        self.preset = "default"

        self._options = self.config.data[self.preset]["observatory"]
        self._mqtthandler = None
        self._setup()

        # Obervatory
        self.obs = None

        # Worker threads for mqtt publisher and device updates to mqtt
        self._threads = []
        self._tread_restarts = {}

        return None

    # Command callback
    def on_command(self, client, userdata, message):
        """Parsing and executing commands received via MQTT

        Args:
            message: JSON string with the command

        Expected message format is (examples):
            {
                "component": "obs.telescope",
                "command": "unpark"
            },
            {
                "component": "obs.telescope",
                "command": "slew",
                "ra": "245.809",
                "dec": "89.024"
            },
            {
                "component": "obs.telescope.focuser",
                "command": "move",
                "position": "4411"
            }
        """

        command = json.loads(message.payload.decode("utf-8"))
        component = None
        try:
            component = self.obs.component_by_absolute_sys_id(
                command.get("component", None)
            )
        except LookupError:
            _LOGGER.error(f"Can not find component sys_id={command['component']}.")
            pass

        try:
            if component.kind == DEVICE_TYPE_TELESCOPE:
                if command["command"] == "park":
                    component.park()
                    _LOGGER.info(f"Executed Telescope park")
                if command["command"] == "unpark":
                    component.unpark()
                    _LOGGER.info(f"Executed Telescope unpark")
                if command["command"] == "slew":
                    _LOGGER.info(
                        f"Slewing Telescope slew to RA: {command['ra']}, DEC: {command['dec']}"
                    )
                    component.slewtocoordinates(command["ra"], command["dec"])
                    _LOGGER.info(
                        f"Executed Telescope slew to RA: {command['ra']}, DEC: {command['dec']}"
                    )
        except RequestConnectionError:
            _LOGGER.error(f"Connection Error to {command['component']}")
            pass
        except TypeError as te:
            _LOGGER.error(f"TypeError {te}")
            pass
        except AlpacaError as ae:
            _LOGGER.error(f"AlpacaError {ae}")
            pass

        try:
            if component.kind == DEVICE_TYPE_FOCUSER:
                if command["command"] == "move":
                    component.move(command["position"])
                    _LOGGER.info(
                        f"Executed Focuser move on {command['component']} to position {command['position']}"
                    )
        except RequestConnectionError:
            _LOGGER.error(f"Connection Error to {command['component']}")
            pass

        try:
            if component.kind == DEVICE_TYPE_SWITCH:
                if command["command"] == "off":
                    component.setswitch(command["id"], False)
                    _LOGGER.info(f"Executed Switch turn off on {command['id']}")
                if command["command"] == "on":
                    component.setswitch(command["id"], True)
                    _LOGGER.info(f"Executed Switch turn on on {command['id']}")
        except RequestConnectionError:
            _LOGGER.error(f"Connection Error to {command['component']}")
            pass

        try:
            if component.kind == DEVICE_TYPE_FILTERWHEEL:
                if command["command"] == "setposition":
                    component.setposition(command["id"], command["position"])
                    _LOGGER.info(f"Executed FilterWheel set position on {command['id']} to {command['position']}")
        except RequestConnectionError:
            _LOGGER.error(f"Connection Error to {command['component']}")
            pass
        
    def _setup(self):
        """Create the MQTT connector"""

        try:
            self._mqtthandler = MqttHandler.create_connector(
                "handler", self._options, publisher=None
            )
            self._mqtthandler.on_command = self.on_command
        except KeyError:
            pass

    @staticmethod
    def esc(code) -> String:
        """Escape color codes.

        Returns:
            Escaped color code
        """

        return f"\033[{code}m"

    # Public functions
    async def link_observatory(
        self,
    ) -> None:
        """Connect to the the observatory."""

        return await self._link_observatory()

    async def start_looper(
        self,
    ) -> None:
        """Start the looper thread."""

        _LOGGER.info(f"Creating thread mqtt.looper")
        self._threads.insert(
            0,
            Thread(
                target=asyncio.run,
                args=(self._mqtthandler.looper(),),
                name="mqtt.looper",
            ),
        )

        return None

    async def start_monitoring(
        self,
    ) -> None:
        """Start the worker threads."""

        # Start the threads one after the other
        for thread in self._threads:
            if not thread.is_alive():
                try:
                    thread.start()
                    _LOGGER.info(f"Thread {thread.name} started")
                    self._tread_restarts[thread.name] = (
                        self._tread_restarts.get(thread.name, -1) + 1
                    )
                except RuntimeError as re:
                    _LOGGER.info(f"Removing dead thread {thread.name}")
                    self._threads.remove(thread)
                    pass
                except KeyboardInterrupt:
                    break
                sleep(3)

        return None

    async def health_check(self) -> None:
        """Report the healt of the worker threads."""
        _LOGGER.info(f"Health check:")
        print(
            f"{self.esc(COLOR_GREEN)}Alive: {await self._query_threads_alive()}{self.esc('0')},"
        )
        print(
            f"{self.esc(COLOR_GREEN)}Dead: {await self._query_threads_dead()}{self.esc('0')},"
        )
        print(
            f"{self.esc(COLOR_GREEN)}Restarts: {self._tread_restarts}{self.esc('0')}\n"
        )

        return None

    # Private functions
    async def _query_thread_alive(self, sys_id) -> bool:
        """Checks if the requested thread is alive.

        Args:
            SiteLatitude (float): Site latitude (degrees).

        Returns:
            True if thread is alive
        """

        for thread in self._threads:
            if thread.name == sys_id:
                if thread.is_alive():
                    _LOGGER.debug(f"Thread {thread.name} is alive")
                    return True
                else:
                    _LOGGER.debug(f"Removing dead thread {thread.name}")
                    self._threads.remove(thread)
        _LOGGER.debug(f"Thread {sys_id} not existing")

    async def _query_threads_alive(self) -> list:
        """Returns a list of threads alive.

        Returns:
            List of threads alive.
        """
        threads_alive = []
        for thread in self._threads:
            if thread.is_alive():
                threads_alive.append(thread.name)
        return threads_alive

    async def _query_threads_dead(self) -> list:
        """Returns a list of threads dead.

        Returns:
            List of threads dead.
        """

        threads_dead = []
        for thread in self._threads:
            if thread.is_alive() is not True:
                threads_dead.append(thread.name)
        return threads_dead

    async def _link_observatory(self) -> None:
        """Connect to the the observatory.

        Returns:
            List of threads dead.
        """

        if self.obs is None:
            self.obs = Observatory()
            self.obs.connect()

        # Iteration of all children of Observatory object
        children = {}
        for child in self.obs.children_tree_iter():
            if type(child) is Observatory:
                continue
            children[child.sys_id] = {
                "kind": child.kind,
                "name": "",
                "connected": False,
                "description": "",
                "driverversion": "",
            }
            if type(child) is CameraFile:
                children[child.sys_id]["connected"] = True
            else:
                try:  # connection may fail, Component may not be a Device
                    children[child.sys_id]["name"] = child.name()
                    children[child.sys_id]["connected"] = child.connected()
                    children[child.sys_id]["description"] = child.description()
                    children[child.sys_id]["driverversion"] = child.driverversion()
                except AttributeError:  # child is not a Device (so lacks those methods)
                    pass
                except (
                    RequestConnectionError,
                    DeviceResponseError,
                ):  # connection to telescope failed
                    pass
            children[child.sys_id]["comment"] = child.component_options.get(
                "comment", ""
            )
            children[child.sys_id]["friendly_name"] = child.component_options.get(
                "friendly_name", ""
            )
            children[child.sys_id]["monitor"] = child.component_options.get(
                "monitor", ""
            )
            children[child.sys_id]["update_interval"] = child.component_options.get(
                "update_interval", ""
            )

        # Printing tabulated results
        _LOGGER.info(f"Status:")
        df = pd.DataFrame(children)
        print(
            f"{self.esc(COLOR_BLUE)}"
            + f"{tabulate(df.T, headers='keys')}"
            + f"{self.esc('0')}\n"
        )

        for child in children:
            if children[child].get("kind") != DEVICE_TYPE_OBSERVATORY:
                _LOGGER.debug(f"Verifying a {children[child].get('kind')}")
                try:
                    if children[child].get("connected") == True:
                        _LOGGER.debug(f"Verifying a {children[child].get('kind')} which is {children[child].get('friendly_name')}")
                        sys_id = child
                        device_type = children[child].get("kind")
                        device_friendly_name = children[child].get("friendly_name")
                        device_functions = list(FUNCTIONS.get(device_type))
                        device_icon = ICONS.get(device_type)
                        update_interval = children[child].get("update_interval")

                        if await self._query_thread_alive(sys_id) != True:
                            try:
                                mqtt_connector = MqttConnector.create_connector(
                                    device_type,
                                    self._options,
                                    publisher=self._mqtthandler,
                                )
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                                _LOGGER.error(e)
                            except KeyError:
                                pass

                            # If device is of type switch enumerate the ports
                            if device_type == DEVICE_TYPE_SWITCH:
                                max_switch = self.obs.telescope.switch.maxswitch()
                                _LOGGER.debug(f"Verifying {children[child].get('friendly_name')} has {max_switch} switches")
                                for port_id in range(0, max_switch):
                                    device_functions.append("Switch " + str(port_id))
                                    device_functions.append(
                                        "Switch Value " + str(port_id)
                                    )

                            # Create entity configuration in mqtt
                            await mqtt_connector.create_mqtt_config(
                                sys_id,
                                device_type,
                                device_friendly_name,
                                device_functions,
                                device_icon,
                            )

                            # Create thread
                            _LOGGER.info(f"Creating thread {sys_id}")
                            self._threads.append(
                                Thread(
                                    target=asyncio.run,
                                    args=(
                                        mqtt_connector.publish_loop(
                                            sys_id,
                                            self.obs.component_by_absolute_sys_id(
                                                sys_id
                                            ),
                                            device_type,
                                            update_interval,
                                        ),
                                    ),
                                    name=sys_id,
                                )
                            )
                except AttributeError:  # c is not a Device (so lacks those methods)
                    pass
                except (
                    RequestConnectionError,
                    DeviceResponseError,
                ):  # connection to telescope failed
                    pass

        return None
