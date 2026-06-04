from django.apps import AppConfig


class PortalConfig(AppConfig):
    name = "portal"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """Load the schema config and warm up category choices at startup."""
        from django.conf import settings

        from portal import config as portal_config

        try:
            cfg = portal_config.load_config(settings.SCHEMA_CONFIG_PATH)
            # Populate category choices from the vectors DB.
            # This call will fail gracefully if the vectors DB is not yet
            # reachable (e.g., during testing without a real DB).
            try:
                portal_config.populate_choices(cfg)
            except Exception as exc:  # noqa: BLE001
                import warnings

                warnings.warn(
                    f"VectorBase: could not populate category choices at startup: {exc}",
                    stacklevel=1,
                )
        except FileNotFoundError as exc:
            import warnings

            warnings.warn(str(exc), stacklevel=1)
