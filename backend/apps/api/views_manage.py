from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import FarmMembership

from .permissions import HasFarmMembership, IsAdmin

User = get_user_model()

VALID_ROLES = {choice.value for choice in FarmMembership.Role}


class FarmUsersView(APIView):
    permission_classes = [HasFarmMembership, IsAdmin]

    def get(self, request):
        memberships = (
            FarmMembership.objects.filter(farm=request.farm_membership.farm)
            .select_related("user")
            .order_by("user__username")
        )
        return Response(
            [
                {
                    "id": str(m.id),
                    "username": m.user.username,
                    "role": m.role,
                    "is_active": m.user.is_active,
                }
                for m in memberships
            ]
        )

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        role = request.data.get("role") or ""

        if not username or not password:
            return Response(
                {"detail": "Usuario y contraseña son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if role not in VALID_ROLES:
            return Response(
                {"detail": f"Rol inválido. Válidos: {sorted(VALID_ROLES)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(password) < 8:
            return Response(
                {"detail": "La contraseña debe tener al menos 8 caracteres."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User(username=username)
        try:
            user.full_clean(exclude=['password'])
            validate_password(password, user=user)
        except ValidationError as exc:
            return Response({'detail': ' '.join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                user.set_password(password)
                user.save()
                FarmMembership.objects.create(user=user, farm=request.farm_membership.farm, role=role)
        except IntegrityError:
            return Response({'detail': 'Ese usuario ya existe. Elegí otro nombre.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"detail": "ok", "username": user.username, "role": role},
            status=status.HTTP_201_CREATED,
        )
