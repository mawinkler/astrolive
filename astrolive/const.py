"""Constant Definitions for AstroLive."""

MANUFACTURER = "AstroLive 0.5"
API_ENDPOINT = "http://localhost:11111/api/v1"
CLIENT_ID = 1

REQUESTS_TIMEOUTS = (2, 30)

COLOR_BLACK = "1;30"
COLOR_RED = "1;31"
COLOR_GREEN = "1;32"
COLOR_BROWN = "1;33"
COLOR_BLUE = "1;34"
COLOR_PURPLE = "1;35"
COLOR_CYAN = "1;36"
COLOR_STD = "0"


# #########################################################################
# Image Manipulation
# #########################################################################
CAMERA_SAMPLE_RESOLUTION = 16
IMAGE_PUBLISH_DIMENSIONS = (1920, 1080)

# Select Stretching Algorithm
# Valid Options: STF, AP
STRETCH_ALGORITHM = "STF"

# PixInsight STF Stretch
STRETCH_STF_ID = "STF"
STRETCH_STF_TARGET_BACKGROUND = 0.25
STRETCH_STF_CLIPPING_POINT = -2.8

# AstroPy Stretch
STRETCH_AP_ID = "AP"
STRETCH_AP_STRETCH_FUNCTION = "asinh"
STRETCH_AP_MINMAX_PERCENT = [15, 95]  # [0.5, 95]
STRETCH_AP_MINMAX_VALUE = None

# #########################################################################
# Devices
# #########################################################################
DEVICE_TYPE_OBSERVATORY = "observatory"
DEVICE_TYPE_TELESCOPE = "telescope"
DEVICE_TYPE_CAMERA = "camera"
DEVICE_TYPE_CAMERA_FILE = "camerafile"
DEVICE_TYPE_SWITCH = "switch"
DEVICE_TYPE_FOCUSER = "focuser"
DEVICE_TYPE_FILTERWHEEL = "filterwheel"
DEVICE_TYPE_DOME = "dome"
DEVICE_TYPE_ROTATOR = "rotator"
DEVICE_TYPE_SAFETYMONITOR = "safetymonitor"

DEVICE_TYPE_TELESCOPE_ICON = "mdi:telescope"
DEVICE_TYPE_CAMERA_ICON = "mdi:camera"
DEVICE_TYPE_CAMERA_FILE_ICON = "mdi:camera"
DEVICE_TYPE_FOCUSER_ICON = "mdi:focus-auto"
DEVICE_TYPE_SWITCH_ICON = "mdi:hubspot"
DEVICE_TYPE_FILTERWHEEL_ICON = "mdi:image-filter-black-white"
DEVICE_TYPE_DOME_ICON = "mdi:greenhouse"
DEVICE_TYPE_ROTATOR_ICON = "mdi:rotate-360"
DEVICE_TYPE_SAFETYMONITOR_ICON = "mdi:seatbelt"

# #########################################################################
# Entities
# #########################################################################
SENSOR_TYPE = 0
SENSOR_NAME = 1
SENSOR_UNIT = 2
SENSOR_ICON = 3
SENSOR_DEVICE_CLASS = 4
SENSOR_STATE_CLASS = 5

STATE_ON = "on"
STATE_OFF = "off"

TYPE_BINARY_SENSOR = "binary_sensor"
TYPE_SENSOR = "sensor"
TYPE_SWITCH = "switch"
TYPE_TEXT = "text"

UNIT_OF_MEASUREMENT_NONE = None
UNIT_OF_MEASUREMENT_ARCSEC_PER_SEC = '"/s'
UNIT_OF_MEASUREMENT_DEGREE = "°"
UNIT_OF_MEASUREMENT_DEGREE_PER_SEC = "°/s"
UNIT_OF_MEASUREMENT_METER = "m"
UNIT_OF_MEASUREMENT_MICROMETER = "µm"
UNIT_OF_MEASUREMENT_MILLIMETER = "mm"
UNIT_OF_MEASUREMENT_PERCENTAGE = "%"
UNIT_OF_MEASUREMENT_SECONDS = "s"
UNIT_OF_MEASUREMENT_TEMP_CELSIUS = "°C"

DEVICE_CLASS_NONE = None
DEVICE_CLASS_DISTANCE = "distance"
DEVICE_CLASS_DURATION = "duration"
DEVICE_CLASS_POWER = "power"
DEVICE_CLASS_SWITCH = "switch"
DEVICE_CLASS_TEMPERATURE = "temperature"
DEVICE_CLASS_TIMESTAMP = "timestamp"

STATE_CLASS_NONE = None
STATE_CLASS_MEASUREMENT = "measurement"

FUNCTIONS = {
    DEVICE_TYPE_TELESCOPE: (
        [
            TYPE_BINARY_SENSOR,
            "At home",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_TELESCOPE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_BINARY_SENSOR,
            "At park",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_TELESCOPE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Altitude",
            UNIT_OF_MEASUREMENT_DEGREE,
            DEVICE_TYPE_TELESCOPE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Azimuth",
            UNIT_OF_MEASUREMENT_DEGREE,
            DEVICE_TYPE_TELESCOPE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Declination",
            UNIT_OF_MEASUREMENT_DEGREE,
            DEVICE_TYPE_TELESCOPE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Declination rate",
            UNIT_OF_MEASUREMENT_ARCSEC_PER_SEC,
            DEVICE_TYPE_TELESCOPE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Guiderate declination",
            UNIT_OF_MEASUREMENT_DEGREE_PER_SEC,
            DEVICE_TYPE_TELESCOPE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Right ascension",
            UNIT_OF_MEASUREMENT_DEGREE,
            DEVICE_TYPE_TELESCOPE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Right ascension rate",
            UNIT_OF_MEASUREMENT_ARCSEC_PER_SEC,
            DEVICE_TYPE_TELESCOPE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Guiderate right ascension",
            UNIT_OF_MEASUREMENT_DEGREE_PER_SEC,
            DEVICE_TYPE_TELESCOPE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Side of pier",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_TELESCOPE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Site elevation",
            UNIT_OF_MEASUREMENT_METER,
            DEVICE_TYPE_TELESCOPE_ICON,
            DEVICE_CLASS_DISTANCE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Site Latitude",
            UNIT_OF_MEASUREMENT_DEGREE,
            DEVICE_TYPE_TELESCOPE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Site Longitude",
            UNIT_OF_MEASUREMENT_DEGREE,
            DEVICE_TYPE_TELESCOPE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_BINARY_SENSOR,
            "Slewing",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_TELESCOPE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
    ),
    DEVICE_TYPE_CAMERA: (
        [
            TYPE_SENSOR,
            "Camera state",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "CCD temperature",
            UNIT_OF_MEASUREMENT_TEMP_CELSIUS,
            DEVICE_TYPE_CAMERA_ICON,
            DEVICE_CLASS_TEMPERATURE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_BINARY_SENSOR,
            "Cooler on",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Cooler Power",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Image array",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_BINARY_SENSOR,
            "Image ready",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Last exposure duration",
            UNIT_OF_MEASUREMENT_SECONDS,
            DEVICE_TYPE_CAMERA_ICON,
            DEVICE_CLASS_DURATION,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Last exposure start time",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_ICON,
            DEVICE_CLASS_TIMESTAMP,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Percent completed",
            UNIT_OF_MEASUREMENT_PERCENTAGE,
            DEVICE_TYPE_CAMERA_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Readout mode",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Readout modes",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Sensor type",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
    ),
    DEVICE_TYPE_CAMERA_FILE: (
        [
            TYPE_SENSOR,
            "Image Type",  # IMAGETYP
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Exposure Duration",  # EXPOSURE
            UNIT_OF_MEASUREMENT_SECONDS,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_DURATION,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Time of observation",  # DATE-OBS
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_TIMESTAMP,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "X axis binning",  # XBINNING
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Y axis binning",  # YBINNING
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Gain",  # GAIN
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Offset",  # OFFSET
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Pixel X axis size",  # XPIXSZ
            UNIT_OF_MEASUREMENT_MICROMETER,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Pixel Y axis size",  # YPIXSZ
            UNIT_OF_MEASUREMENT_MICROMETER,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Imaging instrument",  # INSTRUME
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "CCD temperature",  # CCD-TEMP
            UNIT_OF_MEASUREMENT_TEMP_CELSIUS,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_TEMPERATURE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Filter",  # FILTER
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Sensor readout mode",  # READOUTM
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Sensor Bayer pattern",  # BAYERPAT
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Telescope",  # TELESCOP
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Focal length",  # FOCALLEN
            UNIT_OF_MEASUREMENT_MILLIMETER,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_DISTANCE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "RA of telescope",  # RA
            UNIT_OF_MEASUREMENT_DEGREE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Declination of telescope",  # DEC
            UNIT_OF_MEASUREMENT_DEGREE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Altitude of telescope",  # CENTALT
            UNIT_OF_MEASUREMENT_DEGREE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Azimuth of telescope",  # CENTAZ
            UNIT_OF_MEASUREMENT_DEGREE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Object of interest",  # OBJECT
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "RA of imaged object",  # OBJCTRA
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Declination of imaged object",  # OBJCTDEC
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Rotation of imaged object",  # OBJCTROT
            UNIT_OF_MEASUREMENT_DEGREE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Software",  # SWCREATE
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_CAMERA_FILE_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
    ),
    DEVICE_TYPE_FOCUSER: (
        [
            TYPE_SENSOR,
            "Position",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_FOCUSER_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_BINARY_SENSOR,
            "Is moving",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_FOCUSER_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
    ),
    DEVICE_TYPE_SWITCH: (
        [
            TYPE_SENSOR,
            "Max switch",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_SWITCH_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        # 0  QHC268c (Power)
        # 1  EQ6-R (Power)
        # 2  GEM45 (Power)
        # 3  Flat Mask (Power)
        # 4  QHY 268C (USB)
        # 5  QHY 5III264C (USB)
        # 6  EQ6-R (USB)
        # 7  GEM45 (USB)
        # 8  Polemaster / EFA (USB)
        # 9  Lunarnet (USB)
        # 10 Dew A
        # 11 Dew B
        # 12 Dew C
        # 13 Voltage
        # 14 Current
        # 15 Power
        # [
        #     TYPE_SWITCH,
        #     "QHC268c (Power)",
        #     UNIT_OF_MEASUREMENT_NONE,
        #     DEVICE_TYPE_SWITCH_ICON,
        #     DEVICE_CLASS_SWITCH,
        #     STATE_CLASS_NONE,
        # ],
    ),
    DEVICE_TYPE_FILTERWHEEL: (
        [
            TYPE_SENSOR,
            "Names",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_FILTERWHEEL_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Position",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_FILTERWHEEL_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Current",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_FILTERWHEEL_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
    ),
    DEVICE_TYPE_DOME: (
        [
            TYPE_BINARY_SENSOR,
            "At home",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_DOME_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_BINARY_SENSOR,
            "At park",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_DOME_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
        [
            TYPE_SENSOR,
            "Altitude",
            UNIT_OF_MEASUREMENT_DEGREE,
            DEVICE_TYPE_DOME_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Azimuth",
            UNIT_OF_MEASUREMENT_DEGREE,
            DEVICE_TYPE_DOME_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_BINARY_SENSOR,
            "Shutter status",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_DOME_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
    ),
    DEVICE_TYPE_ROTATOR: (
        [
            TYPE_SENSOR,
            "Mechanical position",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_ROTATOR_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
        [
            TYPE_SENSOR,
            "Position",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_ROTATOR_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_MEASUREMENT,
        ],
    ),
    DEVICE_TYPE_SAFETYMONITOR: (
        [
            TYPE_BINARY_SENSOR,
            "Is safe",
            UNIT_OF_MEASUREMENT_NONE,
            DEVICE_TYPE_SAFETYMONITOR_ICON,
            DEVICE_CLASS_NONE,
            STATE_CLASS_NONE,
        ],
    ),
}

CAMERA_STATES = [
    "Camera idle",
    "Camera waiting",
    "Camera exposing",
    "Camera reading",
    "Camera download",
    "Camera error",
]
CAMERA_SENSOR_TYPES = [
    "Monochrome",
    "Colour not requiring Bayer decoding",
    "RGGB Bayer encoding",
    "CMYG Bayer encoding",
    "CMYG2 Bayer encoding",
    "LRGB TRUESENSE Bayer encoding",
]
