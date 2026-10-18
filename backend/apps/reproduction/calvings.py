"""Complete calving records. Caller holds the farm sync transaction lock."""
from decimal import Decimal
from uuid import UUID, uuid5, NAMESPACE_URL
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from apps.livestock.models import Animal, AnimalLot, Paddock, Owner, PaddockMovement
from apps.livestock.agreements import amount, money
from apps.production.models import Weighing
from .models import CalvingRecord, ReproductiveEvent


def normalize_calving(attrs, farm_id, record_id):
    def uuid(value):
        return str(UUID(str(value))) if value else None
    record_id = UUID(str(record_id))
    attrs.setdefault('notes','');attrs.setdefault('delivery','normal');attrs.setdefault('maternal_status','keep')
    rows = attrs.get('calves')
    if not isinstance(rows,list) or not 1 <= len(rows) <= 5:
        raise ValueError('Registrá entre una y cinco crías en este parto.')
    normalized=[];seen=set()
    for row in rows:
        if not isinstance(row,dict) or row.get('mode') not in ('new','existing','stillborn'):
            raise ValueError('Elegí registrar, vincular o indicar nacido muerto para cada cría.')
        mode=row['mode'];aid=uuid(row.get('animal')) if mode!='stillborn' else None
        if mode!='stillborn' and (not aid or aid in seen):raise ValueError('Cada cría viva necesita una identificación distinta.')
        if aid:seen.add(aid)
        item={'mode':mode,'animal':aid,'weight_kg':money(amount(row['weight_kg'],minimum=Decimal('.01'),maximum=Decimal('99999.99'))) if row.get('weight_kg') not in (None,'') else None}
        if mode!='existing':
            sex=row.get('sex');tag=str(row.get('tag','')).strip() if mode=='new' else '';name=str(row.get('name','')).strip()
            if sex not in (('M','H','unknown') if mode=='stillborn' else ('M','H')) or len(tag)>50 or len(name)>150:raise ValueError('Revisá el sexo, arete y nombre de la cría.')
            item.update(sex=sex,tag=tag,name=name)
        normalized.append(item)
    loc=attrs.get('location',{})
    if not isinstance(loc,dict):raise ValueError('Revisá los datos de ubicación.')
    location={k:uuid(loc.get(k)) for k in ('mother_lot','mother_paddock','calf_lot','calf_paddock','calf_owner')}
    for key in ('change_mother_lot','change_mother_paddock'):
        if type(loc.get(key,False)) is not bool:raise ValueError('Revisá los cambios de ubicación.')
        location[key]=loc.get(key,False)
    attrs['calves']=normalized;attrs['location']=location
    existing=CalvingRecord.objects.filter(pk=record_id).first()
    if existing:
        if existing.farm_id!=farm_id or any(getattr(existing,k)!=v for k,v in attrs.items()):raise ValueError('Este parto ya está confirmado y su historial está protegido.')
        return attrs
    mother=attrs['mother'];day=attrs['date']
    if mother.sex!='H' or day>timezone.localdate() or (mother.birth_date and day<=mother.birth_date):raise ValueError('Elegí una hembra y una fecha posterior a su nacimiento, hasta hoy.')
    if parse_datetime(attrs['mother_version'])!=mother.updated_at:raise ValueError('La ficha de la madre cambió. Sincronizá y revisá el parto pendiente.')
    changes=attrs['maternal_status']!='keep' or location['change_mother_lot'] or location['change_mother_paddock']
    if mother.status!='active' and (changes or not mother.status_changed_at or day>mother.status_changed_at):raise ValueError('Para una madre inactiva, registrá solo el parto histórico anterior a su salida y conservá su situación.')
    if CalvingRecord.objects.filter(farm_id=farm_id,mother=mother,date=day).exists():raise ValueError('Ya hay un parto registrado para esta madre en esa fecha. Revisá su historial antes de continuar.')
    if changes and ReproductiveEvent.objects.filter(farm_id=farm_id,animal=mother,type='calving',date__gt=day).exists():raise ValueError('Hay un parto posterior: registrá este como histórico sin cambiar la situación actual de la vaca.')
    for key,model in [('mother_lot',AnimalLot),('calf_lot',AnimalLot),('mother_paddock',Paddock),('calf_paddock',Paddock),('calf_owner',Owner)]:
        if location[key] and not model.objects.filter(pk=location[key],farm_id=farm_id).exists():raise ValueError('El propietario, lote y potrero deben pertenecer a esta finca.')
    if location['change_mother_paddock'] and location['mother_paddock']!=(str(mother.paddock_id) if mother.paddock_id else None):
        if not location['mother_paddock']:raise ValueError('Elegí un potrero de destino para trasladar a la madre.')
        if mother.paddock_since and day<mother.paddock_since:raise ValueError('El traslado no puede ser anterior al último ingreso de la madre a su potrero.')
    for row in normalized:
        aid=row['animal']
        if row['mode']=='new':
            tag=row['tag'] or f'TEMP-{record_id.hex[:8]}-{UUID(aid).hex[:6]}'
            if Animal.objects.filter(pk=aid).exists() or Animal.objects.filter(tag__iexact=tag).exists():raise ValueError(f'{tag}: ya está registrado. Usá la opción Vincular existente.')
        elif row['mode']=='existing':
            calf=Animal.objects.filter(pk=aid,farm_id=farm_id).first()
            if not calf or calf.id==mother.id or calf.birth_record or (calf.mother_id and calf.mother_id!=mother.id) or (calf.birth_date and calf.birth_date!=day):raise ValueError('La cría existente debe ser de esta finca, sin otro parto/madre y con nacimiento compatible con la fecha elegida.')
            ancestor=mother;visited=set()
            while ancestor and ancestor.id not in visited:
                if str(ancestor.id)==aid:raise ValueError('El parentesco seleccionado formaría un ciclo. Revisá la madre y la cría.')
                visited.add(ancestor.id);ancestor=ancestor.mother
    tags=[r['tag'].casefold() for r in normalized if r['mode']=='new' and r['tag']]
    if len(tags)!=len(set(tags)):raise ValueError('Las crías no pueden tener el mismo arete.')
    return attrs


def apply_calving(record):
    record.id=UUID(str(record.id))
    mother=record.mother;loc=record.location;result=[]
    for row in record.calves:
        if row['mode']=='stillborn':
            result.append({**row,'outcome':'stillborn'});continue
        if row['mode']=='new':
            tag=row['tag'] or f'TEMP-{UUID(str(record.id)).hex[:8]}-{UUID(row["animal"]).hex[:6]}'
            calf=Animal.objects.create(id=row['animal'],farm_id=record.farm_id,tag=tag,name=row['name'],sex=row['sex'],category='calf',birth_date=record.date,mother=mother,birth_record=record.id,owner_id=loc['calf_owner'],lot_id=loc['calf_lot'],paddock_id=loc['calf_paddock'],paddock_since=record.date if loc['calf_paddock'] else None)
        else:
            calf=Animal.objects.get(pk=row['animal'],farm_id=record.farm_id)
            calf.mother=mother;calf.birth_date=record.date;calf.birth_record=record.id
            calf.save(update_fields=['mother','birth_date','birth_record','updated_at'])
        if row['weight_kg'] and not Weighing.objects.filter(animal=calf,date=record.date,weight_kg=row['weight_kg'],voided=False).exists():
            Weighing.objects.create(id=uuid5(NAMESPACE_URL,f'bovinonic:birth-weight:{record.id}:{calf.id}'),farm_id=record.farm_id,animal=calf,date=record.date,weight_kg=row['weight_kg'],source_type='birth',source_id=record.id)
        result.append({'mode':row['mode'],'animal':str(calf.id),'tag':calf.tag,'name':calf.name,'sex':calf.sex,'weight_kg':row['weight_kg'],'outcome':'alive','provisional':row['mode']=='new' and not row['tag']})
    event=ReproductiveEvent.objects.filter(farm_id=record.farm_id,animal=mother,type='calving',date=record.date,calving_record__isnull=True).order_by('created_at','id').first()
    if event:
        event.calving_record=record.id;event.save(update_fields=['calving_record','updated_at'])
    else:
        event=ReproductiveEvent.objects.create(id=uuid5(NAMESPACE_URL,f'bovinonic:calving-event:{record.id}'),farm_id=record.farm_id,animal=mother,date=record.date,type='calving',calving_record=record.id)
    movement=None
    if loc['change_mother_paddock'] and str(mother.paddock_id or '')!=str(loc['mother_paddock'] or ''):
        movement=PaddockMovement.objects.create(id=uuid5(NAMESPACE_URL,f'bovinonic:calving-movement:{record.id}'),farm_id=record.farm_id,date=record.date,destination_id=loc['mother_paddock'],animals=[{'animal':str(mother.id),'from_paddock':str(mother.paddock_id) if mother.paddock_id else None,'previous_movement':str(mother.paddock_movement) if mother.paddock_movement else None}],notes='Traslado al registrar parto')
        mother.paddock_id=loc['mother_paddock'];mother.paddock_since=record.date;mother.paddock_movement=movement.id
    if loc['change_mother_lot']:mother.lot_id=loc['mother_lot']
    if record.maternal_status!='keep':mother.category=record.maternal_status
    if CalvingRecord.objects.filter(farm_id=record.farm_id,mother=mother).order_by('-date','-created_at').first().id==record.id:mother.last_calving=record.id
    mother.save(update_fields=['paddock','paddock_since','paddock_movement','lot','category','last_calving','updated_at'])
    record.result={'calves':result,'event':str(event.id),'movement':str(movement.id) if movement else None,'mother_category':mother.category}
    record.save(update_fields=['result','updated_at'])
