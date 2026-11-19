"""Application package bootstrap.

Expõe apenas o FastAPI app e o factory para uso externo (ex.: uvicorn).
"""

__all__ = ["app", "create_app"]


def __getattr__(name):
    """Load the web application only when its public exports are requested.

    Administrative tools can import configuration and crypto without starting
    the application, configuring log files or loading unrelated integrations.
    """
    if name in __all__:
        from .main import app, create_app
        return app if name == 'app' else create_app
    raise AttributeError(name)
