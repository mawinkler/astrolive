"""Define package errors."""


class AstroLiveError(Exception):
    """Define a base error."""

    pass


class RequestError(AstroLiveError):
    """Define an error related to invalid requests."""

    pass


class ResultError(AstroLiveError):
    """Define an error related to the result returned from a request."""

    pass


class DeviceResponseError(Exception):
    pass


class AlpacaError(DeviceResponseError):
    """Exception for when Alpaca throws an error with a numeric value.

    Args:
        error_number (int): Non-zero integer.
        error_message (str): Message describing the issue that was encountered.

    """

    def __init__(self, error_number: int, error_message: str):
        """Initialize NumericError object."""
        super().__init__(self)
        self.message = "Error %d: %s" % (error_number, error_message)

    def __str__(self):
        """Message to display with error."""
        return self.message


class AlpacaHttpError(DeviceResponseError):
    """Exception for when Alpaca throws an error without a numeric value.

    Args:
        error_message (str): Message describing the issue that was encountered.

    """

    def __init__(self, error_message: str):
        """Initialize ErrorMessage object."""
        super().__init__(self)
        self.message = error_message

    def __str__(self):
        """Message to display with error."""
        return self.message


class AlpacaHttp400Error(AlpacaHttpError):
    pass


class AlpacaHttp500Error(AlpacaHttpError):
    pass


class RequestConnectionError(IOError):
    pass
