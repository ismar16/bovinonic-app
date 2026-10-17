"""Immutable sale receipts. Call only inside the farm's locked sync transaction."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from uuid import UUID

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import Animal, AnimalAgreement, AnimalSale
from .agreements import amount, money, calculate_settlement


def allocated_expenses(agreement, animal_id):
    """Equal shares of common costs; original row order assigns remainder cents once."""
    ids = [r['animal'] for r in agreement.animals]
    index = ids.index(animal_id)
    result = []
    from .pasture import pasture_expenses
    for expense in agreement.expenses + pasture_expenses(agreement):
        if expense.get('animal') and expense['animal'] != animal_id:
            continue
        cents = int(Decimal(expense['amount']) * 100)
        if not expense.get('animal'):
            share, remainder = divmod(cents, len(ids))
            cents = share + (index < remainder)
        if cents:
            result.append({**expense, 'animal': animal_id, 'amount': money(Decimal(cents) / 100)})
    return result


def normalize_sale(attrs, farm_id, existing=None, accept_loss=False):
    if attrs['date'] > timezone.localdate():
        raise ValueError('La fecha de venta no puede ser futura.')
    raw_lines = attrs.get('lines')
    if not isinstance(raw_lines, list) or not 1 <= len(raw_lines) <= 200:
        raise ValueError('Seleccioná entre 1 y 200 animales para vender.')
    lines, seen = [], set()
    active = list(AnimalAgreement.objects.filter(farm_id=farm_id, status='active'))
    prior = {r['animal']: r for r in existing.lines} if existing else {}
    for raw in raw_lines:
        if not isinstance(raw, dict):
            raise ValueError('Revisá los animales de la venta.')
        aid = str(UUID(str(raw.get('animal', ''))))
        if aid in seen:
            raise ValueError('Un animal no puede aparecer dos veces en la venta.')
        seen.add(aid)
        animal = Animal.objects.filter(pk=aid, farm_id=farm_id).first()
        if not animal or (not existing and animal.status != 'active'):
            raise ValueError('Solo se pueden vender animales activos de esta finca.')
        if animal.birth_date and attrs['date'] < animal.birth_date:
            raise ValueError(f'{animal.tag}: la venta es anterior al nacimiento.')
        weight = format(amount(raw.get('weight_kg'), minimum=Decimal('.01'), maximum=Decimal('99999.99')), '.2f')
        price = format(amount(raw.get('price_per_kg'), minimum=Decimal('.01'), maximum=Decimal('9999999.99')), '.2f')
        extra = raw.get('expenses', [])
        if not isinstance(extra, list) or len(extra) > 200:
            raise ValueError('Revisá los gastos adicionales de la venta.')
        expenses = []
        for e in extra:
            if not isinstance(e, dict) or e.get('paid_by') not in ('owner', 'partner'):
                raise ValueError('Indicá quién pagó cada gasto adicional.')
            concept = str(e.get('concept', '')).strip()
            if not concept or len(concept) > 200:
                raise ValueError('Cada gasto necesita un concepto de hasta 200 caracteres.')
            expenses.append({'concept': concept, 'paid_by': e['paid_by'], 'amount': format(amount(e.get('amount'), minimum=Decimal('.01')), '.2f')})
        value = money(Decimal(weight) * Decimal(price))
        if Decimal(value) <= 0:
            raise ValueError('El importe del animal debe ser al menos 0.01.')
        agreement_id = str(UUID(str(raw['agreement']))) if raw.get('agreement') else None
        version = raw.get('agreement_version') or None
        line = {'animal': aid, 'weight_kg': weight, 'price_per_kg': price, 'agreement': agreement_id,
                'agreement_version': version, 'expenses': expenses}
        if existing:
            old = prior.get(aid)
            if not old or any(old.get(k) != v for k, v in line.items()):
                raise ValueError('Una venta confirmada no se puede modificar.')
            lines.append(deepcopy(old))
            continue
        if any(aid == r['animal'] for sale in AnimalSale.objects.filter(farm_id=farm_id) for r in sale.lines):
            raise ValueError(f'{animal.tag}: ya existe una venta para este animal.')
        agreement = next((a for a in active if any(r['animal'] == aid for r in a.animals)), None)
        if (str(agreement.id) if agreement else None) != agreement_id:
            raise ValueError(f'{animal.tag}: su acuerdo cambió. Sincronizá y revisá la venta.')
        if agreement:
            if not isinstance(version, str) or parse_datetime(version) != agreement.updated_at:
                raise ValueError('El acuerdo fue actualizado. Sincronizá y revisá pesos y gastos antes de vender.')
            if attrs['currency'] != agreement.currency or attrs['date'] < agreement.start_date:
                raise ValueError('La moneda y fecha de venta deben corresponder al acuerdo.')
        elif any(e['paid_by'] == 'partner' for e in expenses):
            raise ValueError('Los gastos sin acuerdo deben estar pagados por el propietario.')
        line.update(tag=animal.tag, name=animal.name, value=value, settlement=None,
                    agreement_title=agreement.title if agreement else '', partner_name=agreement.partner_name if agreement else '',
                    owner_name=agreement.owner_name if agreement else '', kind=agreement.kind if agreement else None)
        if agreement:
            row = next(r for r in agreement.animals if r['animal'] == aid)
            final_row = {**row, 'final_weight': weight, 'price_per_kg': price, 'final_date': attrs['date'].isoformat()}
            allocated = allocated_expenses(agreement, aid)
            line['allocated_expenses'] = allocated
            line['initial_weight'] = row.get('initial_weight')
            line['owner_share'] = str(agreement.owner_share)
            line['settlement'] = calculate_settlement(agreement.kind, [final_row], allocated + [{**e, 'animal': aid} for e in expenses], agreement.owner_share)
            if Decimal(line['settlement'].get('net_gain', '0')) < 0 and accept_loss is not True:
                raise ValueError('Hay una pérdida. Confirmá expresamente el reparto antes de vender.')
        lines.append(line)
    if existing and len(lines) != len(existing.lines):
        raise ValueError('Una venta confirmada no se puede modificar.')
    attrs['lines'] = lines
    attrs['total'] = sum((Decimal(r['value']) for r in lines), Decimal(0))
    amount(attrs['total'], minimum=Decimal('.01'))
    if existing and any(getattr(existing, k) != v for k, v in attrs.items()):
        raise ValueError('Una venta confirmada no se puede modificar.')
    return attrs


def effective_sale_lines(sale, extra=None):
    """Derive current balances from the original receipt plus append-only expenses."""
    adjustments = list(sale.expense_adjustments.order_by('created_at', 'id').values('id', 'animal_id', 'date', 'concept', 'amount', 'paid_by', 'created_at'))
    if extra:
        adjustments.append(extra)
    lines = deepcopy(sale.lines)
    for line in lines:
        added = [{'id': str(e.get('id', 'preview')), 'animal': str(e['animal_id']), 'date': e['date'].isoformat(),
                  'concept': e['concept'], 'amount': money(e['amount']), 'paid_by': e['paid_by'],
                  'created_at': e['created_at'].isoformat() if e.get('created_at') else None}
                 for e in adjustments if str(e['animal_id']) == line['animal']]
        line['subsequent_expenses'] = added
        rent = []
        if line.get('kind') == 'pasture' and line.get('agreement'):
            from .pasture import pasture_expenses
            original_ids = {e.get('id') for e in line.get('allocated_expenses', [])}
            rent = [e for e in pasture_expenses(AnimalAgreement.objects.get(pk=line['agreement'],farm_id=sale.farm_id)) if e['animal'] == line['animal'] and e['id'] not in original_ids]
        line['subsequent_pasture_costs'] = rent
        costs = line.get('allocated_expenses', []) + line['expenses'] + added + rent
        line['expenses_total'] = money(sum((Decimal(e['amount']) for e in costs), Decimal(0)))
        line['net_after_expenses'] = money(Decimal(line['value']) - Decimal(line['expenses_total']))
        if not added and not rent:
            continue
        line['original_settlement'] = deepcopy(line.get('settlement'))
        if line.get('agreement'):
            row = {'animal': line['animal'], 'initial_weight': line.get('initial_weight'),
                   'final_weight': line['weight_kg'], 'price_per_kg': line['price_per_kg']}
            line['settlement'] = calculate_settlement(line['kind'], [row], [{**e, 'animal': line['animal']} for e in costs], line['owner_share'])
    return lines


def apply_sale(sale):
    Animal.objects.filter(farm_id=sale.farm_id, pk__in=[r['animal'] for r in sale.lines]).update(
        status='sold', status_changed_at=sale.date, status_reason=f'Venta a {sale.buyer}', updated_at=timezone.now())
    refresh_sale_agreements(sale)


def refresh_sale_agreements(sale):
    for agreement_id in {r['agreement'] for r in sale.lines if r.get('agreement')}:
        agreement = AnimalAgreement.objects.get(pk=agreement_id, farm_id=sale.farm_id)
        receipts = [line for record in AnimalSale.objects.filter(farm_id=sale.farm_id).order_by('date', 'id') for line in effective_sale_lines(record) if line.get('agreement') == agreement_id]
        sold = {r['animal']: r for r in receipts}
        dates = {line['animal']: record.date.isoformat() for record in AnimalSale.objects.filter(farm_id=sale.farm_id) for line in record.lines if line.get('agreement') == agreement_id}
        agreement.animals = [{**row, **({'final_weight': sold[row['animal']]['weight_kg'], 'price_per_kg': sold[row['animal']]['price_per_kg'], 'final_date': dates[row['animal']]} if row['animal'] in sold else {})} for row in agreement.animals]
        # Keep original rows/terms and expenses immutable once a partial sale exists.
        # Final totals are sums of the actual receipts, preserving per-sale rounding.
        if {r['animal'] for r in agreement.animals}.issubset({r['animal'] for r in receipts}):
            settlements = [r['settlement'] for r in receipts]
            total = {'kind': agreement.kind}
            for key in settlements[0]:
                if key not in ('kind', 'lines'):
                    total[key] = money(sum((Decimal(s.get(key, '0')) for s in settlements), Decimal(0)))
            if agreement.kind != 'pasture':
                total['lines'] = [line for s in settlements for line in s['lines']]
            else:
                from .pasture import pasture_settlement
                total = pasture_settlement(agreement)
            agreement.status = 'settled'
            agreement.end_date = max(record.date for record in AnimalSale.objects.filter(farm_id=sale.farm_id) if any(r.get('agreement') == agreement_id for r in record.lines))
            agreement.settlement = total
        # Bump even on a partial sale so incremental pulls receive the receipts.
        agreement.save()
