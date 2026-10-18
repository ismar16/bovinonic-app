from datetime import timedelta

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.production.models import AnimalEvent
from apps.core.models import Farm, TimeStampedModel
from apps.livestock.models import Animal

GESTATION_DAYS = 283
DRYING_OFF_DAYS_BEFORE_CALVING = 60


class ReproductiveEvent(AnimalEvent):
    calving_record = models.UUIDField(null=True, editable=False)
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


class CalvingRecord(TimeStampedModel):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='calvings')
    mother = models.ForeignKey(Animal, on_delete=models.PROTECT, related_name='calvings')
    date = models.DateField()
    delivery = models.CharField(max_length=16, choices=[('normal','Normal'),('assisted','Asistido'),('complicated','Con complicaciones')], default='normal')
    maternal_status = models.CharField(max_length=24, choices=[('keep','Conservar categoría'),('cow_lactating','Vaca en ordeño'),('cow_nursing','Vaca con cría'),('cow_dry','Vaca seca')], default='keep')
    mother_version = models.CharField(max_length=64)
    calves = models.JSONField(default=list)
    location = models.JSONField(default=dict)
    notes = models.CharField(max_length=1000, blank=True)
    result = models.JSONField(default=dict, editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['farm','mother','date'],name='uniq_calving_mother_date')]
        indexes = [models.Index(fields=['farm','updated_at'])]
