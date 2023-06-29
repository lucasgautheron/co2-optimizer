from server.api import app  # Flask instance of the API

def test_index():
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert response.data.decode("ascii") == "ok"


def test_command():
    response = app.test_client().get("/command/?min_time=10&max_time=24")

    assert response.status_code == 200
    assert len(response.data) == 48

    assert all([byte in [0, 1] for byte in response.data])
