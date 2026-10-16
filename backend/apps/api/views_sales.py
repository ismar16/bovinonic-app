from uuid import UUID
from rest_framework.views import APIView
from rest_framework.response import Response
from .permissions import HasFarmMembership, IsAdmin
from .serializers import AnimalSaleSerializer, SalePaymentSerializer
from apps.livestock.models import AnimalSale, SalePayment


class FinancialReceiptView(APIView):
    """Read one authoritative receipt without uploading a potentially stale outbox."""
    permission_classes = [HasFarmMembership, IsAdmin]

    def get(self, request):
        definitions = {'sales': (AnimalSale, AnimalSaleSerializer), 'sale_payments': (SalePayment, SalePaymentSerializer)}
        definition = definitions.get(request.query_params.get('collection'))
        try:
            record_id = UUID(request.query_params.get('id', ''))
        except ValueError:
            return Response({'detail': 'Identificador inválido.'}, status=400)
        if not definition:
            return Response({'detail': 'Colección inválida.'}, status=400)
        model, serializer = definition
        record = model.objects.filter(pk=record_id, farm_id=request.farm_membership.farm_id).first()
        return Response({'record': serializer(record).data if record else None})
