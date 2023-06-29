from datetime import datetime


def now():

    from flask import Flask, request


from datetime import datetime, timedelta
import pytz


def now():
    return datetime.now(pytz.timezone("Europe/Paris"))


def str_to_datetime(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")


def datetime_to_str(dt):
    s = datetime.strftime(dt, "%Y-%m-%dT%H:%M:%S%z")
    s = "{0}:{1}".format(s[:-2], s[-2:])
    return s
