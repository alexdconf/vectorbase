from django.db import models


class DailyQuota(models.Model):
    """
    Tracks the total number of searches performed on a given calendar day.

    This lives in the `portal` app because quota enforcement is a portal concern.
    The `default` database stores this model; it is never written to `vectors`.
    """

    date = models.DateField(unique=True)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-date"]
        verbose_name = "daily quota"
        verbose_name_plural = "daily quotas"

    def __str__(self) -> str:
        return f"{self.date}: {self.count} searches"
