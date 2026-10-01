from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import FarmMembership
from apps.health.models import HealthEvent
from apps.livestock.models import Animal, Brand, Owner, Paddock
from apps.production.models import Milking, Weighing
from apps.reproduction.models import (
    DRYING_OFF_DAYS_BEFORE_CALVING,
    GESTATION_DAYS,
    ReproductiveEvent,
)

from .permissions import HasFarmMembership
from .serializers import (
    AnimalSerializer,
    BrandSerializer,
    HealthEventSerializer,
    MilkingSerializer,
    OwnerSerializer,
    PaddockSerializer,
    ReproductiveEventSerializer,
    WeighingSerializer,
)

PULL_COLLECTIONS = {
    "owners": (Owner, OwnerSerializer),
    "brands": (Brand, BrandSerializer),
    "paddocks": (Paddock, PaddockSerializer),
    "animals": (Animal, AnimalSerializer),
    "weighings": (Weighing, WeighingSerializer),
    "milkings": (Milking, MilkingSerializer),
    "reproductive_events": (ReproductiveEvent, ReproductiveEventSerializer),
    "health_events": (HealthEvent, HealthEventSerializer),
}

WRITE_COLLECTIONS = {
    "animals": (Animal, AnimalSerializer, FarmMembership.Role.TECHNICIAN),
    "owners": (Owner, OwnerSerializer, FarmMembership.Role.ADMIN),
    "brands": (Brand, BrandSerializer, FarmMembership.Role.ADMIN),
    "paddocks": (Paddock, PaddockSerializer, FarmMembership.Role.ADMIN),
    "weighings": (Weighing, WeighingSerializer, FarmMembership.Role.OPERATOR),
    "milkings": (Milking, MilkingSerializer, FarmMembership.Role.OPERATOR),
    "reproductive_events": (
        ReproductiveEvent,
        ReproductiveEventSerializer,
        FarmMembership.Role.TECHNICIAN,
    ),
    "health_events": (
        HealthEvent,
        HealthEventSerializer,
        FarmMembership.Role.TECHNICIAN,
    ),
}

EVENT_MODELS = (Weighing, Milking, ReproductiveEvent, HealthEvent)
CATALOG_MODELS = (Animal, Owner, Brand, Paddock)

ROLE_RANK = {
    FarmMembership.Role.OPERATOR: 1,
    FarmMembership.Role.TECHNICIAN: 2,
    FarmMembership.Role.ADMIN: 3,
}


class SyncPullView(APIView):
    permission_classes = [HasFarmMembership]

    def get(self, request):
        farm_id = request.farm_membership.farm_id
        since_param = request.query_params.get("since")
        if since_param and " " in since_param:
            since_param = since_param.replace(" ", "+")
        since = parse_datetime(since_param) if since_param else None

        payload = {}
        for name, (model, serializer_class) in PULL_COLLECTIONS.items():
            queryset = model.objects.filter(farm_id=farm_id)
            if since:
                queryset = queryset.filter(updated_at__gt=since)
            payload[name] = serializer_class(queryset, many=True).data
        return Response(payload)


def _apply_computed_fields(model, validated):
    if model is ReproductiveEvent:
        if (
            validated.get("type") == ReproductiveEvent.Type.SERVICE
            and not validated.get("estimated_calving_date")
        ):
            validated["estimated_calving_date"] = validated["date"] + timedelta(
                days=GESTATION_DAYS
            )
        if validated.get("estimated_calving_date") and not validated.get(
            "suggested_drying_off_date"
        ):
            validated["suggested_drying_off_date"] = validated[
                "estimated_calving_date"
            ] - timedelta(days=DRYING_OFF_DAYS_BEFORE_CALVING)
    elif model is HealthEvent:
        if validated.get("withdrawal_days") and not validated.get(
            "withdrawal_end_date"
        ):
            validated["withdrawal_end_date"] = validated["date"] + timedelta(
                days=validated["withdrawal_days"]
            )


class SyncBatchView(APIView):
    permission_classes = [HasFarmMembership]

    def post(self, request):
        farm_id = request.farm_membership.farm_id
        membership = request.farm_membership
        results = {}
        errors = {}

        authorized = {}
        for name, (model, serializer_class, min_role) in WRITE_COLLECTIONS.items():
            records = request.data.get(name, [])
            if not records:
                continue
            if ROLE_RANK[membership.role] < ROLE_RANK[min_role]:
                errors[name] = "Tu rol no puede escribir esta colección."
                continue
            authorized[name] = (model, serializer_class, records)

        if errors:
            return Response(
                {"detail": "Colecciones sin permiso.", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                for name, (model, serializer_class, records) in authorized.items():
                    validated_records = []
                    collection_errors = []
                    for record in records:
                        record_id = record.get("id")
                        if not record_id:
                            collection_errors.append(
                                {"record": record, "error": "Falta el id (UUID) del cliente."}
                            )
                            continue
                        data = {k: v for k, v in record.items() if k != "id"}
                        if model in CATALOG_MODELS:
                            data["farm"] = str(farm_id)
                        serializer = serializer_class(data=data)
                        if not serializer.is_valid():
                            collection_errors.append(
                                {"id": record_id, "error": serializer.errors}
                            )
                            continue
                        validated = dict(serializer.validated_data)
                        if model in EVENT_MODELS:
                            validated["farm_id"] = validated["animal"].farm_id
                        _apply_computed_fields(model, validated)
                        validated_records.append((str(record_id), validated))

                    if collection_errors:
                        errors[name] = collection_errors
                        raise ValueError(f"Errores de validación en {name}.")

                    if not validated_records:
                        continue

                    record_ids = [rid for rid, _ in validated_records]
                    existing_farms = {
                        str(row["id"]): row["farm_id"]
                        for row in model.objects.filter(id__in=record_ids).values(
                            "id", "farm_id"
                        )
                    }
                    for rid in record_ids:
                        if rid in existing_farms and existing_farms[rid] != farm_id:
                            raise ValueError(
                                f"El registro {rid} pertenece a otra finca."
                            )

                    animal_status = {}
                    if model in EVENT_MODELS:
                        animal_ids = {v["animal"].id for _, v in validated_records}
                        animal_status = {
                            str(a.id): a.status
                            for a in Animal.objects.filter(id__in=animal_ids).only(
                                "id", "status"
                            )
                        }

                    milking_merges = {}
                    if model is Milking:
                        keys = {
                            (v["animal"].id, v["date"], v["shift"])
                            for rid, v in validated_records
                            if rid not in existing_farms
                        }
                        if keys:
                            candidates = Milking.objects.filter(
                                animal_id__in=[k[0] for k in keys],
                                date__in=[k[1] for k in keys],
                            )
                            for m in candidates:
                                milking_merges[(m.animal_id, m.date, m.shift)] = m

                    to_create = []
                    to_update = []
                    update_fields = set()
                    entries = []
                    now = timezone.now()
                    batch_milking_keys = {}
                    for rid, validated in validated_records:
                        if model is Milking and rid not in existing_farms:
                            key = (
                                validated["animal"].id,
                                validated["date"],
                                validated["shift"],
                            )
                            existing_milking = milking_merges.get(key)
                            if existing_milking is not None:
                                existing_milking.liters = validated["liters"]
                                existing_milking.save()
                                entries.append(
                                    {
                                        "id": rid,
                                        "status": "updated",
                                        "merged_into": str(existing_milking.id),
                                    }
                                )
                                continue
                            pending_obj = batch_milking_keys.get(key)
                            if pending_obj is not None:
                                pending_obj.liters = validated["liters"]
                                entries.append(
                                    {
                                        "id": rid,
                                        "status": "updated",
                                        "merged_into": str(pending_obj.id),
                                    }
                                )
                                continue

                        obj_data = dict(validated)
                        obj_data["updated_at"] = now
                        obj = model(id=rid, **obj_data)
                        entry = {"id": rid, "status": None}
                        if rid in existing_farms:
                            to_update.append(obj)
                            update_fields.update(
                                k for k in obj_data.keys() if k != "farm_id"
                            )
                            entry["status"] = "updated"
                        else:
                            to_create.append(obj)
                            entry["status"] = "created"
                            if model is Milking:
                                batch_milking_keys[key] = obj
                        if (
                            model in EVENT_MODELS
                            and animal_status.get(str(validated["animal"].id))
                            != Animal.Status.ACTIVE
                        ):
                            entry["historical_warning"] = True
                        entries.append(entry)

                    if to_create:
                        model.objects.bulk_create(to_create)
                    if to_update:
                        model.objects.bulk_update(
                            to_update, fields=sorted(update_fields)
                        )

                    results[name] = entries
        except ValueError as exc:
            return Response(
                {"detail": str(exc), "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError as exc:
            return Response(
                {"detail": f"Conflicto de datos: {exc}", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"results": results}, status=status.HTTP_200_OK)
