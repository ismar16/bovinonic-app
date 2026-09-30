from rest_framework.permissions import BasePermission

from apps.core.models import FarmMembership


def get_membership(user, farm_id):
    if not user.is_authenticated or not farm_id:
        return None
    return FarmMembership.objects.filter(user=user, farm_id=farm_id).first()


class HasFarmMembership(BasePermission):
    message = "No tenés acceso a esta finca."

    def has_permission(self, request, view):
        farm_id = (
            request.headers.get("X-Farm-Id")
            or request.query_params.get("farm")
            or request.data.get("farm")
            or request.data.get("farm_id")
        )
        membership = get_membership(request.user, farm_id)
        if membership is None:
            return False
        request.farm_membership = membership
        return True


class MinimumRole(BasePermission):
    minimum = None
    role_rank = {
        FarmMembership.Role.OPERATOR: 1,
        FarmMembership.Role.TECHNICIAN: 2,
        FarmMembership.Role.ADMIN: 3,
    }
    message = "Tu rol no tiene permisos suficientes para esta acción."

    def has_permission(self, request, view):
        membership = getattr(request, "farm_membership", None)
        if membership is None:
            return False
        return self.role_rank[membership.role] >= self.role_rank[self.minimum]


class IsTechnicianOrAbove(MinimumRole):
    minimum = FarmMembership.Role.TECHNICIAN


class IsAdmin(MinimumRole):
    minimum = FarmMembership.Role.ADMIN
