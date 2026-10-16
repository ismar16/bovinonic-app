"""User-agreed settlement rule. Decimal money, two-decimal kg and prices."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def amount(value, *, minimum=Decimal('0'), maximum=Decimal('999999999.99')):
    if isinstance(value, bool):
        raise ValueError('Ingresá una cantidad numérica válida.')
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < minimum or number > maximum or number != number.quantize(Decimal('.01')):
            raise ValueError('Revisá el importe: hasta dos decimales y dentro del rango permitido.')
    except (InvalidOperation, TypeError):
        raise ValueError('Ingresá una cantidad numérica válida.')
    return number


def money(value):
    return format(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP), '.2f')


def calculate_settlement(kind, animals, expenses, owner_share):
    """Return amounts, never execute payments or change ownership/status."""
    owner_cost = sum((Decimal(e['amount']) for e in expenses if e['paid_by'] == 'owner'), Decimal(0))
    partner_cost = sum((Decimal(e['amount']) for e in expenses if e['paid_by'] == 'partner'), Decimal(0))
    cost = owner_cost + partner_cost
    if kind == 'pasture':
        return {'kind': kind, 'expenses': money(cost), 'owner_paid': money(owner_cost),
                'partner_paid': money(partner_cost), 'partner_reimbursement': money(partner_cost)}
    lines = []
    sale = gain = initial = Decimal(0)
    for row in animals:
        final_weight = Decimal(row['final_weight'])
        price = Decimal(row['price_per_kg'])
        initial_weight = Decimal(row['initial_weight']) if kind == 'weight_gain' else Decimal(0)
        sale_value = Decimal(money(final_weight * price))
        gain_value = Decimal(money((final_weight - initial_weight) * price))
        initial_value = sale_value - gain_value
        own_expenses = sum((Decimal(e['amount']) for e in expenses if e.get('animal') == row['animal']), Decimal(0))
        lines.append({'animal': row['animal'], 'gain_kg': money(final_weight - initial_weight),
                      'sale_value': money(sale_value), 'initial_value': money(initial_value),
                      'gain_value': money(gain_value), 'assigned_expenses': money(own_expenses)})
        sale += sale_value
        gain += gain_value
        initial += initial_value
    net = gain - cost
    owner_part = Decimal(money(net * Decimal(str(owner_share)) / 100))
    partner_part = net - owner_part
    return {'kind': kind, 'lines': lines, 'sale_value': money(sale), 'initial_value': money(initial),
            'gain_value': money(gain), 'expenses': money(cost), 'net_gain': money(net),
            'owner_paid': money(owner_cost), 'partner_paid': money(partner_cost),
            'owner_part': money(owner_part), 'partner_part': money(partner_part),
            'owner_total': money(initial + owner_cost + owner_part),
            'partner_total': money(partner_cost + partner_part)}
