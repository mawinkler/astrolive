"""Convert coordinates from string to Angle"""
from astropy import units as u
from astropy.coordinates import Angle


def check_equatorial_coordinates(ra, dec):
    """Convert equatorial coordinates"""

    if isinstance(ra, str):
        ra = Angle(ra, unit=u.hourangle).deg
    if isinstance(dec, str):
        dec = Angle(dec, unit=u.deg).deg
    return ra, dec


def check_horizontal_coordinates(az, alt):
    """Convert horizonal coordinates"""

    if isinstance(az, str):
        az = Angle(az, unit=u.deg).deg
    if isinstance(alt, str):
        alt = Angle(alt, unit=u.deg).deg
    return az, alt
