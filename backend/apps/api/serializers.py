from decimal import Decimal
from django.utils import timezone

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.core.models import Farm, FarmMembership
from apps.health.models import HealthEvent
from apps.livestock.models import Animal, AnimalLot, Brand, Owner, Paddock
from apps.production.models import Milking, Weighing
from apps.reproduction.models import ReproductiveEvent


class FarmSerializer(serializers.ModelSerializer):
    class Meta:
        model = Farm
        fields = ["id", "name", "location", "updated_at"]
        read_only_fields = ["id", "updated_at"]


class FarmScopedSerializer(serializers.ModelSerializer):
    """Limit foreign keys to the farm authorized for the sync request."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        farm_id = self.context.get("farm_id")
        if farm_id is not None:
            for name in ("animal", "mother", "father", "paddock", "owner", "brand", "title_owner", "lot"):
                field = self.fields.get(name)
                if field is not None and field.queryset is not None:
                    field.queryset = field.queryset.filter(farm_id=farm_id)


class OwnerSerializer(FarmScopedSerializer):
    class Meta:
        model = Owner
        fields = ["id", "farm", "name", "id_number", "phone", "updated_at"]
        read_only_fields = ["updated_at"]


class BrandSerializer(FarmScopedSerializer):
    class Meta:
        model = Brand
        fields = ["id", "farm", "title_owner", "code", "updated_at"]
        read_only_fields = ["updated_at"]
        validators = []


class PaddockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paddock
        fields = ["id", "farm", "name", "updated_at"]
        read_only_fields = ["updated_at"]
        validators = []


class AnimalLotSerializer(FarmScopedSerializer):
    class Meta:
        model = AnimalLot
        fields = ["id", "farm", "name", "description", "updated_at"]
        read_only_fields = ["updated_at"]
        validators = []


class AnimalSerializer(FarmScopedSerializer):
    def validate(self, attrs):
        birth = attrs.get('birth_date')
        if birth and birth > timezone.localdate():
            raise serializers.ValidationError({'birth_date': 'El nacimiento no puede ser futuro.'})
        changed = attrs.get('status_changed_at')
        if changed and (changed > timezone.localdate() or (birth and changed < birth)):
            raise serializers.ValidationError({'status_changed_at': 'La fecha debe estar entre el nacimiento y hoy.'})
        sex, category = attrs.get('sex'), attrs.get('category')
        if (sex == 'H' and category == 'bull') or (sex == 'M' and category in ('cow_lactating', 'cow_dry')):
            raise serializers.ValidationError({'category': 'La categoría no corresponde al sexo.'})
        for field, required_sex in (('mother', 'H'), ('father', 'M')):
            parent = attrs.get(field)
            if parent and (parent.sex != required_sex or str(parent.id) == str(self.context.get('record_id'))):
                raise serializers.ValidationError({field: 'Revisá el sexo y la identificación del progenitor.'})
        return attrs

    class Meta:
        model = Animal
        fields = [
            "id", "farm", "tag", "name", "sex", "category", "birth_date",
            "mother", "father", "paddock", "owner", "brand", "lot", "status",
            "status_changed_at", "status_reason", "photo_url", "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tag_field = self.fields.get("tag")
        if tag_field is not None:
            tag_field.validators = [
                v
                for v in tag_field.validators
                if not isinstance(v, UniqueValidator)
            ]


class AnimalEventSerializer(FarmScopedSerializer):
    historical_warning = serializers.SerializerMethodField()

    def validate(self, attrs):
        date, animal = attrs.get('date'), attrs.get('animal')
        if date and (date > timezone.localdate() or (animal and animal.birth_date and date < animal.birth_date)):
            raise serializers.ValidationError({'date': 'La fecha debe estar entre el nacimiento y hoy.'})
        return attrs

    def get_historical_warning(self, obj):
        return obj.animal.status != Animal.Status.ACTIVE


class WeighingSerializer(AnimalEventSerializer):
    weight_kg = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal("0.01"))
    class Meta:
        model = Weighing
        fields = ["id", "animal", "date", "weight_kg", "updated_at", "historical_warning"]
        read_only_fields = ["updated_at", "historical_warning"]


class MilkingSerializer(AnimalEventSerializer):
    liters = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0"))
    class Meta:
        model = Milking
        fields = ["id", "animal", "date", "shift", "liters", "updated_at", "historical_warning"]
        read_only_fields = ["updated_at", "historical_warning"]
        validators = []


class ReproductiveEventSerializer(AnimalEventSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs['animal'].sex != 'H':
            raise serializers.ValidationError({'animal': 'Seleccioná una hembra para este evento.'})
        if attrs['type'] == 'service' and not attrs.get('service_method'):
            raise serializers.ValidationError({'service_method': 'Indicá el método del servicio.'})
        if attrs['type'] == 'palpation' and not attrs.get('palpation_result'):
            raise serializers.ValidationError({'palpation_result': 'Indicá el resultado de la palpación.'})
        return attrs

    class Meta:
        model = ReproductiveEvent
        fields = [
            "id", "animal", "date", "type", "service_method", "bull_straw",
            "palpation_result", "estimated_calving_date",
            "suggested_drying_off_date", "updated_at", "historical_warning",
        ]
        read_only_fields = [
            "estimated_calving_date", "suggested_drying_off_date",
            "updated_at", "historical_warning",
        ]


class HealthEventSerializer(AnimalEventSerializer):
    withdrawal_days = serializers.IntegerField(min_value=0, max_value=3650, required=False, default=0)
    class Meta:
        model = HealthEvent
        fields = [
            "id", "animal", "date", "type", "product", "dose",
            "withdrawal_days", "withdrawal_end_date", "updated_at",
            "historical_warning",
        ]
        read_only_fields = ["withdrawal_end_date", "updated_at", "historical_warning"]


class FarmMembershipSerializer(serializers.ModelSerializer):
    farm_name = serializers.CharField(source="farm.name", read_only=True)

    class Meta:
        model = FarmMembership
        fields = ["id", "farm", "farm_name", "role"]
