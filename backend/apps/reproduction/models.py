from datetime import timedelta

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.production.models import AnimalEvent

GESTATION_DAYS = 283
DRYING_OFF_DAYS_BEFORE_CALVING = 60


class ReproductiveEvent(AnimalEvent):
    class Type(models.TextChoices):
        HEAT = "heat", _("Celo detectado")
        SERVICE = "service", _("Servicio (monta/IA)")
        PALPATION = "palpation", _("Diagnóstico de preñez")
        CALVING = "calving", _("Parto")
        DRYING_OFF = "drying_off", _("Secado")
        ABORTION = "abortion", _("Aborto")

    class ServiceMethod(models.TextChoices):
        NATURAL = "natural", _("Monta natural")
        ARTIFICIAL_INSEMINATION = "ai", _("Inseminación artificial")

    class PalpationResult(models.TextChoices):
        PREGNANT = "pregnant", _("Preñada")
        EMPTY = "empty", _("Vacía")

    type = models.CharField(_("tipo"), max_length=20, choices=Type.choices)
    service_method = models.CharField(
        _("método de servicio"),
        max_length=10,
        choices=ServiceMethod.choices,
        null=True,
        blank=True,
    )
    bull_straw = models.CharField(_("toro/pajilla"), max_length=150, blank=True)
    palpation_result = models.CharField(
        _("resultado de palpación"),
        max_length=10,
        choices=PalpationResult.choices,
        null=True,
        blank=True,
    )
    estimated_calving_date = models.DateField(
        _("fecha estimada de parto"), null=True, blank=True
    )
    suggested_drying_off_date = models.DateField(
        _("fecha sugerida de secado"), null=True, blank=True
    )

    class Meta(AnimalEvent.Meta):
        verbose_name = _("evento reproductivo")
        verbose_name_plural = _("eventos reproductivos")

    def save(self, *args, **kwargs):
        if self.type == self.Type.SERVICE and not self.estimated_calving_date:
            self.estimated_calving_date = self.date + timedelta(days=GESTATION_DAYS)
        if self.estimated_calving_date and not self.suggested_drying_off_date:
            self.suggested_drying_off_date = self.estimated_calving_date - timedelta(
                days=DRYING_OFF_DAYS_BEFORE_CALVING
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.animal.tag} @ {self.date}: {self.get_type_display()}"
