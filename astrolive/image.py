import logging

import cv2
import numpy as np
from astropy.visualization import (
    AsinhStretch,
    AsymmetricPercentileInterval,
    LinearStretch,
    LogStretch,
    ManualInterval,
    MinMaxInterval,
    SinhStretch,
    SqrtStretch,
)

from .const import (
    CAMERA_SAMPLE_RESOLUTION,
    IMAGE_PUBLISH_DIMENSIONS,
    STRETCH_AP_MINMAX_PERCENT,
    STRETCH_AP_MINMAX_VALUE,
    STRETCH_AP_STRETCH_FUNCTION,
    STRETCH_STF_CLIPPING_POINT,
    STRETCH_STF_TARGET_BACKGROUND,
)

_LOGGER = logging.getLogger(__name__)


class ImageManipulation:
    # #########################################################################
    # Normalize the image data
    # #########################################################################
    @staticmethod
    async def normalize_image(image):
        return np.divide(image, 2**CAMERA_SAMPLE_RESOLUTION)

    # #########################################################################
    # PixInsight STF Stretch
    # #########################################################################
    @staticmethod
    async def midtones_transfer_function(x, m):
        return (m - 1) * x / ((2 * m - 1) * x - m)

    @staticmethod
    async def compute_stf_stretch(image, target_background=STRETCH_STF_TARGET_BACKGROUND):
        """
        Apply a PixInsight-like Screen Transfer Function (STF) to a grayscale image.

        Parameters:
            image : 2D numpy array
                The input image data (can be float or uint).
            target_background : float
                Target background level for midtones (PixInsight uses ~0.25)

        Returns:
            stretched : 2D numpy array
                Auto-stretched image, scaled 0–1.
        """
        # Normalized image data
        x = image

        # Mc Image median
        Mc = np.median(x)

        # Normalized median absolute deviation
        MADNc = 1.4826 * np.median(np.absolute(x - Mc))

        # Target mean background in the [0, 1] range. This parameter controls the global illumination of the
        # image. The recommended default value is B 0 0.25.
        B = target_background

        # Clipping point in units of MADNc, measured from the median Mc
        C = STRETCH_STF_CLIPPING_POINT

        ac = 0 if Mc <= 0.5 else 1

        # Compute the clipping points
        sc = np.minimum(1, np.maximum(0, Mc + C * MADNc))
        hc = np.minimum(1, np.maximum(0, Mc - C * MADNc))

        # Compute midtones balance
        mc = (
            await ImageManipulation.midtones_transfer_function((Mc - sc), B)
            if ac == 0
            else await ImageManipulation.midtones_transfer_function(B, (hc - Mc))
        )

        # Stretch using midtones transfer function
        M = await ImageManipulation.midtones_transfer_function(x, mc)

        _LOGGER.debug(f"MC: {Mc:.8f}, MADNc: {MADNc:.8f}, B: {B}, C: {C}, ac: {ac}, sc: {sc:.8f}, hc: {hc:.8f}")

        return np.clip(M, 0, 1)

    # #########################################################################
    # AstroPy Stretch
    # #########################################################################
    @staticmethod
    async def compute_astropy_stretch(
        image,
        stretch=STRETCH_AP_STRETCH_FUNCTION,
        minmax_percent=STRETCH_AP_MINMAX_PERCENT,
        minmax_value=STRETCH_AP_MINMAX_VALUE,
    ):
        """
        ***Deprecated stretching method using astropy***

        Apply given stretch and scaling to an image array.

        Args:
            image (array): The input image array.
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

        transform += SinhStretch()

        # Adding the scaling to the transform
        if minmax_percent is not None:
            transform += AsymmetricPercentileInterval(*minmax_percent)

            if minmax_value is not None:
                _LOGGER.error("Both minmax_percent and minmax_value are set, minmax_value will be ignored.")
        elif minmax_value is not None:
            transform += ManualInterval(*minmax_value)
        else:  # Default, scale the entire image range to [0,1]
            transform += MinMaxInterval()

        # image = np.divide(image, 2**CAMERA_SAMPLE_RESOLUTION)

        # Performing the transform and then putting it into the integer range 0-255
        image = transform(image)

        return image

    # #########################################################################
    # Downscale Image
    # #########################################################################
    @staticmethod
    async def resize_image(image):
        image_uint8 = (image * 255).astype(np.uint8)

        h, w = image_uint8.shape
        target_w, target_h = IMAGE_PUBLISH_DIMENSIONS

        # Determine scale factor and new size
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)

        image_resized = cv2.resize(image_uint8, (new_w, new_h), interpolation=cv2.INTER_AREA)

        return image_resized
