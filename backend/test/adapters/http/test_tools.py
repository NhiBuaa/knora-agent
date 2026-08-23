import importlib.util


def test_ticket_lookup_router_is_owned_by_http_adapter() -> None:
    from knora.adapters.http import tools

    assert tools.router is not None
    assert importlib.util.find_spec("knora.tools.http") is None
