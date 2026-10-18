from uuid import UUID
from rest_framework.views import APIView
from rest_framework.response import Response
from .permissions import HasFarmMembership
from .serializers import AnimalSaleSerializer, SalePaymentSerializer, SaleExpenseSerializer, PaddockMovementSerializer, PasturePaymentSerializer, CalvingRecordSerializer
from apps.reproduction.models import CalvingRecord
from apps.livestock.models import AnimalSale, SalePayment, SaleExpense, PaddockMovement, PasturePayment


class FinancialReceiptView(APIView):
    """Read one authoritative receipt without uploading a potentially stale outbox."""
    permission_classes = [HasFarmMembership]

    def get(self, request):
        collection = request.query_params.get('collection')
        role = request.farm_membership.role
        if role != 'admin' and not (role == 'technician' and collection in ('paddock_movements','calvings')):
            return Response({'detail': 'Tu rol no permite revisar este registro.'}, status=403)
        definitions = {'calvings': (CalvingRecord, CalvingRecordSerializer), 'pasture_payments': (PasturePayment, PasturePaymentSerializer), 'paddock_movements': (PaddockMovement, PaddockMovementSerializer), 'sales': (AnimalSale, AnimalSaleSerializer), 'sale_payments': (SalePayment, SalePaymentSerializer), 'sale_expenses': (SaleExpense, SaleExpenseSerializer)}
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
