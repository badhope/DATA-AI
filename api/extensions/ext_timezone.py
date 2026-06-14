import os
import time

from data_app import DATAApp


def init_app(app: DATAApp):
    os.environ["TZ"] = "UTC"
    # windows platform not support tzset
    if hasattr(time, "tzset"):
        time.tzset()
