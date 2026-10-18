"""Reconcile agreement/sale weight snapshots with the animal's weight ledger."""
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid5, NAMESPACE_URL
from django.utils import timezone


def reconcile_weights(farm_id, *, apps=None, using='default'):
    if apps:
        Weighing = apps.get_model('production', 'Weighing')
        Agreement = apps.get_model('livestock', 'AnimalAgreement')
        Sale = apps.get_model('livestock', 'AnimalSale')
        Animal = apps.get_model('livestock', 'Animal')
    else:
        from apps.production.models import Weighing
        from apps.livestock.models import AnimalAgreement as Agreement, AnimalSale as Sale, Animal
    animal_ids = {str(pk) for pk in Animal.objects.using(using).filter(farm_id=farm_id).values_list('id',flat=True)}
    expected = {}
    claimed = set()
    manual = {(str(w.animal_id),w.date,Decimal(w.weight_kg)) for w in Weighing.objects.using(using).filter(farm_id=farm_id,source_type='manual',voided=False)}

    def add(source, source_id, animal, day, weight):
        if not day or weight in (None,'') or animal not in animal_ids:
            return
        day = date.fromisoformat(day) if isinstance(day,str) else day
        weight = Decimal(weight)
        if not weight.is_finite() or weight <= 0:
            return
        key = (animal,day,weight)
        if key in manual or key in claimed:
            return
        claimed.add(key)
        pk = uuid5(NAMESPACE_URL,f'bovinonic:{source}:{source_id}:{animal}')
        expected[pk] = {'farm_id':farm_id,'animal_id':UUID(animal),'date':day,'weight_kg':weight,
                        'source_type':source,'source_id':UUID(str(source_id)),'voided':False}

    # A sale is the authoritative final observation, even after a weight correction.
    sales = list(Sale.objects.using(using).filter(farm_id=farm_id))
    sold = {(r.get('agreement'),r['animal']) for s in sales for r in s.lines if r.get('agreement')}
    for sale in sales:
        for row in sale.lines:
            add('sale',sale.id,row['animal'],sale.date,row['weight_kg'])
    for agreement in Agreement.objects.using(using).filter(farm_id=farm_id):
        for row in agreement.animals:
            add('agreement_initial',agreement.id,row['animal'],agreement.start_date,row.get('initial_weight'))
            if (str(agreement.id),row['animal']) not in sold:
                add('agreement_final',agreement.id,row['animal'],row.get('final_date'),row.get('final_weight'))
    current = {w.id:w for w in Weighing.objects.using(using).filter(farm_id=farm_id,source_type__in=['sale','agreement_initial','agreement_final'])}
    now = timezone.now()
    for pk, values in expected.items():
        row = current.get(pk)
        if row is None:
            Weighing.objects.using(using).create(id=pk,**values)
        elif any(getattr(row,key) != value for key,value in values.items()):
            Weighing.objects.using(using).filter(pk=pk).update(**values,updated_at=now)
    # Sync soft removals when dates/weights change or a matching manual reading exists.
    stale = set(current) - set(expected)
    if stale:
        Weighing.objects.using(using).filter(pk__in=stale,voided=False).update(voided=True,updated_at=now)
