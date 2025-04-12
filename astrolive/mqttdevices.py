"""Handler for MQTT communication"""

import glob
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from time import sleep
from typing import Callable, Iterable, Tuple

import cv2
from astropy import units as u
from astropy.coordinates import SkyCoord  # High-level coordinates
from astropy.io import fits
from cv2 import imencode

from .const import (
    CAMERA_SENSOR_TYPES,
    CAMERA_STATES,
    DEVICE_CLASS_SWITCH,
    DEVICE_TYPE_CAMERA,
    DEVICE_TYPE_CAMERA_FILE,
    MANUFACTURER,
    SENSOR_DEVICE_CLASS,
    SENSOR_ICON,
    SENSOR_NAME,
    SENSOR_STATE_CLASS,
    SENSOR_TYPE,
    SENSOR_UNIT,
    STATE_OFF,
    STATE_ON,
    STRETCH_ALGORITHM,
    STRETCH_AP_ID,
    STRETCH_STF_ID,
    TYPE_TEXT,
)
from .errors import AlpacaError, DeviceResponseError, RequestConnectionError
from .image import ImageManipulation
from .observatory import (
    Camera,
    CameraFile,
    Component,
    Dome,
    FilterWheel,
    Focuser,
    Rotator,
    SafetyMonitor,
    Switch,
    Telescope,
)

_LOGGER = logging.getLogger(__name__)


class Connector:
    """Connector class"""

    @classmethod
    def create_connector(cls, protocol: str, *args, **kwargs) -> "Connector":
        """Factory method, crates specialized Connector instance"""

        connector = _connector_classes[protocol](*args, **kwargs)
        return connector

    def get(self, component: "Component", variable: str, **data):
        """Not implemented"""
        raise NotImplementedError

    def put(self, component: "Component", variable: str, **data):
        """Not implemented"""
        raise NotImplementedError

    def call(self, component: "Component", function: str, **data):
        """Not implemented"""
        raise NotImplementedError

    def subscribe(self, variables: Iterable[Tuple[str, str]], callback: Callable):
        """Not implemented"""
        raise NotImplementedError


class MqttConnector(Connector):
    """Specialized MQTT Connector"""

    def __init__(self, *args, **kwargs) -> None:
        # options = args[0]
        self._publisher = kwargs["publisher"]
        if self._publisher is None:
            _LOGGER.error("MQTT Publisher not existing")
            raise RequestConnectionError("MQTT Publisher not existing")

        # Used by the update threads to hold information
        self._store = {}
        super().__init__()

    def connect(self, *args, **kwargs):
        """Connect"""

    def configure_components(self):
        """Configure Components"""

    async def create_mqtt_config(self, sys_id, device_type, device_friendly_name, device_functions):
        """Creates configuration topics within the homeassistant sensor and camera topics.

        Args:
            sys_id (string): ID of the device.
            device_type (string): Type of the device.
            device_friendly_name (string): Friendly name of the device.
            device_functions (list): List of functions provided by the device.

        Returns:
            True if thread is alive
        """

        _LOGGER.debug("Creating MQTT Config for a %s", device_type)
        _LOGGER.debug("  Friendly name %s", device_friendly_name)
        _LOGGER.debug("  Functions %s", device_functions)

        sys_id_ = sys_id.replace(".", "_")
        device_friendly_name_cap = device_friendly_name
        device_friendly_name_low = device_friendly_name.lower().replace(" ", "_")

        for function in device_functions:
            # Generic for all devices one configuration topic for each functionality
            device_function_cap = function[SENSOR_NAME]
            device_function_low = function[SENSOR_NAME].lower().replace(" ", "_")

            root_topic = (
                "homeassistant/"
                + function[SENSOR_TYPE]
                + "/astrolive/"
                + device_friendly_name_low
                + "_"
                + device_function_low
                + "/"
            )
            config = {
                "name": device_function_cap,
                "state_topic": "astrolive/" + device_type + "/" + sys_id_ + "/state",
                "state_class": function[SENSOR_STATE_CLASS],
                "device_class": function[SENSOR_DEVICE_CLASS],
                "icon": function[SENSOR_ICON],
                "availability_topic": "astrolive/" + device_type + "/" + sys_id_ + "/lwt",
                "payload_available": "ON",
                "payload_not_available": "OFF",
                "payload_on": STATE_ON,
                "payload_off": STATE_OFF,
                "unique_id": device_type + "_" + sys_id_ + "_" + device_function_low,
                "value_template": "{{ value_json." + device_function_low + " }}",
                "device": {
                    "identifiers": [sys_id],
                    "name": "AstroLive " + device_friendly_name_cap,
                    "model": device_friendly_name_cap,
                    "manufacturer": MANUFACTURER,
                },
            }
            if function[SENSOR_UNIT] != "" and function[SENSOR_UNIT] is not None:
                config["unit_of_measurement"] = function[SENSOR_UNIT]

            if function[SENSOR_TYPE] == TYPE_TEXT:
                config["command_topic"] = ("astrolive/" + device_type + "/" + sys_id_ + "/cmd",)

            if function[SENSOR_DEVICE_CLASS] == DEVICE_CLASS_SWITCH:
                config["command_topic"] = (
                    "astrolive/" + device_type + "/" + sys_id_ + "/set" + "_" + device_function_low
                )
                # Subscribe to command topic of the switch
                await self._publisher.subsribe_mqtt(
                    "astrolive/" + device_type + "/" + sys_id_ + "/set" + "_" + device_function_low
                )

            await self._publisher.publish_mqtt(root_topic + "config", json.dumps(config), qos=0, retain=True)

        _LOGGER.debug("Published MQTT Config for a %s", device_type)

        if device_type in (DEVICE_TYPE_CAMERA, DEVICE_TYPE_CAMERA_FILE):
            # If the device is a camera or camera_file we create a camera entity configuration
            root_topic = "homeassistant/camera/astrolive/" + device_friendly_name_low + "/"
            config = {
                "name": device_friendly_name_cap,
                "topic": "astrolive/" + device_type + "/" + sys_id_ + "/screen",
                "availability_topic": "astrolive/" + device_type + "/" + sys_id_ + "/lwt",
                "payload_available": "ON",
                "payload_not_available": "OFF",
                "unique_id": device_type + "_" + device_friendly_name_low + "_" + sys_id_,
                "device": {
                    "identifiers": [sys_id],
                    "name": "AstroLive " + device_friendly_name_cap,
                    "model": device_friendly_name_cap,
                    "manufacturer": MANUFACTURER,
                },
            }
            await self._publisher.publish_mqtt(root_topic + "config", json.dumps(config), qos=0, retain=True)
            _LOGGER.debug("Published MQTT Camera Config for a %s", device_type)

        return None


class Telescope(MqttConnector):
    """MQTT Device Telescope"""

    async def publish_loop(self, sys_id, device, device_type, interval):
        """Publish the device state in an endless loop

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
            interval (int): Update interval.
        """

        start = time.time()
        while True:
            try:
                execution_time = round(time.time() - start, 1)
                _LOGGER.debug("Execution time for %s %ds", sys_id, execution_time)
                await self._publish_telescope(sys_id, device, device_type)
                sleep(interval)
            except KeyboardInterrupt:
                break
            except (RequestConnectionError, DeviceResponseError):
                _LOGGER.error("Stopping thread for %s", sys_id)
                break
        _LOGGER.warning("Thread %s exits", sys_id)
        sys.exit(0)

    async def _publish_telescope(self, sys_id, device, device_type):
        """Publish telescope state

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
        """

        sys_id_ = sys_id.replace(".", "_")

        _LOGGER.debug("%s: Update", sys_id)
        topic = "astrolive/" + device_type + "/" + sys_id_ + "/"
        try:
            if device.connected():
                await self._publisher.publish_mqtt(topic + "lwt", "ON")
                state = {
                    "at_home": "on" if device.athome() else "off",
                    "at_park": "on" if device.atpark() else "off",
                    "altitude": round(device.altitude(), 3),
                    "azimuth": round(device.azimuth(), 3),
                    "declination": round(device.declination(), 3),
                    "declination_rate": round(device.declinationrate(), 3),
                    "guiderate_declination": round(device.guideratedeclination(), 3),
                    "right_ascension": round(device.rightascension(), 3),
                    "right_ascension_rate": round(device.rightascensionrate(), 3),
                    "guiderate_right_ascension": round(device.guideraterightascension(), 3),
                    "side_of_pier": device.sideofpier(),
                    "site_elevation": round(device.siteelevation(), 3),
                    "site_latitude": round(device.sitelatitude(), 3),
                    "site_longitude": round(device.sitelongitude(), 3),
                    "slewing": "on" if device.slewing() else "off",
                }
                await self._publisher.publish_mqtt(topic + "state", json.dumps(state))
            else:
                await self._publisher.publish_mqtt(topic + "lwt", "OFF")
        except (RequestConnectionError, DeviceResponseError) as rcedre:
            await self._publisher.publish_mqtt(topic + "lwt", "OFF")
            _LOGGER.error("%s: Not connected", sys_id)
            raise rcedre


class Camera(MqttConnector):
    """MQTT Device Camera"""

    async def publish_loop(self, sys_id, device, device_type, interval):
        """Publish the device state in an endless loop

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
            interval (int): Update interval.
        """

        start = time.time()
        while True:
            try:
                execution_time = round(time.time() - start, 1)
                _LOGGER.debug("Execution time for %s %ds", sys_id, execution_time)
                await self._publish_camera(sys_id, device, device_type)
                sleep(interval)
            except KeyboardInterrupt:
                break
            except (RequestConnectionError, DeviceResponseError):
                _LOGGER.error("Stopping thread for %s", sys_id)
                break
        _LOGGER.warning("Thread %s exits", sys_id)
        sys.exit(0)

    async def _publish_camera(self, sys_id, device, device_type):
        """Publish camera state and image

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
        """

        sys_id_ = sys_id.replace(".", "_")

        _LOGGER.debug("%s: Update", sys_id)
        topic = "astrolive/" + device_type + "/" + sys_id_ + "/"
        try:
            if device.connected():
                await self._publisher.publish_mqtt(topic + "lwt", "ON")
                state = {
                    "camera_state": CAMERA_STATES[device.camerastate()],
                    "ccd_temperature": device.ccdtemperature(),
                    "image_ready": "on" if device.imageready() else "off",
                    "readout_mode": device.readoutmodes()[device.readoutmode()],
                    "sensor_type": CAMERA_SENSOR_TYPES[device.sensortype()],
                }
                if device.cangetcoolerpower():
                    state["cooler_on"] = (device.cooleron(),)
                    state["cooler_power"] = (device.coolerpower(),)

                if device.component_options.get("image", False):
                    try:
                        state["last_exposure_duration"] = (device.lastexposureduration(),)
                        state["last_exposure_start_time"] = (device.lastexposurestarttime(),)
                    except AlpacaError:
                        _LOGGER.warning(
                            "%s: Call to LastExposureDuration before the first image has been taken!",
                            sys_id,
                        )
                    except AttributeError:
                        pass
                    except (RequestConnectionError, DeviceResponseError):
                        pass

                    try:
                        state["percent_completed"] = (device.percentcompleted(),)
                    except AlpacaError:
                        _LOGGER.warning(
                            "%s: Call to LastExposureDuration before the first image has been taken!",
                            sys_id,
                        )
                    except AttributeError:
                        pass
                    except (RequestConnectionError, DeviceResponseError):
                        pass

                    if device.imageready():
                        _LOGGER.info("%s: Reading image", sys_id)
                        image_data = device.imagearray()

                        _LOGGER.debug("%s: Normalize image", sys_id)
                        image_data = await ImageManipulation.normalize_image(image_data)

                        _LOGGER.debug("%s: Stretch image", sys_id)
                        if STRETCH_ALGORITHM == STRETCH_STF_ID:
                            _LOGGER.debug("%s: STF Stretch image", sys_id)
                            image_data = await ImageManipulation.compute_stf_stretch(image_data)
                        if STRETCH_ALGORITHM == STRETCH_AP_ID:
                            _LOGGER.debug("%s: AP Stretch image", sys_id)
                            image_data = await ImageManipulation.compute_astropy_stretch(image_data)

                        _LOGGER.debug("%s: Image dimensions " + str(image_data.shape), sys_id)

                        _LOGGER.debug("%s: Scaling image", sys_id)
                        image_data = await ImageManipulation.resize_image(image_data)

                        _LOGGER.debug("%s: Encoding image", sys_id)
                        image_data = imencode(".png", image_data)[1]

                        _LOGGER.info("%s: Publish image", sys_id)
                        image_bytearray = bytearray(image_data)
                        _LOGGER.debug("%s: Image size %s bytes", sys_id, len(image_bytearray))

                        await self._publisher.publish_mqtt(topic + "screen", image_bytearray)
                await self._publisher.publish_mqtt(topic + "state", json.dumps(state))
            else:
                await self._publisher.publish_mqtt(topic + "lwt", "OFF")
        except (RequestConnectionError, DeviceResponseError) as rcedre:
            await self._publisher.publish_mqtt(topic + "lwt", "OFF")
            _LOGGER.error("%s: Not connected", sys_id)
            raise rcedre


class CameraFile(MqttConnector):
    """MQTT Device CameraFile"""

    async def publish_loop(self, sys_id, device, device_type, interval):
        """Publish the device state in an endless loop

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
            interval (int): Update interval.
        """

        start = time.time()
        while True:
            try:
                execution_time = round(time.time() - start, 1)
                _LOGGER.debug("Execution time for %s %ds", sys_id, execution_time)
                await self._publish_camera_file(sys_id, device, device_type, execution_time)
                sleep(interval)
            except KeyboardInterrupt:
                break
            except (RequestConnectionError, DeviceResponseError):
                _LOGGER.error("Stopping thread for %s", sys_id)
                break
        _LOGGER.warning("Thread %s exits", sys_id)
        sys.exit(0)

    """
    FITS Header example
    
    SIMPLE  =                    T / C# FITS                                        BITPIX  =                   16 /
    NAXIS   =                    2 / Dimensionality                                 NAXIS1  =                 6252 /
    NAXIS2  =                 4176 /                                                BZERO   =                32768 /
    EXTEND  =                    T / Extensions are permitted                       IMAGETYP= 'LIGHT'              / Type of exposure
    EXPOSURE=                300.0 / [s] Exposure duration                          EXPTIME =                300.0 / [s] Exposure duration
    DATE-LOC= '2022-02-28T23:30:33.562' / Time of observation (local)               DATE-OBS= '2022-02-28T22:30:33.562' / Time of observation (UTC)
    XBINNING=                    1 / X axis binning factor                          YBINNING=                    1 / Y axis binning factor
    GAIN    =                   26 / Sensor gain                                    OFFSET  =                    0 / Sensor gain offset
    XPIXSZ  =                 3.76 / [um] Pixel X axis size                         YPIXSZ  =                 3.76 / [um] Pixel Y axis size
    INSTRUME= 'QHY268C'            / Imaging instrument name                        SET-TEMP=                -10.0 / [degC] CCD temperature setpoint
    CCD-TEMP=                -10.0 / [degC] CCD temperature                         READOUTM= 'PhotoGraphic DSO'   / Sensor readout mode
    BAYERPAT= 'RGGB'               / Sensor Bayer pattern                           XBAYROFF=                    0 / Bayer pattern X axis offset
    YBAYROFF=                    0 / Bayer pattern Y axis offset                    USBLIMIT=                    0 / Camera-specific USB setting
    TELESCOP= 'Skywatcher 250PDS'  / Name of telescope                              FOCALLEN=               1200.0 / [mm] Focal length
    RA      =     98.1345762698888 / [deg] RA of telescope                          DEC     =             4.979375 / [deg] Declination of telescope
    CENTALT =     28.5208394003794 / [deg] Altitude of telescope                    CENTAZ  =     242.505237103705 / [deg] Azimuth of telescope
    AIRMASS =     2.08753577175519 / Airmass at frame center (Gueymard 1993)        PIERSIDE= 'East'               / Telescope pointing state
    SITEELEV=                462.0 / [m] Observation site elevation                 SITELAT =              48.XXXX / [deg] Observation site latitude
    SITELONG=              11.XXXX / [deg] Observation site longitude               OBJECT  = 'NGC 2244'           / Name of the object of interest
    OBJCTRA = '06 31 35'           / [H M S] RA of imaged object                    OBJCTDEC= '+04 58 40'          / [D M S] Declination of imaged object
    OBJCTROT=                88.11 / [deg] planned rotation of imaged object        FOCNAME = 'ZWO Focuser (1)'    / Focusing equipment name
    FOCPOS  =                10354 / [step] Focuser position                        FOCUSPOS=                10354 / [step] Focuser position
    FOCUSSZ =                  0.0 / [um] Focuser step size                         FOCTEMP =    -3.21000003814697 / [degC] Focuser temperature
    FOCUSTEM=    -3.21000003814697 / [degC] Focuser temperature                     ROWORDER= 'TOP-DOWN'           / FITS Image Orientation
    EQUINOX =               2000.0 / Equinox of celestial coordinate system         SWCREATE= 'N.I.N.A. 2.0.0.2044 ' / Software that created this file
    END 
    """

    async def _publish_camera_file(self, sys_id, device, device_type, execution_time):
        """Publish image from file with FITS header data

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
            execution_time (int): Duration of the thread is running.
        """

        sys_id_ = sys_id.replace(".", "_")
        monitor_directory = device.component_options.get("monitor", ".")
        _LOGGER.debug("%s: Update", sys_id)

        latest_file = ""
        try:
            list_of_files = glob.glob(f"{monitor_directory}/**/*.fits", recursive=True)
            latest_file = max(list_of_files, key=os.path.getctime)
        except ValueError:
            _LOGGER.warning("%s: No file found", sys_id)
            return

        # TODO:
        # For currently unkown reasons, the first publish doesn't replicate
        # to the broker until create_mqtt_config is run again afterwards.
        # As a workaround for now, we alwas republish for the first 3 minutes
        publish = False
        if DEVICE_TYPE_CAMERA_FILE in self._store:
            if "last_file" in self._store[DEVICE_TYPE_CAMERA_FILE]:
                if self._store[DEVICE_TYPE_CAMERA_FILE]["last_file"] == latest_file:
                    _LOGGER.debug("%s: Image {latest_file} already published", sys_id)
                else:
                    self._store[DEVICE_TYPE_CAMERA_FILE] = {"last_file": latest_file}
                    publish = True
            else:
                self._store[DEVICE_TYPE_CAMERA_FILE] = {"last_file": latest_file}
                publish = True
        else:
            self._store[DEVICE_TYPE_CAMERA_FILE] = {"last_file": latest_file}
            publish = True
        if execution_time < 180:
            publish = True

        if publish:
            _LOGGER.info("%s: Reading image %s", sys_id, latest_file)
            hdr = None
            image_data = None
            try:
                # , ignore_missing_simple=True
                with fits.open(latest_file) as hdul:
                    # hdul = fits.open(latest_file)
                    hdr = hdul[0].header
                    image_data = fits.getdata(latest_file, ext=0)
            except OSError:
                _LOGGER.error(
                    "%s: No SIMPLE card found, this file does not appear to be a valid FITS file",
                    sys_id,
                )
                return

            objctra_fits = hdul[0].header.get("OBJCTRA", "n/a")
            objctdec_fits = hdul[0].header.get("OBJCTDEC", "n/a")
            objct_coords = SkyCoord(objctra_fits, objctdec_fits, unit=(u.hour, u.deg))

            topic = "astrolive/" + device_type + "/" + sys_id_ + "/"
            try:
                await self._publisher.publish_mqtt(topic + "lwt", "ON")
                state = {
                    "image_type": hdr.get("IMAGETYP", "n/a"),
                    "exposure_duration": round(hdr.get("EXPOSURE", 0), 3),
                    "time_of_observation": datetime.fromisoformat(hdr.get("DATE-OBS", datetime.utcnow()))
                    .replace(microsecond=0, tzinfo=timezone.utc)
                    .isoformat(),
                    "x_axis_binning": round(hdr.get("XBINNING", 0), 0),
                    "y_axis_binning": round(hdr.get("YBINNING", 0), 0),
                    "gain": round(hdr.get("GAIN", 0), 0),
                    "offset": round(hdr.get("OFFSET", 0), 3),
                    "pixel_x_axis_size": round(hdr.get("XPIXSZ", 0), 3),
                    "pixel_y_axis_size": round(hdr.get("YPIXSZ", 0), 3),
                    "imaging_instrument": hdr.get("INSTRUME", "n/a"),
                    "ccd_temperature": round(hdr.get("CCD-TEMP", 0), 3),
                    "filter": hdr.get("FILTER", "n/a"),
                    "sensor_readout_mode": hdr.get("READOUTM", "n/a"),
                    "sensor_bayer_pattern": hdr.get("BAYERPAT", "n/a"),
                    "telescope": hdr.get("TELESCOP", "n/a"),
                    "focal_length": round(hdr.get("FOCALLEN", 0), 3),
                    "ra_of_telescope": round(hdr.get("RA", 0), 3),
                    "declination_of_telescope": round(hdr.get("DEC", 0), 3),
                    "altitude_of_telescope": round(hdr.get("CENTALT", 0), 3),
                    "azimuth_of_telescope": round(hdr.get("CENTAZ", 0), 3),
                    "object_of_interest": hdr.get("OBJECT", "n/a"),
                    "ra_of_imaged_object": objct_coords.ra.degree,
                    "declination_of_imaged_object": objct_coords.dec.degree,
                    "rotation_of_imaged_object": round(hdr.get("OBJCTROT", 0), 3),
                    "software": hdr.get("SWCREATE", "n/a"),
                }
                await self._publisher.publish_mqtt(topic + "state", json.dumps(state))

                _LOGGER.debug("%s: Normalize image", sys_id)
                image_data = await ImageManipulation.normalize_image(image_data)

                _LOGGER.debug("%s: Stretch image", sys_id)
                if STRETCH_ALGORITHM == STRETCH_STF_ID:
                    _LOGGER.debug("%s: STF Stretch image", sys_id)
                    image_data = await ImageManipulation.compute_stf_stretch(image_data)
                if STRETCH_ALGORITHM == STRETCH_AP_ID:
                    _LOGGER.debug("%s: AP Stretch image", sys_id)
                    image_data = await ImageManipulation.compute_astropy_stretch(image_data)

                _LOGGER.debug("%s: Image dimensions " + str(image_data.shape), sys_id)

                _LOGGER.debug("%s: Scaling image", sys_id)
                image_data = await ImageManipulation.resize_image(image_data)

                _LOGGER.debug("%s: Encoding image", sys_id)
                image_data = imencode(".png", image_data)[1]

                _LOGGER.info("%s: Publish image", sys_id)
                image_bytearray = bytearray(image_data)
                _LOGGER.debug("%s: Image size %s bytes", sys_id, len(image_bytearray))

                await self._publisher.publish_mqtt(topic + "screen", image_bytearray)
            except (RequestConnectionError, DeviceResponseError) as rcedre:
                await self._publisher.publish_mqtt(topic + "lwt", "OFF")
                _LOGGER.error("%s: Not connected", sys_id)
                raise rcedre
            except Exception as exc:
                await self._publisher.publish_mqtt(topic + "lwt", "OFF")
                _LOGGER.error(exc)
                raise exc


class Focuser(MqttConnector):
    """MQTT Device Focuser"""

    async def publish_loop(self, sys_id, device, device_type, interval):
        """Publish the device state in an endless loop

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
            interval (int): Update interval.
        """

        start = time.time()
        while True:
            try:
                execution_time = round(time.time() - start, 1)
                _LOGGER.debug("Execution time for %s %ds", sys_id, execution_time)
                await self._publish_focuser(sys_id, device, device_type)
                sleep(interval)
            except KeyboardInterrupt:
                break
            except (RequestConnectionError, DeviceResponseError):
                _LOGGER.error("Stopping thread for %s", sys_id)
                break
        _LOGGER.warning("Thread %s exits", sys_id)
        sys.exit(0)

    async def _publish_focuser(self, sys_id, device, device_type):
        """Publish the focuser state

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
        """

        sys_id_ = sys_id.replace(".", "_")

        _LOGGER.debug("%s: Update", sys_id)
        topic = "astrolive/" + device_type + "/" + sys_id_ + "/"
        try:
            if device.connected():
                await self._publisher.publish_mqtt(topic + "lwt", "ON")
                state = {
                    "position": device.position(),
                    "is_moving": "on" if device.ismoving() else "off",
                }
                await self._publisher.publish_mqtt(topic + "state", json.dumps(state))
            else:
                await self._publisher.publish_mqtt(topic + "lwt", "OFF")
        except (RequestConnectionError, DeviceResponseError) as rcedre:
            await self._publisher.publish_mqtt(topic + "lwt", "OFF")
            _LOGGER.error("%s: Not connected", sys_id)
            raise rcedre


class Switch(MqttConnector):
    """MQTT Device Switch"""

    async def publish_loop(self, sys_id, device, device_type, interval):
        """Publish the switch state in an endless loop

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
            interval (int): Update interval.
        """

        start = time.time()
        while True:
            try:
                execution_time = round(time.time() - start, 1)
                _LOGGER.debug("Execution time for %s %ds", sys_id, execution_time)
                await self._publish_switch(sys_id, device, device_type)
                sleep(interval)
            except KeyboardInterrupt:
                break
            except (RequestConnectionError, DeviceResponseError):
                _LOGGER.error("Stopping thread for %s", sys_id)
                break
        _LOGGER.warning("Thread %s exits", sys_id)
        sys.exit(0)

    async def _publish_switch(self, sys_id, device, device_type):
        """Publish the device state

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
        """

        sys_id_ = sys_id.replace(".", "_")

        _LOGGER.debug("%s: Update", sys_id)
        topic = "astrolive/" + device_type + "/" + sys_id_ + "/"
        try:
            if device.connected():
                await self._publisher.publish_mqtt(topic + "lwt", "ON")
                max_switch = device.maxswitch()
                state = {"max_switch": max_switch}
                for switch_id in range(0, max_switch):
                    try:
                        state["switch_" + str(switch_id)] = "on" if device.getswitch(switch_id) else "off"
                        state["switch_value_" + str(switch_id)] = device.getswitchvalue(switch_id)
                    except AttributeError:  # c is not a Device (so lacks those methods)
                        pass
                    except (
                        RequestConnectionError,
                        DeviceResponseError,
                    ):  # connection to telescope failed
                        pass
                await self._publisher.publish_mqtt(topic + "state", json.dumps(state))
            else:
                await self._publisher.publish_mqtt(topic + "lwt", "OFF")
        except (RequestConnectionError, DeviceResponseError) as rcedre:
            await self._publisher.publish_mqtt(topic + "lwt", "OFF")
            _LOGGER.error("%s: Not connected", sys_id)
            raise rcedre


class FilterWheel(MqttConnector):
    """MQTT Device FilterWheel"""

    async def publish_loop(self, sys_id, device, device_type, interval):
        """Publish the device state in an endless loop

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
            interval (int): Update interval.
        """

        start = time.time()
        while True:
            try:
                execution_time = round(time.time() - start, 1)
                _LOGGER.debug("Execution time for %s %ds", sys_id, execution_time)
                await self._publish_filterwheel(sys_id, device, device_type)
                sleep(interval)
            except KeyboardInterrupt:
                break
            except (RequestConnectionError, DeviceResponseError):
                _LOGGER.error("Stopping thread for %s", sys_id)
                break
        _LOGGER.warning("Thread %s exits", sys_id)
        sys.exit(0)

    async def _publish_filterwheel(self, sys_id, device, device_type):
        """Publish the filterwheel state

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
        """

        sys_id_ = sys_id.replace(".", "_")

        _LOGGER.debug("%s: Update", sys_id)
        topic = "astrolive/" + device_type + "/" + sys_id_ + "/"
        try:
            if device.connected() and len(device.names()) > 0:
                await self._publisher.publish_mqtt(topic + "lwt", "ON")
                state = {
                    "position": device.position(),
                    "names": device.names(),
                    "current": device.names()[device.position()],
                }
                await self._publisher.publish_mqtt(topic + "state", json.dumps(state))
            else:
                await self._publisher.publish_mqtt(topic + "lwt", "OFF")
        except (RequestConnectionError, DeviceResponseError) as rcedre:
            await self._publisher.publish_mqtt(topic + "lwt", "OFF")
            _LOGGER.error("%s: Not connected", sys_id)
            raise rcedre


class Dome(MqttConnector):
    """MQTT Device Dome"""

    async def publish_loop(self, sys_id, device, device_type, interval):
        """Publish the device state in an endless loop

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
            interval (int): Update interval.
        """

        start = time.time()
        while True:
            try:
                execution_time = round(time.time() - start, 1)
                _LOGGER.debug("Execution time for %s %ds", sys_id, execution_time)
                await self._publish_dome(sys_id, device, device_type)
                sleep(interval)
            except KeyboardInterrupt:
                break
            except (RequestConnectionError, DeviceResponseError):
                _LOGGER.error("Stopping thread for %s", sys_id)
                break
        _LOGGER.warning("Thread %s exits", sys_id)
        sys.exit(0)

    async def _publish_dome(self, sys_id, device, device_type):
        """Publish the dome state

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
        """

        sys_id_ = sys_id.replace(".", "_")

        _LOGGER.debug("%s: Update", sys_id)
        topic = "astrolive/" + device_type + "/" + sys_id_ + "/"
        try:
            if device.connected():
                await self._publisher.publish_mqtt(topic + "lwt", "ON")
                state = {
                    "altitude": device.altitude(),
                    "athome": device.athome(),
                    "atpark": device.atpark(),
                    "azimuth": device.azimuth(),
                    "shutterstatus": device.shutterstatus(),
                }
                await self._publisher.publish_mqtt(topic + "state", json.dumps(state))
            else:
                await self._publisher.publish_mqtt(topic + "lwt", "OFF")
        except (RequestConnectionError, DeviceResponseError) as rcedre:
            await self._publisher.publish_mqtt(topic + "lwt", "OFF")
            _LOGGER.error("%s: Not connected", sys_id)
            raise rcedre


class Rotator(MqttConnector):
    """MQTT Device Rotator"""

    async def publish_loop(self, sys_id, device, device_type, interval):
        """Publish the device state in an endless loop

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
            interval (int): Update interval.
        """

        start = time.time()
        while True:
            try:
                execution_time = round(time.time() - start, 1)
                _LOGGER.debug("Execution time for %s %ds", sys_id, execution_time)
                await self._publish_rotator(sys_id, device, device_type)
                sleep(interval)
            except KeyboardInterrupt:
                break
            except (RequestConnectionError, DeviceResponseError):
                _LOGGER.error("Stopping thread for %s", sys_id)
                break
        _LOGGER.warning("Thread %s exits", sys_id)
        sys.exit(0)

    async def _publish_rotator(self, sys_id, device, device_type):
        """Publish the rotator state

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
        """

        sys_id_ = sys_id.replace(".", "_")

        _LOGGER.debug("%s: Update", sys_id)
        topic = "astrolive/" + device_type + "/" + sys_id_ + "/"
        try:
            if device.connected():
                await self._publisher.publish_mqtt(topic + "lwt", "ON")
                state = {
                    "mechanicalposition": device.mechanicalposition(),
                    "position": device.position(),
                }
                await self._publisher.publish_mqtt(topic + "state", json.dumps(state))
            else:
                await self._publisher.publish_mqtt(topic + "lwt", "OFF")
        except (RequestConnectionError, DeviceResponseError) as rcedre:
            await self._publisher.publish_mqtt(topic + "lwt", "OFF")
            _LOGGER.error("%s: Not connected", sys_id)
            raise rcedre


class SafetyMonitor(MqttConnector):
    """MQTT Device SafetyMonitor"""

    async def publish_loop(self, sys_id, device, device_type, interval):
        """Publish the device state in an endless loop

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
            interval (int): Update interval.
        """

        start = time.time()
        while True:
            try:
                execution_time = round(time.time() - start, 1)
                _LOGGER.debug("Execution time for %s %ds", sys_id, execution_time)
                await self._publish_safetymonitor(sys_id, device, device_type)
                sleep(interval)
            except KeyboardInterrupt:
                break
            except (RequestConnectionError, DeviceResponseError):
                _LOGGER.error("Stopping thread for %s", sys_id)
                break
        _LOGGER.warning("Thread %s exits", sys_id)
        sys.exit(0)

    async def _publish_safetymonitor(self, sys_id, device, device_type):
        """Publish the safetymonitor state

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
        """

        sys_id_ = sys_id.replace(".", "_")

        _LOGGER.debug("%s: Update", sys_id)
        topic = "astrolive/" + device_type + "/" + sys_id_ + "/"
        try:
            if device.connected():
                await self._publisher.publish_mqtt(topic + "lwt", "ON")
                state = {
                    "issafe": device.issafe(),
                }
                await self._publisher.publish_mqtt(topic + "state", json.dumps(state))
            else:
                await self._publisher.publish_mqtt(topic + "lwt", "OFF")
        except (RequestConnectionError, DeviceResponseError) as rcedre:
            await self._publisher.publish_mqtt(topic + "lwt", "OFF")
            _LOGGER.error("%s: Not connected", sys_id)
            raise rcedre


_connector_classes = {
    "telescope": Telescope,
    "camera": Camera,
    "camerafile": CameraFile,
    "focuser": Focuser,
    "switch": Switch,
    "filterwheel": FilterWheel,
    "dome": Dome,
    "safetymonitor": SafetyMonitor,
    "rotator": Rotator,
}
