import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(_("fecha de creación"), auto_now_add=True)
    updated_at = models.DateTimeField(_("fecha de actualización"), auto_now=True)

    class Meta:
        abstract = True


class Farm(TimeStampedModel):
    name = models.CharField(_("nombre"), max_length=150)
    location = models.CharField(_("ubicación"), max_length=255, blank=True)

    class Meta:
        indexes = [models.Index(fields=["updated_at"])]
        verbose_name = _("finca")
        verbose_name_plural = _("fincas")

    def __str__(self):
        return self.name


class FarmMembership(TimeStampedModel):
    class Role(models.TextChoices):
        ADMIN = "admin", _("Administrador")
        TECHNICIAN = "technician", _("Técnico")
        OPERATOR = "operator", _("Operador de corral")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("usuario"),
    )
    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("finca"),
    )
    role = models.CharField(_("rol"), max_length=20, choices=Role.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "farm"], name="uniq_membership_user_farm"
            )
        ]
        indexes = [models.Index(fields=["farm", "updated_at"])]
        verbose_name = _("membresía de finca")
        verbose_name_plural = _("membresías de finca")

    def __str__(self):
        return f"{self.user} @ {self.farm} ({self.role})"
