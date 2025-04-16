import inspect
import logging
import os
from functools import wraps
from typing import get_type_hints, Any
from datetime import datetime

# Create a dedicated logger for type logging
type_logger = logging.getLogger("type_checker")
type_logger.setLevel(logging.INFO)

# Create file handler
file_handler = logging.FileHandler("/tmp/typing.log")
file_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter("%(asctime)s - %(message)s")
file_handler.setFormatter(formatter)

# Add handler to logger
type_logger.addHandler(file_handler)


def log_typing(func):
    """
    A decorator that logs the input and output types of a function call
    along with its location in the source code.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get function location info
        frame = inspect.currentframe()
        filename = inspect.getfile(func)
        line_number = frame.f_back.f_lineno if frame and frame.f_back else "unknown"

        # Get type hints
        type_hints = get_type_hints(func)
        return_type = type_hints.pop("return", Any)

        # Get actual argument types
        actual_arg_types = {}

        # Handle positional arguments
        func_params = inspect.signature(func).parameters
        param_names = list(func_params.keys())

        for i, arg in enumerate(args):
            if i < len(param_names):
                actual_arg_types[param_names[i]] = type(arg).__name__

        # Handle keyword arguments
        for key, value in kwargs.items():
            actual_arg_types[key] = type(value).__name__

        # Log the type information
        log_message = (
            f"\nFunction: {func.__name__}\n"
            f"Location: {filename}:{line_number}\n"
            f"Expected Types: {type_hints}\n"
            f"Actual Argument Types: {actual_arg_types}\n"
            f"Return Type: {return_type.__name__}\n"
            f"Timestamp: {datetime.now().isoformat()}\n"
            f"{'-' * 80}"
        )

        type_logger.info(log_message)

        # Execute the function
        result = func(*args, **kwargs)

        # Log the actual return type
        if result is not None:
            actual_return_type = type(result).__name__
            type_logger.info(
                f"Actual Return Type for {func.__name__}: {actual_return_type}\n"
                f"{'-' * 80}"
            )

        return result

    return wrapper
