"""Define a client to interact with ASCOM Remote."""
import asyncio
import json
import logging
import sys
import traceback
from threading import Thread
from time import sleep
from tokenize import String
from typing import Optional

import pandas as pd
from tabulate import tabulate

from .config import Config
from .const import (
    COLOR_BLUE,
    COLOR_GREEN,
    FUNCTIONS,
    DEVICE_TYPE_FOCUSER,
    DEVICE_TYPE_OBSERVATORY,
    DEVICE_TYPE_SWITCH,
    DEVICE_TYPE_TELESCOPE,
    DEVICE_TYPE_FILTERWHEEL,
    DEVICE_TYPE_SWITCH_ICON,
    STATE_ON,
    STATE_OFF,
    TYPE_SWITCH,
    TYPE_SENSOR,
    UNIT_OF_MEASUREMENT_NONE,
    DEVICE_CLASS_SWITCH,
    DEVICE_CLASS_NONE,
    STATE_CLASS_NONE,
)
from .errors import AlpacaError, DeviceResponseError, RequestConnectionError
from .mqttdevices import Connector as MqttConnector
from .mqtthandler import Connector as MqttHandler
from .observatory import CameraFile, Switch, Observatory

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
    def on_command(self, client, userdata, command):
        """Parsing and executing commands received via MQTT

        Args:
            message: Dictionary with the command and component information

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

        _LOGGER.debug("Command: %s.", command)
        component = None
        try:
            component = self.obs.component_by_absolute_sys_id(command.get("component", None))
        except LookupError:
            _LOGGER.error("Can not find component sys_id=%s.", command["component"])

        try:
            if component.kind == DEVICE_TYPE_TELESCOPE:
                if command["command"] == "park":
                    component.park()
                    _LOGGER.info("Executed Telescope park")
                if command["command"] == "unpark":
                    component.unpark()
                    _LOGGER.info("Executed Telescope unpark")
                if command["command"] == "slew":
                    _LOGGER.info(
                        "Slewing Telescope slew to RA: %d, DEC: %d",
                        command["ra"],
                        command["dec"],
                    )
                    component.slewtocoordinates(command["ra"], command["dec"])
                    _LOGGER.info(
                        "Executed Telescope slew to RA: %d, DEC: %d",
                        command["ra"],
                        command["dec"],
                    )
        except RequestConnectionError:
            _LOGGER.error("Connection Error to %s", command["component"])

        except TypeError as texc:
            _LOGGER.error(texc)

        except AlpacaError as aexc:
            _LOGGER.error(aexc)

        try:
            if component.kind == DEVICE_TYPE_FOCUSER:
                if command["command"] == "move":
                    component.move(command["position"])
                    _LOGGER.info(
                        "Executed Focuser move on %s to position %d",
                        command["component"],
                        command["position"],
                    )
        except RequestConnectionError:
            _LOGGER.error("Connection Error to %s", command["component"])

        try:
            if component.kind == DEVICE_TYPE_SWITCH:
                if command["command"] == STATE_OFF:
                    component.setswitch(command["id"], False)
                    _LOGGER.info("Executed Switch turn off on %s", command["id"])
                if command["command"] == STATE_ON:
                    component.setswitch(command["id"], True)
                    _LOGGER.info("Executed Switch turn on on %s", command["id"])
        except RequestConnectionError:
            _LOGGER.error("Connection Error to %s", command["component"])

        try:
            if component.kind == DEVICE_TYPE_FILTERWHEEL:
                if command["command"] == "setposition":
                    component.setposition(command["id"], command["position"])
                    _LOGGER.info(
                        "Executed FilterWheel set position on %s to %d",
                        command["id"],
                        command["position"],
                    )
        except RequestConnectionError:
            _LOGGER.error("Connection Error to %s", command["component"])

    def _setup(self):
        """Create the MQTT connector"""

        try:
            self._mqtthandler = MqttHandler.create_connector("handler", self._options, publisher=None)
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

        _LOGGER.info("Creating thread mqtt.looper")
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
                    _LOGGER.info("Thread %s started", thread.name)
                    self._tread_restarts[thread.name] = self._tread_restarts.get(thread.name, -1) + 1
                except RuntimeError:
                    _LOGGER.info("Removing dead thread %s", thread.name)
                    self._threads.remove(thread)
                except KeyboardInterrupt:
                    break

                sleep(3)

        return None

    async def health_check(self) -> None:
        """Report the healt of the worker threads."""
        _LOGGER.info("Health check:")
        print(f"{self.esc(COLOR_GREEN)}Alive: {await self._query_threads_alive()}{self.esc('0')},")
        print(f"{self.esc(COLOR_GREEN)}Dead: {await self._query_threads_dead()}{self.esc('0')},")
        print(f"{self.esc(COLOR_GREEN)}Restarts: {self._tread_restarts}{self.esc('0')}\n")

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
                    _LOGGER.debug("Thread %s is alive", thread.name)
                    return True
                _LOGGER.debug("Removing dead thread %s", thread.name)
                self._threads.remove(thread)
        _LOGGER.debug("Thread %s not existing", sys_id)

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
            if isinstance(child, Observatory):
                continue
            children[child.sys_id] = {
                "kind": child.kind,
                "name": "",
                "connected": False,
                "description": "",
                "driverversion": "",
            }
            if isinstance(child, CameraFile):
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
            if isinstance(child, Switch):
                max_switch = child.component_options.get("max_switch", 0)
                if max_switch == 0:
                    max_switch = self.obs.telescope.switch.maxswitch()
                children[child.sys_id]["max_switch"] = max_switch
            children[child.sys_id]["comment"] = child.component_options.get("comment", "")
            children[child.sys_id]["friendly_name"] = child.component_options.get("friendly_name", "")
            children[child.sys_id]["monitor"] = child.component_options.get("monitor", "")
            children[child.sys_id]["update_interval"] = child.component_options.get("update_interval", "")

        # Printing tabulated results
        _LOGGER.info("Status:")
        children_df = pd.DataFrame(children)
        print(f"{self.esc(COLOR_BLUE)}" + f"{tabulate(children_df.T, headers='keys')}" + f"{self.esc('0')}\n")

        for child in children:
            if children[child].get("kind") != DEVICE_TYPE_OBSERVATORY:
                _LOGGER.debug("Verifying a %s", children[child].get("kind"))
                try:
                    if children[child].get("connected") is True:
                        _LOGGER.debug(
                            "Verifying a %s which is %s",
                            children[child].get("kind"),
                            children[child].get("friendly_name"),
                        )
                        sys_id = child
                        device_type = children[child].get("kind")
                        device_friendly_name = children[child].get("friendly_name")
                        device_functions = list(FUNCTIONS.get(device_type))
                        update_interval = children[child].get("update_interval")

                        if await self._query_thread_alive(sys_id) is not True:
                            try:
                                mqtt_connector = MqttConnector.create_connector(
                                    device_type,
                                    self._options,
                                    publisher=self._mqtthandler,
                                )
                            except KeyError:
                                pass
                            except Exception as exc:
                                traceback.print_exc(file=sys.stdout)
                                _LOGGER.error(exc)

                            # If device is of type switch enumerate the ports
                            if device_type == DEVICE_TYPE_SWITCH:
                                max_switch = children[child].get("max_switch")
                                _LOGGER.info(
                                    "Verifying %s has %d switches",
                                    children[child].get("friendly_name"),
                                    max_switch,
                                )
                                for port_id in range(0, max_switch):
                                    device_functions.append(
                                        [
                                            TYPE_SWITCH,
                                            "Switch " + str(port_id),
                                            UNIT_OF_MEASUREMENT_NONE,
                                            DEVICE_TYPE_SWITCH_ICON,
                                            DEVICE_CLASS_SWITCH,
                                            STATE_CLASS_NONE,
                                        ]
                                    )
                                    device_functions.append(
                                        [
                                            TYPE_SENSOR,
                                            "Switch Value " + str(port_id),
                                            UNIT_OF_MEASUREMENT_NONE,
                                            DEVICE_TYPE_SWITCH_ICON,
                                            DEVICE_CLASS_NONE,
                                            STATE_CLASS_NONE,
                                        ]
                                    )

                            # Create entity configuration in mqtt
                            await mqtt_connector.create_mqtt_config(
                                sys_id,
                                device_type,
                                device_friendly_name,
                                device_functions,
                            )

                            # Create thread
                            _LOGGER.info("Creating thread %s", sys_id)
                            self._threads.append(
                                Thread(
                                    target=asyncio.run,
                                    args=(
                                        mqtt_connector.publish_loop(
                                            sys_id,
                                            self.obs.component_by_absolute_sys_id(sys_id),
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
