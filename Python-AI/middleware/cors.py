

class cors_middleware(CORSMiddleware):
    """CORS middleware configured from Settings.cors.

    FastAPI's ``add_middleware`` expects a class that accepts the ``app``
    argument as its first positional parameter. By subclassing ``CORSMiddleware``
    we can inject the configuration at import time while keeping the same
    signature expected by ``app.add_middleware``.
    """

    def __init__(self, app):
        settings = get_settings()
        cors_cfg = settings.cors
        super().__init__(
            app,
            allow_origins=cors_cfg.allow_origins,
            allow_methods=cors_cfg.allow_methods,
            allow_headers=cors_cfg.allow_headers,
            allow_credentials=cors_cfg.allow_credentials,
            expose_headers=cors_cfg.expose_headers,
            max_age=cors_cfg.max_age,
        )

__all__ = ["cors_middleware"]