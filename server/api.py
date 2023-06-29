from flask import Flask, request

from optimizer.optimization import Optimizer
from optimizer.utils import datetime_to_str

from datetime import datetime, timedelta
import pytz

import numpy as np

def create_app(test_config=None):
    # create and configure the app

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

        output = "".join(map(str, command.astype(int)))

        if "saved_emissions" in request.args:
            production = optimizer.prediction.dispatch(start, end)

            sources_carbon_intensity = np.array(
                [source.carbon_intensity for source in optimizer.sources]
            )
            carbon_intensity = (sources_carbon_intensity @ production) / production.sum(
                axis=0
            )

            emissions = np.dot(carbon_intensity, command)
            ref_emissions = carbon_intensity[:time].sum()

            emissions_saved = (1 - emissions / ref_emissions) * 100

            output += f"\n{emissions_saved:.0f}"

        return output

    return app


if __name__ == "__main__":
    app = create_app()
