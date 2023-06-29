from flask import Flask, request

from optimizer.optimization import Optimizer

from datetime import datetime, timedelta

import pytz


app = Flask(__name__)
app.config["DEBUG"] = True


@app.route("/")
def index():
    return "ok"


@app.route("/command/")
def command():
    if "time" not in request.args:
        return "missing charge time"

    if "max_time" not in request.args:
        return "missing max charge time"

    try:
        time = int(float(request.args["time"]) + 0.5)
    except:
        return "time has inappropriate format"

    try:
        max_time = int(request.args["max_time"])
    except:
        return "time has inappropriate format"

    now = datetime.now(pytz.timezone("Europe/Paris")) - timedelta(days=3)

    start = now.strftime("%Y-%m-%dT%H:%M:%S%z")
    end = (now + timedelta(days=2)).strftime(
        "%Y-%m-%dT%H:%M:%S%z"
    )

    start = "{0}:{1}".format(start[:-2], start[-2:])
    end = "{0}:{1}".format(end[:-2], end[-2:])

    optimizer = Optimizer()
    command = optimizer.optimize(time, max_time, start=start, end=end)

    return command


app.run()
