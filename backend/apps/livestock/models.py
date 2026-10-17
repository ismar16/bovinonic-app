from django.db import models, transaction
from django.db.models import Max
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
    area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    area_unit = models.CharField(max_length=2, choices=[('mz', 'Manzanas'), ('ha', 'Hectáreas'), ('m2', 'Metros cuadrados')], default='mz')
    max_occupation_days = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["farm", "name"], name="uniq_paddock_farm_name")
        ]
        indexes = [models.Index(fields=["farm", "updated_at"])]
        verbose_name = _("potrero")
        verbose_name_plural = _("potreros")

    def __str__(self):
        return f"{self.name} ({self.farm})"


class PaddockMovement(TimeStampedModel):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='paddock_movements')
    date = models.DateField()
    destination = models.ForeignKey(Paddock, on_delete=models.PROTECT, related_name='movements')
    lot = models.ForeignKey('AnimalLot', null=True, blank=True, on_delete=models.SET_NULL)
    animals = models.JSONField(default=list)
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        indexes = [models.Index(fields=['farm', 'updated_at'])]


class AnimalLot(TimeStampedModel):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="lots", verbose_name=_("finca"))
    name = models.CharField(_("nombre"), max_length=100)
    description = models.CharField(_("descripción"), max_length=500, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["farm", "name"], name="uniq_lot_farm_name")]
        indexes = [models.Index(fields=["farm", "updated_at"])]
        verbose_name = _("lote de animales")
        verbose_name_plural = _("lotes de animales")

    def __str__(self):
        return f"{self.name} ({self.farm})"


class Animal(TimeStampedModel):
    paddock_since = models.DateField(null=True, blank=True, editable=False)
    paddock_movement = models.UUIDField(null=True, editable=False)
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
    lot = models.ForeignKey(AnimalLot, on_delete=models.SET_NULL, null=True, blank=True, related_name="animals", verbose_name=_("lote"))
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
    photo_url = models.URLField(_("foto"), blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["farm", "updated_at"]),
            models.Index(fields=["farm", "status"]),
        ]
        verbose_name = _("animal")
        verbose_name_plural = _("animales")

    def __str__(self):
        return f"{self.tag} - {self.name or 'sin nombre'}"


class AnimalAgreement(TimeStampedModel):
    class Kind(models.TextChoices):
        WEIGHT_GAIN = 'weight_gain', _('Ganancia de peso')
        SALE = 'sale', _('Valor de venta')
        OFFSPRING = 'offspring', _('Crías: valor de venta')
        PASTURE = 'pasture', _('Pasto alquilado')

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='animal_agreements')
    title = models.CharField(max_length=150)
    owner_name = models.CharField(max_length=150)
    partner_name = models.CharField(max_length=150)
    external_farm = models.CharField(max_length=150)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.WEIGHT_GAIN)
    currency = models.CharField(max_length=3, choices=[('NIO', 'Córdobas'), ('USD', 'Dólares')], default='NIO')
    owner_share = models.DecimalField(max_digits=5, decimal_places=2, default=50)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=[('active', 'En curso'), ('settled', 'Liquidado')], default='active')
    notes = models.CharField(max_length=2000, blank=True)
    # A whole agreement (terms, individual weights and ledger) syncs atomically.
    animals = models.JSONField(default=list)
    expenses = models.JSONField(default=list)
    settlement = models.JSONField(null=True, blank=True, editable=False)

    class Meta:
        indexes = [models.Index(fields=['farm', 'updated_at'])]
        verbose_name = 'acuerdo de manejo'
        verbose_name_plural = 'acuerdos de manejo'

    def __str__(self):
        return self.title


class AnimalSale(TimeStampedModel):
    number = models.PositiveIntegerField(null=True, editable=False)
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='animal_sales')
    date = models.DateField()
    buyer = models.CharField(max_length=150)
    buyer_phone = models.CharField(max_length=30, blank=True)
    currency = models.CharField(max_length=3, choices=[('NIO', 'Córdobas'), ('USD', 'Dólares')])
    notes = models.CharField(max_length=2000, blank=True)
    lines = models.JSONField(default=list)
    total = models.DecimalField(max_digits=18, decimal_places=2, editable=False)

    class Meta:
        indexes = [models.Index(fields=['farm', 'updated_at'])]
        constraints = [models.UniqueConstraint(fields=['farm', 'number'], name='uniq_sale_number_per_farm')]

    @property
    def reference(self):
        return f'V-{self.number:06d}' if self.number is not None else None

    def save(self, *args, **kwargs):
        if self.number is not None:
            return super().save(*args, **kwargs)
        # Same lock as sync: offline devices receive distinct consecutive numbers.
        with transaction.atomic():
            Farm.objects.select_for_update().get(pk=self.farm_id)
            last = type(self).objects.filter(farm_id=self.farm_id).aggregate(last=Max('number'))['last'] or 0
            self.number = last + 1
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = set(kwargs['update_fields']) | {'number'}
            return super().save(*args, **kwargs)


class SalePayment(TimeStampedModel):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='sale_payments')
    sale = models.ForeignKey(AnimalSale, on_delete=models.CASCADE, related_name='payments')
    date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    method = models.CharField(max_length=20, choices=[('cash', 'Efectivo'), ('transfer', 'Transferencia'), ('other', 'Otro')])
    reference = models.CharField(max_length=150, blank=True)

    class Meta:
        indexes = [models.Index(fields=['farm', 'updated_at'])]


class SaleExpense(TimeStampedModel):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='sale_expenses')
    sale = models.ForeignKey(AnimalSale, on_delete=models.CASCADE, related_name='expense_adjustments')
    animal = models.ForeignKey(Animal, on_delete=models.PROTECT, related_name='sale_expenses')
    date = models.DateField()
    concept = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=11, decimal_places=2)
    paid_by = models.CharField(max_length=10, choices=[('owner', 'Propietario'), ('partner', 'Responsable')])

    class Meta:
        indexes = [models.Index(fields=['farm', 'updated_at'])]
