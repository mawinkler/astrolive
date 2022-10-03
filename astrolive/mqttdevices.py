"""Handler for MQTT communication"""
import glob
import json
import logging
import os
import time
from datetime import datetime
from doctest import ELLIPSIS_MARKER
from time import sleep
from typing import Callable, Iterable, Tuple

import cv2
import numpy as np
from astropy.io import fits
from astropy.visualization import (AsinhStretch, AsymmetricPercentileInterval,
                                   LinearStretch, LogStretch, ManualInterval,
                                   MinMaxInterval, SinhStretch, SqrtStretch)
from cv2 import imencode

from .const import (CAMERA_SENSOR_TYPES, CAMERA_STATES, DEVICE_TYPE_CAMERA,
                    DEVICE_TYPE_CAMERA_FILE, IMAGE_INVERT,
                    IMAGE_MINMAX_PERCENT, IMAGE_MINMAX_VALUE,
                    IMAGE_PUBLISH_DIMENSIONS, IMAGE_STRETCH_FUNCTION,
                    MANUFACTURER)
from .errors import AlpacaError, DeviceResponseError, RequestConnectionError
from .observatory import (Camera, CameraFile, Component, Dome, FilterWheel,
                          Focuser, Observatory, Rotator, SafetyMonitor, Switch,
                          Telescope)

_LOGGER = logging.getLogger(__name__)
logging.getLogger("mqtt").setLevel(logging.DEBUG)


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

        options = args[0]
        self._publisher = kwargs["publisher"]
        if self._publisher == None:
            _LOGGER.error("MQTT Publisher not existing")
            raise RequestConnectionError("MQTT Publisher not existing")

        # Used by the update threads to hold information
        self._store = {}
        super().__init__()

    def connect(*args, **kwargs):
        """Connect"""

        pass

    def configure_components(self):
        """Configure Components"""

        pass

    """
    Create the entity configuration for Home Assistant.
    Currently we create sensor and camera entities.
    """

    async def create_mqtt_config(
        self, sys_id, device_type, device_friendly_name, device_functions, device_icon
    ):
        """Creates configuration topics within the homeassistant sensor and camera topics.

        Args:
            sys_id (string): ID of the device.
            device_type (string): Type of the device.
            device_friendly_name (string): Friendly name of the device.
            device_functions (list): List of functions provided by the device.
            device_icon (string): Icon name

        Returns:
            True if thread is alive
        """

        _LOGGER.debug(f"Creating MQTT Config for a {device_type}")
        _LOGGER.debug(f"  Friendly name {device_friendly_name}")
        _LOGGER.debug(f"  Functions {device_functions}")
        _LOGGER.debug(f"  Icon {device_icon}")

        sys_id_ = sys_id.replace(".", "_")
        device_friendly_name_cap = device_friendly_name
        device_friendly_name_low = device_friendly_name.lower().replace(" ", "_")

        for function in device_functions:
            # Generic for all devices one configuration topic for each functionality
            device_function_cap = function
            device_function_low = function.lower().replace(" ", "_")

            root_topic = (
                "homeassistant/sensor/astrolive/"
                + device_friendly_name_low
                + "_"
                + device_function_low
                + "/"
            )
            config = {
                "name": device_friendly_name_cap + " " + device_function_cap,
                "state_topic": "astrolive/" + device_type + "/" + sys_id_ + "/state",
                "unit_of_measurement": "",
                "icon": device_icon,
                "availability_topic": "astrolive/"
                + device_type
                + "/"
                + sys_id_
                + "/lwt",
                "payload_available": "ON",
                "payload_not_available": "OFF",
                "unique_id": device_type + "_" + sys_id_ + "_" + device_function_low,
                "value_template": "{{ value_json." + device_function_low + " }}",
                "device": {
                    "identifiers": [sys_id],
                    "name": device_friendly_name_cap,
                    "model": device_friendly_name_cap,
                    "manufacturer": MANUFACTURER,
                },
            }
            await self._publisher._publish_mqtt(
                root_topic + "config", json.dumps(config)
            )

        _LOGGER.debug(f"Published MQTT Config for a {device_type}")

        if (device_type == DEVICE_TYPE_CAMERA) or (
            device_type == DEVICE_TYPE_CAMERA_FILE
        ):
            # If the device is a camera or camera_file we create a camera entity configuration
            root_topic = (
                "homeassistant/camera/astrolive/" + device_friendly_name_low + "/"
            )
            config = {
                "name": device_friendly_name_cap,
                "topic": "astrolive/" + device_type + "/" + sys_id_ + "/screen",
                "availability_topic": "astrolive/"
                + device_type
                + "/"
                + sys_id_
                + "/lwt",
                "payload_available": "ON",
                "payload_not_available": "OFF",
                "unique_id": device_type
                + "_"
                + device_friendly_name_low
                + "_"
                + sys_id_,
                "device": {
                    "identifiers": [sys_id],
                    "name": device_friendly_name_cap,
                    "model": device_friendly_name_cap,
                    "manufacturer": MANUFACTURER,
                },
            }
            await self._publisher._publish_mqtt(
                root_topic + "config", json.dumps(config)
            )
            _LOGGER.debug(f"Published MQTT Camera Config for a {device_type}")

        return None

    """
    Image Manipulation
    """

    async def normalize_img(
        self,
        img_arr,
        stretch="asinh",
        minmax_percent=None,
        minmax_value=None,
        invert=False,
    ):
        """
        Apply given stretch and scaling to an image array.

        Args:
            img_arr (array): The input image array.
            stretch (str):
                Optional. default 'asinh'. The stretch to apply to the image array.
                Valid values are: asinh, sinh, sqrt, log, linear
            minmax_percent (array):
                Optional. Interval based on a keeping a specified fraction of pixels (can be asymmetric)
                when scaling the image. The format is [lower percentile, upper percentile], where pixel
                values below the lower percentile and above the upper percentile are clipped.
                Only one of minmax_percent and minmax_value shoul be specified.
            minmax_value (array):
                Optional. Interval based on user-specified pixel values when scaling the image.
                The format is [min value, max value], where pixel values below the min value and above
                the max value are clipped.
                Only one of minmax_percent and minmax_value should be specified.
            invert (bool):
                Optional, default False.  If True the image is inverted (light pixels become dark and vice versa).

        Returns
        -------
        response (array):
            The normalized image array, in the form in an integer arrays with values in the range 0-255.
        """

        # Setting up the transform with the stretch
        if stretch == "asinh":
            transform = AsinhStretch()
        elif stretch == "sinh":
            transform = SinhStretch()
        elif stretch == "sqrt":
            transform = SqrtStretch()
        elif stretch == "log":
            transform = LogStretch()
        elif stretch == "linear":
            transform = LinearStretch()

        # transform = LinearStretch(slope=0.5, intercept=0.5) + SinhStretch() + LinearStretch(slope=2, intercept=-1)
        transform += SinhStretch()

        # Adding the scaling to the transform
        if minmax_percent is not None:
            transform += AsymmetricPercentileInterval(*minmax_percent)

            if minmax_value is not None:
                _LOGGER.error(
                    f"Both minmax_percent and minmax_value are set, minmax_value will be ignored."
                )
        elif minmax_value is not None:
            transform += ManualInterval(*minmax_value)
        else:  # Default, scale the entire image range to [0,1]
            transform += MinMaxInterval()

        # Performing the transform and then putting it into the integer range 0-255
        norm_img = transform(img_arr)
        norm_img = np.multiply(256, norm_img, out=norm_img)
        norm_img = norm_img.astype(np.uint16)

        # Applying invert if requested
        if invert:
            norm_img = 256 - norm_img

        return norm_img

    async def image_resize(self, image, width=None, height=None, inter=cv2.INTER_AREA):
        """Resizes an image while keeping the aspect ratio.

        Args:
            image (array): The input image array.
            width (int):
                Optional. Width of the target image.
            height (int):
                Optional. Height of the target image.
            inter (int):
                Optional. Interpolation method.

        Returns
        -------
        response (array):
            The resized image.
        """

        # initialize the dimensions of the image to be resized and
        # grab the image size
        dim = None
        (h, w) = image.shape[:2]

        # if both the width and height are None, then return the
        # original image
        if width is None and height is None:
            return image

        # check to see if the width is None
        if width is None:
            # calculate the ratio of the height and construct the
            # dimensions
            r = height / float(h)
            dim = (int(w * r), height)

        # otherwise, the height is None
        else:
            # calculate the ratio of the width and construct the
            # dimensions
            r = width / float(w)
            dim = (width, int(h * r))

        # resize the image
        resized = cv2.resize(image, dim, interpolation=inter)

        # return the resized image
        return resized


class Telescope(MqttConnector):
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
                _LOGGER.debug(f"Execution time for {sys_id} {execution_time}s")
                # await self._publish(sys_id, device, device_type, execution_time)
                await self._publish_telescope(sys_id, device, device_type)
                sleep(interval)
            except KeyboardInterrupt:
                break
            except (RequestConnectionError, DeviceResponseError) as de:
                _LOGGER.error("Stopping thread for %s", sys_id)
                break
        _LOGGER.warning(f"Thread {sys_id} exits")
        exit(0)

    async def _publish_telescope(self, sys_id, device, device_type):
        """Publish telescope state

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
        """

        sys_id_ = sys_id.replace(".", "_")

        _LOGGER.debug(f"{sys_id}: Update")
        topic = "astrolive/" + device_type + "/" + sys_id_ + "/"
        try:
            if device.connected():
                await self._publisher._publish_mqtt(topic + "lwt", "ON")
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
                    "guiderate_right_ascension": round(
                        device.guideraterightascension(), 3
                    ),
                    "side_of_pier": device.sideofpier(),
                    "site_elevation": round(device.siteelevation(), 3),
                    "site_latitude": round(device.sitelatitude(), 3),
                    "site_longitude": round(device.sitelongitude(), 3),
                    "slewing": "on" if device.slewing() else "off",
                }
                await self._publisher._publish_mqtt(topic + "state", json.dumps(state))
            else:
                await self._publisher._publish_mqtt(topic + "lwt", "OFF")
        except (RequestConnectionError, DeviceResponseError) as de:
            await self._publisher._publish_mqtt(topic + "lwt", "OFF")
            _LOGGER.error(f"{sys_id}: Not connected")
            raise de


class Camera(MqttConnector):
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
                _LOGGER.debug(f"Execution time for {sys_id} {execution_time}s")
                # await self._publish(sys_id, device, device_type, execution_time)
                await self._publish_camera(sys_id, device, device_type)
                sleep(interval)
            except KeyboardInterrupt:
                break
            except (RequestConnectionError, DeviceResponseError) as de:
                _LOGGER.error("Stopping thread for %s", sys_id)
                break
        _LOGGER.warning(f"Thread {sys_id} exits")
        exit(0)

    async def _publish_camera(self, sys_id, device, device_type):
        """Publish camera state and image

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
        """

        sys_id_ = sys_id.replace(".", "_")

        _LOGGER.debug(f"{sys_id}: Update")
        topic = "astrolive/" + device_type + "/" + sys_id_ + "/"
        try:
            if device.connected():
                await self._publisher._publish_mqtt(topic + "lwt", "ON")
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
                        state["last_exposure_duration"] = (
                            device.lastexposureduration(),
                        )
                        state["last_exposure_start_time"] = (
                            device.lastexposurestarttime(),
                        )
                    except AlpacaError:
                        _LOGGER.warning(
                            f"{sys_id}: Call to LastExposureDuration before the first image has been taken!"
                        )
                        pass
                    except AttributeError:
                        pass
                    except (RequestConnectionError, DeviceResponseError):
                        pass

                    try:
                        state["percent_completed"] = (device.percentcompleted(),)
                    except AlpacaError:
                        _LOGGER.warning(
                            f"{sys_id}: Call to LastExposureDuration before the first image has been taken!"
                        )
                        pass
                    except AttributeError:
                        pass
                    except (RequestConnectionError, DeviceResponseError):
                        pass

                    if device.imageready():
                        _LOGGER.info(f"{sys_id}: Reading image")
                        image_data = device.imagearray()

                        _LOGGER.debug(f"{sys_id}: Normalizing image")
                        normalized = await self.normalize_img(
                            image_data,
                            IMAGE_STRETCH_FUNCTION,
                            IMAGE_MINMAX_PERCENT,
                            IMAGE_MINMAX_VALUE,
                            IMAGE_INVERT,
                        )
                        _LOGGER.debug(
                            f"{sys_id}: Image dimensions " + str(normalized.shape)
                        )

                        _LOGGER.debug(f"{sys_id}: Scaling image")
                        normalized = await self.image_resize(normalized, width=1024)

                        _LOGGER.debug(f"{sys_id}: Encoding image")
                        normalized_jpg = imencode(".jpg", normalized)[1]

                        _LOGGER.info(f"{sys_id}: Publish image")
                        image_bytearray = bytearray(normalized_jpg)
                        _LOGGER.debug(
                            f"{sys_id}: Image size {len(image_bytearray)} bytes"
                        )
                        await self._publisher._publish_mqtt(
                            topic + "screen", image_bytearray
                        )
                await self._publisher._publish_mqtt(topic + "state", json.dumps(state))
            else:
                await self._publisher._publish_mqtt(topic + "lwt", "OFF")
        except (RequestConnectionError, DeviceResponseError) as de:
            await self._publisher._publish_mqtt(topic + "lwt", "OFF")
            _LOGGER.error(f"{sys_id}: Not connected")
            raise de


class CameraFile(MqttConnector):
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
                _LOGGER.debug(f"Execution time for {sys_id} {execution_time}s")
                await self._publish_camera_file(
                    sys_id, device, device_type, execution_time
                )
                sleep(interval)
            except KeyboardInterrupt:
                break
            except (RequestConnectionError, DeviceResponseError) as de:
                _LOGGER.error("Stopping thread for %s", sys_id)
                break
        _LOGGER.warning(f"Thread {sys_id} exits")
        exit(0)

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
        _LOGGER.debug(f"{sys_id}: Update")

        latest_file = ""
        try:
            list_of_files = glob.glob(f"{monitor_directory}/**/*.fits", recursive=True)
            latest_file = max(list_of_files, key=os.path.getctime)
        except ValueError as ve:
            _LOGGER.warning(f"{sys_id}: No file found")
            return

        # TODO
        # For currently unkown reasons, the first publish doesn't replicate
        # to the broker until create_mqtt_config is run again afterwards.
        # As a workaround for now, we alwas republish for the first 3 minutes
        publish = False
        if DEVICE_TYPE_CAMERA_FILE in self._store:
            if "last_file" in self._store[DEVICE_TYPE_CAMERA_FILE]:
                if self._store[DEVICE_TYPE_CAMERA_FILE]["last_file"] == latest_file:
                    _LOGGER.debug(f"{sys_id}: Image {latest_file} already published")
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
            _LOGGER.info(f"{sys_id}: Reading image {latest_file}")
            hdr = None
            image_data = None
            try:
                # , ignore_missing_simple=True
                hdul = fits.open(latest_file)
                hdr = hdul[0].header
                image_data = fits.getdata(latest_file, ext=0)
            except OSError as ose:
                _LOGGER.error(
                    f"{sys_id}: No SIMPLE card found, this file does not appear to be a valid FITS file"
                )
                return

            topic = "astrolive/" + device_type + "/" + sys_id_ + "/"
            try:
                await self._publisher._publish_mqtt(topic + "lwt", "ON")
                state = {
                    "image_type": hdr.get("IMAGETYP", "n/a"),
                    "exposure_duration": hdr.get("EXPOSURE", "n/a"),
                    "time_of_observation": datetime.fromisoformat(
                        hdr.get("DATE-LOC", datetime.utcnow())
                    )
                    .replace(microsecond=0)
                    .isoformat(),
                    "x_axis_binning": hdr.get("XBINNING", "n/a"),
                    "y_axis_binning": hdr.get("YBINNING", "n/a"),
                    "gain": hdr.get("GAIN", "n/a"),
                    "offset": hdr.get("OFFSET", "n/a"),
                    "pixel_x_axis_size": hdr.get("XPIXSZ", "n/a"),
                    "pixel_y_axis_size": hdr.get("YPIXSZ", "n/a"),
                    "imaging_instrument": hdr.get("INSTRUME", "n/a"),
                    "ccd_temperature": hdr.get("CCD-TEMP", "n/a"),
                    "filter": hdr.get("FILTER", "n/a"),
                    "sensor_readout_mode": hdr.get("READOUTM", "n/a"),
                    "sensor_bayer_pattern": hdr.get("BAYERPAT", "n/a"),
                    "telescope": hdr.get("TELESCOP", "n/a"),
                    "focal_length": hdr.get("FOCALLEN", "n/a"),
                    "ra_of_telescope": round(hdr.get("RA", 0), 3),
                    "declination_of_telescope": round(hdr.get("DEC", 0), 3),
                    "altitude_of_telescope": round(hdr.get("CENTALT", 0), 3),
                    "azimuth_of_telescope": round(hdr.get("CENTAZ", 0), 3),
                    "object_of_interest": hdr.get("OBJECT", "n/a"),
                    "ra_of_imaged_object": hdr.get("OBJCTRA", "n/a"),
                    "declination_of_imaged_object": hdr.get("OBJCTDEC", "n/a"),
                    "rotation_of_imaged_object": hdr.get("OBJCTROT", "n/a"),
                    "software": hdr.get("SWCREATE", "n/a"),
                }
                await self._publisher._publish_mqtt(topic + "state", json.dumps(state))

                _LOGGER.debug(f"{sys_id}: Normalizing image")
                normalized = await self.normalize_img(
                    image_data,
                    IMAGE_STRETCH_FUNCTION,
                    IMAGE_MINMAX_PERCENT,
                    IMAGE_MINMAX_VALUE,
                    IMAGE_INVERT,
                )
                _LOGGER.debug(f"{sys_id}: Image dimensions " + str(normalized.shape))

                _LOGGER.debug(f"{sys_id}: Scaling image")
                normalized = await self.image_resize(normalized, width=1024)

                _LOGGER.debug(f"{sys_id}: Encoding image")
                normalized_jpg = imencode(".jpg", normalized)[1]

                _LOGGER.info(f"{sys_id}: Publish image")
                image_bytearray = bytearray(normalized_jpg)
                _LOGGER.debug(f"{sys_id}: Image size {len(image_bytearray)} bytes")
                await self._publisher._publish_mqtt(topic + "screen", image_bytearray)
            except Exception as e:
                await self._publisher._publish_mqtt(topic + "lwt", "OFF")
                _LOGGER.error(e)
                raise e
            except (RequestConnectionError, DeviceResponseError) as de:
                await self._publisher._publish_mqtt(topic + "lwt", "OFF")
                _LOGGER.error(f"{sys_id}: Not connected")
                raise de


class Focuser(MqttConnector):
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
                _LOGGER.debug(f"Execution time for {sys_id} {execution_time}s")
                await self._publish_focuser(sys_id, device, device_type)
                sleep(interval)
            except KeyboardInterrupt:
                break
            except (RequestConnectionError, DeviceResponseError) as de:
                _LOGGER.error("Stopping thread for %s", sys_id)
                break
        _LOGGER.warning(f"Thread {sys_id} exits")
        exit(0)

    async def _publish_focuser(self, sys_id, device, device_type):
        """Publish the focuser state

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
        """

        sys_id_ = sys_id.replace(".", "_")

        _LOGGER.debug(f"{sys_id}: Update")
        topic = "astrolive/" + device_type + "/" + sys_id_ + "/"
        try:
            if device.connected():
                await self._publisher._publish_mqtt(topic + "lwt", "ON")
                state = {
                    "position": device.position(),
                    "is_moving": "on" if device.ismoving() else "off",
                }
                await self._publisher._publish_mqtt(topic + "state", json.dumps(state))
            else:
                await self._publisher._publish_mqtt(topic + "lwt", "OFF")
        except (RequestConnectionError, DeviceResponseError) as de:
            await self._publisher._publish_mqtt(topic + "lwt", "OFF")
            _LOGGER.error(f"{sys_id}: Not connected")
            raise de


class Switch(MqttConnector):
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
                _LOGGER.debug(f"Execution time for {sys_id} {execution_time}s")
                await self._publish_switch(sys_id, device, device_type)
                sleep(interval)
            except KeyboardInterrupt:
                break
            except (RequestConnectionError, DeviceResponseError) as de:
                _LOGGER.error("Stopping thread for %s", sys_id)
                break
        _LOGGER.warning(f"Thread {sys_id} exits")
        exit(0)

    async def _publish_switch(self, sys_id, device, device_type):
        """Publish the device state

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
        """

        sys_id_ = sys_id.replace(".", "_")

        _LOGGER.debug(f"{sys_id}: Update")
        topic = "astrolive/" + device_type + "/" + sys_id_ + "/"
        try:
            if device.connected():
                await self._publisher._publish_mqtt(topic + "lwt", "ON")
                max_switch = device.maxswitch()
                state = {"max_switch": max_switch}
                for id in range(0, max_switch):
                    try:
                        state["switch_" + str(id)] = (
                            "on" if device.getswitch(id) else "off"
                        )
                        state["switch_value_" + str(id)] = device.getswitchvalue(id)
                    except AttributeError:  # c is not a Device (so lacks those methods)
                        pass
                    except (
                        RequestConnectionError,
                        DeviceResponseError,
                    ):  # connection to telescope failed
                        pass
                await self._publisher._publish_mqtt(topic + "state", json.dumps(state))
            else:
                await self._publisher._publish_mqtt(topic + "lwt", "OFF")
        except (RequestConnectionError, DeviceResponseError) as de:
            await self._publisher._publish_mqtt(topic + "lwt", "OFF")
            _LOGGER.error(f"{sys_id}: Not connected")
            raise de

class FilterWheel(MqttConnector):
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
                _LOGGER.debug(f"Execution time for {sys_id} {execution_time}s")
                await self._publish_filterwheel(sys_id, device, device_type)
                sleep(interval)
            except KeyboardInterrupt:
                break
            except (RequestConnectionError, DeviceResponseError) as de:
                _LOGGER.error("Stopping thread for %s", sys_id)
                break
        _LOGGER.warning(f"Thread {sys_id} exits")
        exit(0)

    async def _publish_filterwheel(self, sys_id, device, device_type):
        """Publish the filterwheel state

        Args:
            sys_id (string): ID of the device.
            device (Device): The device.
            device_type (string): Type of the device.
        """

        sys_id_ = sys_id.replace(".", "_")

        _LOGGER.debug(f"{sys_id}: Update")
        topic = "astrolive/" + device_type + "/" + sys_id_ + "/"
        try:
            if device.connected():
                await self._publisher._publish_mqtt(topic + "lwt", "ON")
                state = {
                    "position": device.position(),
                    "names": device.names(),
                    "current": device.names()[device.position()],
                }
                await self._publisher._publish_mqtt(topic + "state", json.dumps(state))
            else:
                await self._publisher._publish_mqtt(topic + "lwt", "OFF")
        except (RequestConnectionError, DeviceResponseError) as de:
            await self._publisher._publish_mqtt(topic + "lwt", "OFF")
            _LOGGER.error(f"{sys_id}: Not connected")
            raise de


_connector_classes = {
    "telescope": Telescope,
    "camera": Camera,
    "camerafile": CameraFile,
    "focuser": Focuser,
    "switch": Switch,
    "filterwheel": FilterWheel,
}
