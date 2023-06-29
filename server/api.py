from flask import Flask, request

from optimizer.optimization import Optimizer
from optimizer.utils import datetime_to_str

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

    now = datetime.now(pytz.timezone("Europe/Paris")).replace(
        minute=0, second=0, microsecond=0
    )

    start = datetime_to_str(now)
    end = datetime_to_str(now + timedelta(days=2))

    optimizer = Optimizer()
    command = optimizer.optimize(time, max_time, start=start, end=end)

    return "".join(map(str, command.astype(int)))


app.run()
