"""Append-only records of rent already paid, never bank transfers."""
from calendar import monthrange
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid5, NAMESPACE_URL
from django.utils import timezone
from .models import Animal, AnimalSale, SaleExpense, PasturePayment
from .agreements import amount, money, calculate_settlement


def pasture_expenses(agreement):
    if agreement.kind != 'pasture':
        return []
    return [{'id':str(uuid5(NAMESPACE_URL,f'bovinonic:rent:{p.id}:{row["animal"]}')),
             'date':p.date.isoformat(),'concept':f'Alquiler {p.period:%Y-%m}',
             'amount':money(p.price_per_animal),'paid_by':'owner','animal':row['animal']}
            for p in PasturePayment.objects.filter(agreement=agreement).order_by('period','id') for row in p.animals]


def normalize_pasture_payment(attrs, farm_id, existing=None):
    ids = [str(i) for i in attrs.pop('animal_ids')]
    if not ids or len(ids) > 500 or len(set(ids)) != len(ids):
        raise ValueError('Seleccioná entre 1 y 500 animales distintos.')
    if existing:
        if existing.farm_id != farm_id or set(ids) != {r['animal'] for r in existing.animals} or any(getattr(existing,k) != v for k,v in attrs.items()):
            raise ValueError('Un pago confirmado no se puede modificar. Su comprobante se conserva como historial.')
        return {**attrs, 'animals':existing.animals,'total':existing.total,'currency':existing.currency,'recipient':existing.recipient}
    agreement = attrs['agreement']
    if agreement.kind != 'pasture':
        raise ValueError('Las mensualidades corresponden únicamente a acuerdos de pasto alquilado.')
    period, paid = attrs['period'], attrs['date']
    end_month = date(period.year,period.month,monthrange(period.year,period.month)[1])
    if period.day != 1 or period > timezone.localdate().replace(day=1) or end_month < agreement.start_date or (agreement.end_date and period > agreement.end_date):
        raise ValueError('Elegí un mes transcurrido o actual que corresponda al período del acuerdo.')
    if paid > timezone.localdate() or paid < agreement.start_date or paid < period:
        raise ValueError('La fecha de pago debe estar entre el inicio del mes/acuerdo y hoy.')
    members = {r['animal']:r for r in agreement.animals}
    animals = {str(a.id):a for a in Animal.objects.filter(farm_id=farm_id,pk__in=ids)}
    sales = {r['animal']:s.date for s in AnimalSale.objects.filter(farm_id=farm_id) for r in s.lines if r.get('agreement') == str(agreement.id)}
    already = {r['animal'] for p in PasturePayment.objects.filter(agreement=agreement,period=period) for r in p.animals}
    rows = []
    for animal_id in ids:
        animal = animals.get(animal_id)
        if animal_id not in members or not animal:
            raise ValueError('Todos los animales deben pertenecer a este acuerdo y finca.')
        if animal_id in already:
            raise ValueError(f'{animal.tag}: la mensualidad de ese mes ya está registrada.')
        exit_date = sales.get(animal_id) or (animal.status_changed_at if animal.status != 'active' else None)
        if (exit_date and exit_date < period) or (animal.birth_date and animal.birth_date > end_month):
            raise ValueError(f'{animal.tag}: no corresponde incluirlo en ese mes.')
        rows.append({'animal':animal_id,'tag':members[animal_id]['tag'],'name':members[animal_id].get('name','')})
    attrs.update(animals=rows,total=amount(attrs['price_per_animal']*len(rows),minimum=Decimal('.01')),currency=agreement.currency,recipient=agreement.partner_name)
    return attrs


def pasture_settlement(agreement):
    extra = []
    for sale in AnimalSale.objects.filter(farm_id=agreement.farm_id):
        ids = {r['animal'] for r in sale.lines if r.get('agreement') == str(agreement.id)}
        extra.extend(e for r in sale.lines if r['animal'] in ids for e in r['expenses'])
        extra.extend({'amount':money(e.amount),'paid_by':e.paid_by} for e in SaleExpense.objects.filter(sale=sale,animal_id__in=ids))
    return calculate_settlement('pasture',agreement.animals,agreement.expenses+pasture_expenses(agreement)+extra,agreement.owner_share)


def refresh_pasture_payment(payment):
    agreement = payment.agreement
    related = [s for s in AnimalSale.objects.filter(farm_id=payment.farm_id) if any(r.get('agreement') == str(agreement.id) for r in s.lines)]
    for sale in related:
        AnimalSale.objects.filter(pk=sale.pk).update(updated_at=timezone.now())
    if agreement.status == 'settled':
        agreement.settlement = pasture_settlement(agreement)
        agreement.save()
    else:
        type(agreement).objects.filter(pk=agreement.pk).update(updated_at=timezone.now())
