from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import Farm, TimeStampedModel
from apps.livestock.models import Animal


class AnimalEvent(TimeStampedModel):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, editable=False, verbose_name=_("finca"))
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, verbose_name=_("animal"))
    date = models.DateField(_("fecha"))

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["farm", "updated_at"]),
            models.Index(fields=["animal", "date"]),
        ]

    def save(self, *args, **kwargs):
        if self.animal_id and not self.farm_id:
            self.farm_id = self.animal.farm_id
        super().save(*args, **kwargs)


class Weighing(AnimalEvent):
    weight_kg = models.DecimalField(_("peso (kg)"), max_digits=7, decimal_places=2)
    source_type = models.CharField(max_length=24, default='manual', editable=False)
    source_id = models.UUIDField(null=True, editable=False)
    voided = models.BooleanField(default=False, editable=False)

    class Meta(AnimalEvent.Meta):
        verbose_name = _("pesaje")
        verbose_name_plural = _("pesajes")

    def __str__(self):
        return f"{self.animal.tag} @ {self.date}: {self.weight_kg} kg"


class Milking(AnimalEvent):
    class Shift(models.TextChoices):
        MORNING = "AM", _("Mañana")
        AFTERNOON = "PM", _("Tarde")

    shift = models.CharField(_("turno"), max_length=2, choices=Shift.choices)
    liters = models.DecimalField(_("litros"), max_digits=6, decimal_places=2)

    class Meta(AnimalEvent.Meta):
        verbose_name = _("ordeño")
        verbose_name_plural = _("ordeños")
        constraints = [
            models.UniqueConstraint(
                fields=["animal", "date", "shift"], name="uniq_milking_animal_date_shift"
            )
        ]

    def __str__(self):
        return f"{self.animal.tag} @ {self.date} {self.shift}: {self.liters} L"


class DailyMilkProduction(TimeStampedModel):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='daily_milk')
    date = models.DateField()
    liters = models.DecimalField(max_digits=8, decimal_places=2)
    notes = models.CharField(max_length=1000, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['farm', 'date'], name='uniq_daily_milk_farm_date')]
        indexes = [models.Index(fields=['farm', 'updated_at'])]
