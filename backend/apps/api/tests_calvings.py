import copy
import uuid
from datetime import date
from django.test import TestCase
from apps.core.models import Farm, FarmMembership
from apps.livestock.models import Animal, AnimalLot, Paddock, Owner, PaddockMovement
from apps.reproduction.models import CalvingRecord, ReproductiveEvent
from apps.production.models import Weighing
from . import tests_sales
from .serializers import AnimalSerializer, ReproductiveEventSerializer


class CalvingTests(TestCase):
    setUp = tests_sales.SaleApiTests.setUp
    login = tests_sales.SaleApiTests.login
    push = tests_sales.SaleApiTests.push

    def record(self, **changes):
        self.animal.refresh_from_db()
        data={'id':str(uuid.uuid4()),'mother':str(self.animal.id),'date':'2026-10-01','delivery':'normal','maternal_status':'keep','mother_version':self.animal.updated_at.isoformat(),'notes':'',
              'calves':[{'mode':'new','animal':str(uuid.uuid4()),'tag':'CALF-1','name':'Nueva','sex':'H','weight_kg':'30.00'}],
              'location':{k:None for k in ['mother_lot','mother_paddock','calf_lot','calf_paddock','calf_owner']}}
        data['location'].update(change_mother_lot=False,change_mother_paddock=False)
        data.update(changes);return data

    def submit(self, data):
        response=self.push(calvings=[data]);self.assertEqual(response.status_code,200,response.content);return CalvingRecord.objects.get(pk=data['id'])

    def test_existing_calf_links_without_duplicate_and_preserves_ficha(self):
        self.login('boss');lot=AnimalLot.objects.create(farm=self.farm,name='Crías')
        calf=Animal.objects.create(farm=self.farm,tag='EXISTING',sex='M',category='calf',owner=self.owner,lot=lot,mother=self.animal,birth_date=date(2026,10,1))
        data=self.record(calves=[{'mode':'existing','animal':str(calf.id),'weight_kg':None}]);count=Animal.objects.count()
        self.submit(data);self.submit(data);calf.refresh_from_db()
        self.assertEqual(Animal.objects.count(),count);self.assertEqual(calf.birth_record,uuid.UUID(data['id']));self.assertEqual(calf.owner_id,self.owner.id);self.assertEqual(calf.lot_id,lot.id);self.assertEqual(calf.sex,'M');self.assertEqual(ReproductiveEvent.objects.count(),1)

    def test_new_twins_stillborn_provisional_weight_and_mother_movement_atomic_retry(self):
        self.login('boss');lot=AnimalLot.objects.create(farm=self.farm,name='Maternidad');paddock=Paddock.objects.create(farm=self.farm,name='Cerca')
        data=self.record(maternal_status='cow_nursing');data['calves'][0]['tag']='';data['calves'].append({'mode':'stillborn','animal':None,'sex':'unknown','name':'Gemelo','weight_kg':'20'})
        data['location'].update(change_mother_lot=True,mother_lot=str(lot.id),change_mother_paddock=True,mother_paddock=str(paddock.id),calf_lot=str(lot.id),calf_paddock=str(paddock.id),calf_owner=str(self.owner.id))
        stored=self.submit(data);self.submit(data);calf=Animal.objects.get(pk=data['calves'][0]['animal']);self.animal.refresh_from_db()
        self.assertTrue(calf.tag.startswith('TEMP-'));self.assertEqual(calf.mother_id,self.animal.id);self.assertEqual(calf.owner_id,self.owner.id);self.assertEqual(calf.paddock_id,paddock.id);self.assertEqual(calf.birth_date,date(2026,10,1))
        self.assertEqual(self.animal.category,'cow_nursing');self.assertEqual(self.animal.lot_id,lot.id);self.assertEqual(self.animal.paddock_id,paddock.id);self.assertEqual(self.animal.last_calving,stored.id)
        self.assertEqual(PaddockMovement.objects.count(),1);self.assertEqual(ReproductiveEvent.objects.count(),1);self.assertEqual(Weighing.objects.count(),1);self.assertEqual(Animal.objects.count(),3);self.assertEqual(stored.result['calves'][1]['outcome'],'stillborn')
        weighing=Weighing.objects.get();self.assertEqual(weighing.source_type,'birth')
        response=self.push(weighings=[{'id':str(uuid.uuid4()),'animal':str(calf.id),'date':'2026-10-02','weight_kg':'32'}]);self.assertEqual(response.status_code,200,response.content);weighing.refresh_from_db();self.assertFalse(weighing.voided)

    def test_stillbirth_only_is_history_without_hato_animal_and_reuses_old_event(self):
        self.login('boss');event=ReproductiveEvent.objects.create(farm=self.farm,animal=self.animal,date='2026-10-01',type='calving')
        data=self.record(calves=[{'mode':'stillborn','animal':None,'sex':'M','name':'','weight_kg':None}]);self.submit(data)
        self.assertEqual(Animal.objects.count(),2);self.assertEqual(ReproductiveEvent.objects.count(),1);event.refresh_from_db();self.assertEqual(event.calving_record,uuid.UUID(data['id']))

    def test_invalid_second_calf_rolls_back_everything(self):
        self.login('boss');data=self.record(maternal_status='cow_nursing');data['calves'].append({'mode':'existing','animal':str(uuid.uuid4()),'weight_kg':None})
        self.assertEqual(self.push(calvings=[data]).status_code,400);self.assertFalse(CalvingRecord.objects.exists());self.assertFalse(ReproductiveEvent.objects.exists());self.assertEqual(Animal.objects.count(),2);self.assertFalse(Weighing.objects.exists());self.animal.refresh_from_db();self.assertEqual(self.animal.category,'cow_lactating')

    def test_duplicate_mother_date_immutable_record_and_stale_version(self):
        self.login('boss');data=self.record();stale=copy.deepcopy(data);self.animal.name='Actualizada';self.animal.save()
        self.assertEqual(self.push(calvings=[stale]).status_code,400)
        data=self.record();self.submit(data)
        self.assertEqual(self.push(calvings=[{**data,'notes':'Alterado'}]).status_code,400)
        duplicate=self.record(calves=[{'mode':'stillborn','animal':None,'sex':'unknown','weight_kg':None}]);self.assertEqual(self.push(calvings=[duplicate]).status_code,400)

    def test_other_mother_date_and_cross_farm_references_rejected(self):
        self.login('boss');other=Farm.objects.create(name='Otra');foreign=Animal.objects.create(farm=other,tag='FOREIGN',sex='M',category='calf');owner=Owner.objects.create(farm=other,name='Otro')
        calf=Animal.objects.create(farm=self.farm,tag='WRONG-DATE',sex='H',category='calf',birth_date=date(2026,9,1))
        for aid in [str(foreign.id),str(calf.id),str(self.animal.id)]:
            data=self.record(calves=[{'mode':'existing','animal':aid,'weight_kg':None}]);self.assertEqual(self.push(calvings=[data]).status_code,400)
        data=self.record();data['location']['calf_owner']=str(owner.id);self.assertEqual(self.push(calvings=[data]).status_code,400)
        for patch in [{'mother':str(foreign.id)},{'date':'2099-01-01'},{'calves':[]},{'maternal_status':'bull'}]:
            self.assertEqual(self.push(calvings=[{**self.record(),**patch}]).status_code,400)

    def test_roles_pull_receipt_and_birth_history_protected(self):
        self.login('op1');data=self.record();self.assertEqual(self.push(calvings=[data]).status_code,400)
        FarmMembership.objects.filter(user=self.user,farm=self.farm).update(role='technician');self.submit(data)
        receipt=self.client.get('/api/sales/receipt',{'farm':str(self.farm.id),'collection':'calvings','id':data['id']});self.assertEqual(receipt.status_code,200)
        calf=Animal.objects.get(pk=data['calves'][0]['animal']);edit=dict(AnimalSerializer(calf).data);edit['birth_date']='2026-10-02';self.assertEqual(self.push(animals=[edit]).status_code,400)
        edit=dict(AnimalSerializer(calf).data);edit['name']='Renombrada';self.assertEqual(self.push(animals=[edit]).status_code,200)
        event=ReproductiveEvent.objects.get();edit=dict(ReproductiveEventSerializer(event).data);edit['date']='2026-10-02';self.assertEqual(self.push(reproductive_events=[edit]).status_code,400)
        FarmMembership.objects.filter(user=self.user,farm=self.farm).update(role='operator');pulled=self.client.get('/api/sync/pull',{'farm':str(self.farm.id)});self.assertEqual(len(pulled.data['calvings']),1)

    def test_later_calving_prevents_historical_category_change(self):
        self.login('boss');ReproductiveEvent.objects.create(farm=self.farm,animal=self.animal,date='2026-10-10',type='calving')
        data=self.record(maternal_status='cow_dry');self.assertEqual(self.push(calvings=[data]).status_code,400)
        data['maternal_status']='keep';self.submit(data)

    def test_existing_calf_missing_birth_is_completed_and_stale_mother_edit_rejected(self):
        self.login('boss');before=dict(AnimalSerializer(self.animal).data)
        calf=Animal.objects.create(farm=self.farm,tag='WITHOUT-BIRTH',sex='M',category='calf')
        data=self.record(calves=[{'mode':'existing','animal':str(calf.id),'weight_kg':None}],maternal_status='cow_nursing');self.submit(data);calf.refresh_from_db()
        self.assertEqual(calf.birth_date,date(2026,10,1));self.assertEqual(calf.mother_id,self.animal.id)
        self.assertEqual(self.push(animals=[before]).status_code,400)
        self.animal.refresh_from_db();current=dict(AnimalSerializer(self.animal).data);current['category']='cow_lactating';self.assertEqual(self.push(animals=[current]).status_code,200)

    def test_invalid_later_record_rolls_back_prior_record_in_same_upload(self):
        self.login('boss');first=self.record();bad=self.record(calves=[])
        response=self.push(calvings=[first,bad]);self.assertEqual(response.status_code,400)
        self.assertEqual(Animal.objects.count(),2);self.assertFalse(CalvingRecord.objects.exists());self.assertFalse(ReproductiveEvent.objects.exists());self.assertFalse(Weighing.objects.exists())
