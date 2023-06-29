import pytest


from server.api import create_app


@pytest.fixture
def app():
    app = create_app()
    return app


def test_index(app):
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert response.data.decode("ascii") == "ok"


def test_command(app):
    response = app.test_client().get("/command/?time=10&max_time=24")

    assert response.status_code == 200

    data = response.data.decode("ascii").strip()

    assert len(data) == 48, "command must be 48 bytes long"
    assert all([int(byte) in [0, 1] for byte in data]), "command must be 0s or 1s only"


def test_command_saved_emissions(app):
    response = app.test_client().get("/command/?time=10&max_time=24&saved_emissions")

    assert response.status_code == 200

    data = response.data.decode("ascii").strip()

    lines = data.split("\n")

    assert len(lines[0]) == 48, "command must be 48 bytes long"
    assert all(
        [int(byte) in [0, 1] for byte in lines[0]]
    ), "command must be 0s or 1s only"
    assert len(lines[1]) <= 2, "percentage of saved emissions should be returned"
