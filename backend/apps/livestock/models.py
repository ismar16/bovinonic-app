from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import Farm, TimeStampedModel


class Owner(TimeStampedModel):
    farm = models.ForeignKey(
        Farm, on_delete=models.CASCADE, related_name="owners", verbose_name=_("finca")
    )
    name = models.CharField(_("nombre"), max_length=150)
    id_number = models.CharField(_("identificación"), max_length=50, blank=True)
    phone = models.CharField(_("teléfono"), max_length=30, blank=True)

    class Meta:
        indexes = [models.Index(fields=["farm", "updated_at"])]
        verbose_name = _("propietario")
        verbose_name_plural = _("propietarios")

    def __str__(self):
        return self.name


class Brand(TimeStampedModel):
    farm = models.ForeignKey(
        Farm, on_delete=models.PROTECT, related_name="brands", verbose_name=_("finca")
    )
    title_owner = models.ForeignKey(
        Owner,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="brands",
        verbose_name=_("titular propietario"),
    )
    code = models.CharField(_("código"), max_length=50)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["farm", "code"], name="uniq_brand_farm_code")
        ]
        indexes = [models.Index(fields=["farm", "updated_at"])]
        verbose_name = _("fierro")
        verbose_name_plural = _("fierros")

    def __str__(self):
        return f"{self.code} ({self.farm})"


class Paddock(TimeStampedModel):
    farm = models.ForeignKey(
        Farm, on_delete=models.CASCADE, related_name="paddocks", verbose_name=_("finca")
    )
    name = models.CharField(_("nombre"), max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["farm", "name"], name="uniq_paddock_farm_name")
        ]
        indexes = [models.Index(fields=["farm", "updated_at"])]
        verbose_name = _("potrero")
        verbose_name_plural = _("potreros")

    def __str__(self):
        return f"{self.name} ({self.farm})"


class Animal(TimeStampedModel):
    class Sex(models.TextChoices):
        MALE = "M", _("Macho")
        FEMALE = "H", _("Hembra")

    class Category(models.TextChoices):
        CALF = "calf", _("Ternero/a")
        HEIFER = "heifer", _("Novillo/a")
        COW_LACTATING = "cow_lactating", _("Vaca en ordeño")
        COW_DRY = "cow_dry", _("Vaca seca")
        BULL = "bull", _("Toro reproductor")

    class Status(models.TextChoices):
        ACTIVE = "active", _("Activo")
        SOLD = "sold", _("Vendido")
        DEAD = "dead", _("Muerto")
        CULLED = "culled", _("Descarte")

    farm = models.ForeignKey(
        Farm, on_delete=models.CASCADE, related_name="animals", verbose_name=_("finca")
    )
    tag = models.CharField(_("arete"), max_length=50, unique=True, db_index=True)
    name = models.CharField(_("nombre"), max_length=150, blank=True)
    sex = models.CharField(_("sexo"), max_length=1, choices=Sex.choices)
    category = models.CharField(_("categoría"), max_length=20, choices=Category.choices)
    birth_date = models.DateField(_("fecha de nacimiento"), null=True, blank=True)
    mother = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="offspring_as_mother",
        limit_choices_to={"sex": "H"},
        verbose_name=_("madre"),
    )
    father = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="offspring_as_father",
        limit_choices_to={"sex": "M"},
        verbose_name=_("padre"),
    )
    paddock = models.ForeignKey(
        Paddock,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="animals",
        verbose_name=_("potrero"),
    )
    owner = models.ForeignKey(
        Owner,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="animals",
        verbose_name=_("propietario"),
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="animals",
        verbose_name=_("fierro"),
    )
    status = models.CharField(
        _("estado"), max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    status_changed_at = models.DateField(
        _("fecha de cambio de estado"), null=True, blank=True
    )
    status_reason = models.CharField(
        _("motivo del cambio de estado"), max_length=255, blank=True
    )

    class Meta:
        indexes = [
            models.Index(fields=["farm", "updated_at"]),
            models.Index(fields=["farm", "status"]),
        ]
        verbose_name = _("animal")
        verbose_name_plural = _("animales")

    def __str__(self):
        return f"{self.tag} - {self.name or 'sin nombre'}"
