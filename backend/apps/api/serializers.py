from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.core.models import Farm, FarmMembership
from apps.health.models import HealthEvent
from apps.livestock.models import Animal, Brand, Owner, Paddock
from apps.production.models import Milking, Weighing
from apps.reproduction.models import ReproductiveEvent


class FarmSerializer(serializers.ModelSerializer):
    class Meta:
        model = Farm
        fields = ["id", "name", "location", "updated_at"]
        read_only_fields = ["id", "updated_at"]


class OwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Owner
        fields = ["id", "farm", "name", "id_number", "phone", "updated_at"]
        read_only_fields = ["updated_at"]


class BrandSerializer(serializers.ModelSerializer):
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


class AnimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Animal
        fields = [
            "id", "farm", "tag", "name", "sex", "category", "birth_date",
            "mother", "father", "paddock", "owner", "brand", "status",
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


class AnimalEventSerializer(serializers.ModelSerializer):
    historical_warning = serializers.SerializerMethodField()

    def get_historical_warning(self, obj):
        return obj.animal.status != Animal.Status.ACTIVE


class WeighingSerializer(AnimalEventSerializer):
    class Meta:
        model = Weighing
        fields = ["id", "animal", "date", "weight_kg", "updated_at", "historical_warning"]
        read_only_fields = ["updated_at", "historical_warning"]


class MilkingSerializer(AnimalEventSerializer):
    class Meta:
        model = Milking
        fields = ["id", "animal", "date", "shift", "liters", "updated_at", "historical_warning"]
        read_only_fields = ["updated_at", "historical_warning"]
        validators = []


class ReproductiveEventSerializer(AnimalEventSerializer):
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
