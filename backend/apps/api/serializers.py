from decimal import Decimal
from datetime import date
from uuid import UUID
from django.utils import timezone

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.core.models import Farm, FarmMembership
from apps.health.models import HealthEvent
from apps.livestock.models import Animal, AnimalLot, AnimalAgreement, AnimalSale, SalePayment, SaleExpense, Brand, Owner, Paddock, PaddockMovement
from apps.livestock.agreements import amount, calculate_settlement
from apps.production.models import Milking, Weighing, DailyMilkProduction
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
            for name in ("animal", "mother", "father", "paddock", "destination", "owner", "brand", "title_owner", "lot"):
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
    area = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('.01'), allow_null=True, required=False)
    max_occupation_days = serializers.IntegerField(min_value=1, max_value=3650, allow_null=True, required=False)
    class Meta:
        model = Paddock
        fields = ["id", "farm", "name", "area", "area_unit", "max_occupation_days", "updated_at"]
        read_only_fields = ["updated_at"]
        validators = []


class AnimalLotSerializer(FarmScopedSerializer):
    class Meta:
        model = AnimalLot
        fields = ["id", "farm", "name", "description", "updated_at"]
        read_only_fields = ["updated_at"]
        validators = []


class PaddockMovementSerializer(FarmScopedSerializer):
    id = serializers.UUIDField()
    class Meta:
        model = PaddockMovement
        fields = ['id', 'farm', 'date', 'destination', 'lot', 'animals', 'notes', 'updated_at']
        read_only_fields = ['updated_at']

    def validate(self, attrs):
        try:
            record_id = UUID(str(self.context.get('record_id')))
            farm_id = self.context['farm_id']
            existing = PaddockMovement.objects.filter(pk=record_id).first()
            if existing:
                if existing.farm_id != farm_id or any(getattr(existing, key) != value for key, value in attrs.items()):
                    raise ValueError('Un traslado confirmado no se puede modificar. Registrá otro movimiento para corregir la ubicación.')
                return attrs
            if attrs['date'] > timezone.localdate():
                raise ValueError('La fecha del traslado no puede ser futura.')
            rows = attrs['animals']
            if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
                raise ValueError('Seleccioná entre 1 y 500 animales por traslado.')
            ids = [str(UUID(str(row['animal']))) for row in rows]
            if len(set(ids)) != len(ids):
                raise ValueError('Hay animales repetidos.')
            animals = {str(a.id): a for a in Animal.objects.filter(farm_id=farm_id, pk__in=ids)}
            for row, animal_id in zip(rows, ids):
                animal = animals.get(animal_id)
                if not animal or animal.status != 'active':
                    raise ValueError('Todos los animales deben estar activos y pertenecer a esta finca.')
                if attrs.get('lot') and animal.lot_id != attrs['lot'].id:
                    raise ValueError(f'{animal.tag}: ya no pertenece al lote seleccionado.')
                if set(row) != {'animal', 'from_paddock', 'previous_movement'}:
                    raise ValueError('Falta la ubicación de origen del animal. Volvé a seleccionar los animales.')
                if row['from_paddock'] != (str(animal.paddock_id) if animal.paddock_id else None) or row['previous_movement'] != (str(animal.paddock_movement) if animal.paddock_movement else None):
                    raise ValueError(f'{animal.tag}: su ubicación cambió en otro dispositivo. Revisá el traslado pendiente.')
                if animal.paddock_id == attrs['destination'].id:
                    raise ValueError(f'{animal.tag}: ya está en el potrero de destino.')
                if (animal.birth_date and attrs['date'] < animal.birth_date) or (animal.paddock_since and attrs['date'] < animal.paddock_since):
                    raise ValueError(f'{animal.tag}: la fecha es anterior al nacimiento o a su último traslado.')
            return attrs
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise serializers.ValidationError({'movement': str(exc) or 'Revisá el traslado.'})


class AnimalAgreementSerializer(FarmScopedSerializer):
    owner_share = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False, default=50)
    sale_receipts = serializers.SerializerMethodField()

    def get_sale_receipts(self, obj):
        return [{'sale': str(s.id), 'reference': s.reference, 'date': s.date.isoformat(), 'animals': [r['animal'] for r in s.lines if r.get('agreement') == str(obj.id)]}
                for s in AnimalSale.objects.filter(farm_id=obj.farm_id).order_by('date', 'id')
                if any(r.get('agreement') == str(obj.id) for r in s.lines)]

    class Meta:
        model = AnimalAgreement
        fields = ['id', 'farm', 'title', 'owner_name', 'partner_name', 'external_farm', 'kind',
                  'currency', 'owner_share', 'start_date', 'end_date', 'status', 'notes',
                  'animals', 'expenses', 'settlement', 'updated_at', 'sale_receipts']
        read_only_fields = ['settlement', 'updated_at']

    def validate(self, attrs):
        def iso(value, label):
            try:
                parsed = date.fromisoformat(value)
                if parsed.isoformat() != value or parsed > timezone.localdate() or parsed < start:
                    raise ValueError()
                return value
            except (ValueError, TypeError):
                raise ValueError(f'{label}: elegí una fecha entre el inicio del acuerdo y hoy.')

        try:
            record_id = str(UUID(str(self.context['record_id']))) if self.context.get('record_id') else None
            farm_id = self.context.get('farm_id') or attrs['farm'].pk
            existing = AnimalAgreement.objects.filter(pk=record_id, farm_id=farm_id).first() if record_id else None
            if existing and self.get_sale_receipts(existing):
                for field, value in attrs.items():
                    if getattr(existing, field) != value:
                        raise ValueError('Este acuerdo tiene ventas: sus condiciones y gastos originales quedan protegidos. Registrá nuevos gastos en la siguiente venta.')
                return {**attrs, 'settlement': existing.settlement}
            start = attrs['start_date']
            end = attrs.get('end_date')
            kind = attrs.get('kind', 'weight_gain')
            settled = attrs.get('status', 'active') == 'settled'
            if not settled:
                end = None
                attrs['end_date'] = None
            if start > timezone.localdate() or (end and (end < start or end > timezone.localdate())):
                raise ValueError('Revisá las fechas de inicio y cierre del acuerdo.')
            if settled and not end:
                raise ValueError('Indicá la fecha de liquidación.')
            rows = attrs.get('animals', [])
            expenses = attrs.get('expenses', [])
            if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
                raise ValueError('Seleccioná entre 1 y 500 animales.')
            if not isinstance(expenses, list) or len(expenses) > 2000:
                raise ValueError('La lista de gastos no es válida (máximo 2000).')
            normalized = []
            ids = set()
            if any(not isinstance(row, dict) for row in rows):
                raise ValueError('Los datos de animales no son válidos.')
            requested_ids = [str(UUID(str(row.get('animal', '')))) for row in rows]
            animals_by_id = {str(animal.id): animal for animal in Animal.objects.filter(farm_id=farm_id, pk__in=requested_ids)}
            prior_rows = {r['animal']: r for r in existing.animals} if existing else {}
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    raise ValueError('Los datos de animales no son válidos.')
                animal_id = str(UUID(str(row.get('animal', ''))))
                if animal_id in ids:
                    raise ValueError('Un animal no puede aparecer dos veces en el mismo acuerdo.')
                ids.add(animal_id)
                animal = animals_by_id.get(animal_id)
                if not animal:
                    raise ValueError('Todos los animales deben pertenecer al hato de esta finca.')
                if animal.birth_date and start < animal.birth_date and not (existing and existing.status == 'settled'):
                    raise ValueError(f'{animal.tag}: el acuerdo no puede iniciar antes de su nacimiento.')
                prior = prior_rows.get(animal_id)
                if not prior and animal.status != 'active':
                    raise ValueError(f'{animal.tag}: solo se pueden entregar animales activos.')
                item = {'animal': animal_id, 'tag': prior['tag'] if existing and existing.status == 'settled' and prior else animal.tag,
                        'name': prior.get('name', '') if existing and existing.status == 'settled' and prior else animal.name}
                for field in ['initial_weight', 'final_weight', 'price_per_kg']:
                    raw = row.get(field)
                    required = (field == 'initial_weight' and kind == 'weight_gain') or (settled and kind != 'pasture' and field in ('final_weight', 'price_per_kg'))
                    item[field] = format(amount(raw, minimum=Decimal('.01'), maximum=Decimal('99999.99') if 'weight' in field else Decimal('9999999.99')), '.2f') if raw not in (None, '') else None
                    if required and item[field] is None:
                        raise ValueError(f'{animal.tag}: completá el peso inicial, peso final y precio que requiere esta modalidad.')
                item['final_date'] = iso(row['final_date'], animal.tag) if row.get('final_date') else None
                if settled and kind != 'pasture' and not item['final_date']:
                    raise ValueError(f'{animal.tag}: indicá la fecha del pesaje final o venta.')
                if end and item['final_date'] and date.fromisoformat(item['final_date']) > end:
                    raise ValueError('Un pesaje final no puede ser posterior al cierre.')
                normalized.append(item)
            ledger = []
            expense_ids = set()
            for expense in expenses:
                if not isinstance(expense, dict):
                    raise ValueError('Los datos de gastos no son válidos.')
                expense_id = str(UUID(str(expense.get('id', ''))))
                if expense_id in expense_ids:
                    raise ValueError('Hay gastos repetidos en el acuerdo.')
                expense_ids.add(expense_id)
                concept = str(expense.get('concept', '')).strip()
                if not concept or len(concept) > 200 or expense.get('paid_by') not in ('owner', 'partner'):
                    raise ValueError('Cada gasto necesita concepto (hasta 200 caracteres) y quién lo pagó.')
                animal_id = expense.get('animal') or None
                if animal_id and animal_id not in ids:
                    raise ValueError('El animal del gasto debe estar incluido en el acuerdo.')
                day = iso(expense.get('date'), 'Gasto')
                if end and date.fromisoformat(day) > end:
                    raise ValueError('No se pueden incluir gastos posteriores al cierre.')
                ledger.append({'id': expense_id, 'date': day, 'concept': concept,
                               'amount': format(amount(expense.get('amount'), minimum=Decimal('.01')), '.2f'),
                               'paid_by': expense['paid_by'], 'animal': animal_id})
            attrs['animals'], attrs['expenses'] = normalized, ledger
            attrs['settlement'] = calculate_settlement(kind, normalized, ledger, attrs['owner_share']) if settled else None
            if settled and kind != 'pasture' and Decimal(attrs['settlement']['net_gain']) < 0 and not ((existing and existing.status == 'settled') or self.initial_data.get('accept_loss') is True):
                raise ValueError('La liquidación tiene saldo negativo. Confirmá expresamente su reparto antes de cerrar.')
            if existing and existing.status == 'settled':
                for field, value in attrs.items():
                    if field != 'settlement' and getattr(existing, field) != value:
                        raise ValueError('Un acuerdo liquidado no se puede modificar. Su liquidación se conserva como historial.')
                return attrs
            for other in AnimalAgreement.objects.filter(farm_id=farm_id, status='active').exclude(pk=record_id):
                if ids.intersection(r['animal'] for r in other.animals) and (not end or other.start_date <= end):
                    raise ValueError(f'Hay animales incluidos en otro acuerdo en curso: {other.title}.')
            return attrs
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise serializers.ValidationError({'agreement': str(exc) or 'Revisá los datos del acuerdo.'})


class AnimalSerializer(FarmScopedSerializer):
    def validate(self, attrs):
        record_id = str(self.context.get('record_id', ''))
        existing = Animal.objects.filter(pk=record_id, farm_id=self.context.get('farm_id')).first() if record_id else None
        if existing and attrs.get('paddock') != existing.paddock:
            raise serializers.ValidationError({'paddock': 'La ubicación cambió o requiere un traslado. Sincronizá y usá Mover animales para conservar el historial.'})
        sold = any(r['animal'] == record_id for s in AnimalSale.objects.filter(farm_id=self.context.get('farm_id')) for r in s.lines)
        if sold and (attrs.get('status') != 'sold' or attrs.get('status_changed_at') != Animal.objects.get(pk=record_id).status_changed_at):
            raise serializers.ValidationError('Este animal tiene una venta confirmada y no puede volver al hato activo ni cambiar su fecha de venta.')
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
            "status_changed_at", "status_reason", "photo_url", "updated_at", "paddock_since", "paddock_movement",
        ]
        read_only_fields = ["updated_at", "paddock_since", "paddock_movement"]

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

    def validate(self, attrs):
        attrs = super().validate(attrs)
        existing = Weighing.objects.filter(pk=self.context.get('record_id')).first() if self.context.get('record_id') else None
        if existing and existing.source_type != 'manual':
            raise serializers.ValidationError('Este peso está vinculado a un acuerdo o venta. Se corrige desde su registro de origen.')
        return attrs

    class Meta:
        model = Weighing
        fields = ["id", "animal", "date", "weight_kg", "updated_at", "historical_warning", 'source_type','source_id','voided']
        read_only_fields = ["updated_at", "historical_warning", 'source_type','source_id','voided']


class MilkingSerializer(AnimalEventSerializer):
    liters = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0"))
    class Meta:
        model = Milking
        fields = ["id", "animal", "date", "shift", "liters", "updated_at", "historical_warning"]
        read_only_fields = ["updated_at", "historical_warning"]
        validators = []


class DailyMilkProductionSerializer(FarmScopedSerializer):
    liters = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal('0'))

    class Meta:
        model = DailyMilkProduction
        fields = ['id', 'farm', 'date', 'liters', 'notes', 'updated_at']
        read_only_fields = ['updated_at']
        validators = []

    def validate(self, attrs):
        if attrs['date'] > timezone.localdate():
            raise serializers.ValidationError('La fecha de producción no puede ser futura.')
        attrs.setdefault('notes', '')
        try:
            record_id = UUID(str(self.context['record_id']))
        except (ValueError, KeyError):
            raise serializers.ValidationError('Identificador de producción inválido.')
        existing = DailyMilkProduction.objects.filter(pk=record_id).first()
        if existing and (existing.farm_id != self.context['farm_id'] or existing.date != attrs['date']):
            raise serializers.ValidationError('El registro pertenece a otra finca o fecha. Abrí el día que querés corregir.')
        return attrs


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


class AnimalSaleSerializer(FarmScopedSerializer):
    reference = serializers.CharField(read_only=True)
    def to_representation(self, instance):
        from apps.livestock.sales import effective_sale_lines
        result = super().to_representation(instance)
        result['lines'] = effective_sale_lines(instance)
        return result

    class Meta:
        model = AnimalSale
        fields = ['id', 'farm', 'number', 'reference', 'date', 'buyer', 'buyer_phone', 'currency', 'notes', 'lines', 'total', 'updated_at']
        read_only_fields = ['number', 'reference', 'total', 'updated_at']

    def validate(self, attrs):
        from apps.livestock.sales import normalize_sale
        try:
            record_id = UUID(str(self.context['record_id']))
            existing = AnimalSale.objects.filter(pk=record_id).first()
            if existing and existing.farm_id != self.context['farm_id']:
                raise ValueError('La venta pertenece a otra finca.')
            for field in ['buyer_phone', 'notes']:
                attrs.setdefault(field, '')
            return normalize_sale(attrs, self.context['farm_id'], existing, self.initial_data.get('accept_loss'))
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise serializers.ValidationError({'sale': str(exc) or 'Revisá los datos de la venta.'})


class SalePaymentSerializer(FarmScopedSerializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal('.01'))

    class Meta:
        model = SalePayment
        fields = ['id', 'farm', 'sale', 'date', 'amount', 'method', 'reference', 'updated_at']
        read_only_fields = ['updated_at']

    def validate(self, attrs):
        sale = attrs['sale']
        if sale.farm_id != self.context['farm_id']:
            raise serializers.ValidationError('La venta pertenece a otra finca.')
        if not sale.date <= attrs['date'] <= timezone.localdate():
            raise serializers.ValidationError('La fecha del abono debe estar entre la venta y hoy.')
        attrs.setdefault('reference', '')
        try:
            existing = SalePayment.objects.filter(pk=UUID(str(self.context['record_id']))).first()
        except ValueError:
            raise serializers.ValidationError('El identificador del abono no es válido.')
        if existing:
            if any(getattr(existing, k) != v for k, v in attrs.items()):
                raise serializers.ValidationError('Un abono confirmado no se puede modificar.')
        else:
            paid = sum((p.amount for p in sale.payments.all()), Decimal(0))
            if paid + attrs['amount'] > sale.total:
                raise serializers.ValidationError('El abono supera el saldo pendiente de esta venta.')
        return attrs


class SaleExpenseSerializer(FarmScopedSerializer):
    amount = serializers.DecimalField(max_digits=11, decimal_places=2, min_value=Decimal('.01'))

    class Meta:
        model = SaleExpense
        fields = ['id', 'farm', 'sale', 'animal', 'date', 'concept', 'amount', 'paid_by', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        from apps.livestock.sales import effective_sale_lines
        sale, animal = attrs['sale'], attrs['animal']
        if sale.farm_id != self.context['farm_id'] or animal.farm_id != self.context['farm_id']:
            raise serializers.ValidationError('La venta y el animal deben pertenecer a esta finca.')
        line = next((r for r in sale.lines if r['animal'] == str(animal.id)), None)
        if not line:
            raise serializers.ValidationError('Seleccioná un animal incluido en esta venta.')
        if attrs['date'] > timezone.localdate() or (animal.birth_date and attrs['date'] < animal.birth_date):
            raise serializers.ValidationError('La fecha del gasto debe estar entre el nacimiento y hoy.')
        if not line.get('agreement') and attrs['paid_by'] != 'owner':
            raise serializers.ValidationError('Sin acuerdo, el gasto corresponde al propietario.')
        try:
            existing = SaleExpense.objects.filter(pk=UUID(str(self.context['record_id']))).first()
        except ValueError:
            raise serializers.ValidationError('Identificador de gasto inválido.')
        if existing:
            if any(getattr(existing, k) != v for k, v in attrs.items()):
                raise serializers.ValidationError('Un gasto confirmado no se puede modificar. Se conserva en el historial.')
            return attrs
        extra = {**attrs, 'animal_id': animal.id}
        calculated = next(r for r in effective_sale_lines(sale, extra) if r['animal'] == str(animal.id))
        if Decimal((calculated.get('settlement') or {}).get('net_gain', '0')) < 0 and self.initial_data.get('accept_loss') is not True:
            raise serializers.ValidationError('El gasto deja una pérdida. Confirmá expresamente su reparto para guardarlo.')
        return attrs
