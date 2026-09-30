from datetime import timedelta

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.production.models import AnimalEvent


class HealthEvent(AnimalEvent):
    class Type(models.TextChoices):
        VACCINE = "vaccine", _("Vacunación")
        DEWORMING = "deworming", _("Desparasitación")
        ANTIBIOTIC = "antibiotic", _("Antibiótico")
        VITAMIN = "vitamin", _("Vitamina")

    type = models.CharField(_("tipo"), max_length=20, choices=Type.choices)
    product = models.CharField(_("producto"), max_length=150)
    dose = models.CharField(_("dosis"), max_length=100, blank=True)
    withdrawal_days = models.PositiveIntegerField(_("días de retiro"), default=0)
    withdrawal_end_date = models.DateField(
        _("fecha fin de retiro"), null=True, blank=True
    )

    class Meta(AnimalEvent.Meta):
        verbose_name = _("evento sanitario")
        verbose_name_plural = _("eventos sanitarios")

    def save(self, *args, **kwargs):
        if self.withdrawal_days and not self.withdrawal_end_date:
            self.withdrawal_end_date = self.date + timedelta(days=self.withdrawal_days)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.animal.tag} @ {self.date}: {self.get_type_display()} ({self.product})"
