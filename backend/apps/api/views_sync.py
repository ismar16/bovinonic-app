from django.db import transaction
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import FarmMembership
from apps.health.models import HealthEvent
from apps.livestock.models import Animal, Brand, Owner, Paddock
from apps.production.models import Milking, Weighing
from apps.reproduction.models import ReproductiveEvent

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


class SyncBatchView(APIView):
    permission_classes = [HasFarmMembership]

    def post(self, request):
        farm_id = request.farm_membership.farm_id
        membership = request.farm_membership
        results = {}
        errors = {}

        try:
            with transaction.atomic():
                for name, (model, serializer_class, min_role) in WRITE_COLLECTIONS.items():
                    records = request.data.get(name, [])
                    if not records:
                        continue
                    if ROLE_RANK[membership.role] < ROLE_RANK[min_role]:
                        errors[name] = "Tu rol no puede escribir esta colección."
                        continue

                    collection_results = []
                    collection_errors = []
                    for record in records:
                        record_id = record.get("id")
                        if not record_id:
                            collection_errors.append(
                                {"record": record, "error": "Falta el id (UUID) del cliente."}
                            )
                            continue
                        data = {k: v for k, v in record.items() if k != "id"}
                        if model is Animal:
                            data["farm"] = str(farm_id)
                        serializer = serializer_class(data=data)
                        if not serializer.is_valid():
                            collection_errors.append(
                                {"id": record_id, "error": serializer.errors}
                            )
                            continue
                        validated = dict(serializer.validated_data)
                        if model is not Animal:
                            validated.pop("farm", None)
                        obj, created = model.objects.update_or_create(
                            id=record_id, defaults=validated
                        )
                        if obj.farm_id != farm_id:
                            raise ValueError(
                                f"El registro {record_id} pertenece a otra finca."
                            )
                        entry = {"id": str(obj.id), "status": "created" if created else "updated"}
                        if model is not Animal and obj.animal.status != Animal.Status.ACTIVE:
                            entry["historical_warning"] = True
                        collection_results.append(entry)

                    if collection_errors:
                        errors[name] = collection_errors
                        raise ValueError(f"Errores de validación en {name}.")
                    results[name] = collection_results

                if errors:
                    raise ValueError("El lote contiene colecciones sin permiso o con errores.")
        except ValueError as exc:
            response = {"detail": str(exc), "errors": errors}
            return Response(response, status=status.HTTP_400_BAD_REQUEST)

        return Response({"results": results}, status=status.HTTP_200_OK)
