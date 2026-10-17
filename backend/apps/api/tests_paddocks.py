import uuid
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.core.models import Farm, FarmMembership
from apps.livestock.models import Animal, AnimalLot, Paddock, PaddockMovement
from . import tests


class PaddockTests(TestCase):
    setUp = tests.SyncApiTests.setUp
    login = tests.SyncApiTests.login

    def prepare(self):
        self.login('boss')
        self.origin = Paddock.objects.create(farm=self.farm, name='Norte')
        self.destination = Paddock.objects.create(farm=self.farm, name='Sur', area='5.50', max_occupation_days=3)
        self.lot = AnimalLot.objects.create(farm=self.farm, name='Terneras')
        self.animal.paddock = self.origin; self.animal.lot = self.lot; self.animal.save()
        self.other = Animal.objects.create(farm=self.farm, tag='NI-102', sex='H', category='calf', lot=self.lot)
        return {'id':str(uuid.uuid4()), 'date':timezone.localdate().isoformat(), 'destination':str(self.destination.id), 'lot':str(self.lot.id), 'notes':'Rotación',
                'animals':[{'animal':str(a.id), 'from_paddock':str(a.paddock_id) if a.paddock_id else None, 'previous_movement':None} for a in [self.animal,self.other]]}

    def push(self, **collections):
        return self.client.post('/api/sync/batch', {'farm':str(self.farm.id), **collections}, format='json')

    def test_settings_validation_and_legacy_optional_fields(self):
        self.login('boss'); pk=str(uuid.uuid4())
        base={'id':pk,'name':'Oeste','area':'5.50','area_unit':'mz','max_occupation_days':3}
        self.assertEqual(self.push(paddocks=[base]).status_code,200)
        row=Paddock.objects.get(pk=pk);self.assertEqual(row.area,Decimal('5.50'))
        for changes in [{'area':'0'},{'area':'-2'},{'area':'NaN'},{'area_unit':'acre'},{'max_occupation_days':0},{'max_occupation_days':3651},{'max_occupation_days':1.5}]:
            self.assertEqual(self.push(paddocks=[{**base,**changes}]).status_code,400,changes)
        row.refresh_from_db();self.assertEqual(row.max_occupation_days,3)
        self.assertEqual(self.push(paddocks=[{'id':pk,'name':'Oeste'}]).status_code,200)
        row.refresh_from_db();self.assertEqual(row.area,Decimal('5.50'))

    def test_lot_transfer_is_atomic_idempotent_and_incrementally_visible(self):
        movement=self.prepare(); cursor=self.animal.updated_at.isoformat()
        response=self.push(paddock_movements=[movement]);self.assertEqual(response.status_code,200,response.content)
        first=PaddockMovement.objects.get(); before=first.updated_at
        for animal in [self.animal,self.other]:
            animal.refresh_from_db();self.assertEqual(animal.paddock_id,self.destination.id);self.assertEqual(animal.paddock_movement,first.id);self.assertEqual(animal.lot_id,self.lot.id)
        self.assertEqual(self.push(paddock_movements=[movement]).status_code,200)
        first.refresh_from_db();self.assertEqual(before,first.updated_at);self.assertEqual(PaddockMovement.objects.count(),1)
        data=self.client.get('/api/sync/pull',{'farm':str(self.farm.id),'since':cursor}).data
        self.assertEqual(len(data['paddock_movements']),1);self.assertEqual(len(data['animals']),2)

    def test_any_invalid_animal_rolls_back_whole_transfer(self):
        movement=self.prepare();self.other.status='sold';self.other.save()
        self.assertEqual(self.push(paddock_movements=[movement]).status_code,400)
        self.animal.refresh_from_db();self.assertEqual(self.animal.paddock_id,self.origin.id);self.assertFalse(PaddockMovement.objects.exists())

    def test_rejects_foreign_destination_animal_and_lot(self):
        movement=self.prepare();farm=Farm.objects.create(name='Otra')
        paddock=Paddock.objects.create(farm=farm,name='Fuera');lot=AnimalLot.objects.create(farm=farm,name='Ajeno')
        animal=Animal.objects.create(farm=farm,tag='OTRA',sex='M',category='calf')
        for patch in [{'destination':str(paddock.id)},{'lot':str(lot.id)},{'animals':[{'animal':str(animal.id),'from_paddock':None,'previous_movement':None}]}]:
            self.assertEqual(self.push(paddock_movements=[{**movement,**patch}]).status_code,400)
        self.assertFalse(PaddockMovement.objects.exists())

    def test_stale_origin_conflict_and_return_cycle_marker(self):
        movement=self.prepare();self.assertEqual(self.push(paddock_movements=[movement]).status_code,200)
        back={**movement,'id':str(uuid.uuid4()),'destination':str(self.origin.id),'animals':[{'animal':r['animal'],'from_paddock':str(self.destination.id),'previous_movement':movement['id']} for r in movement['animals']]}
        self.assertEqual(self.push(paddock_movements=[back]).status_code,200)
        stale={**movement,'id':str(uuid.uuid4())}
        self.assertEqual(self.push(paddock_movements=[stale]).status_code,400)
        self.assertEqual(PaddockMovement.objects.count(),2)

    def test_dates_duplicate_empty_same_destination_and_membership_validation(self):
        movement=self.prepare()
        patches=[{'date':(timezone.localdate()+timedelta(days=1)).isoformat()}, {'animals':[]}, {'animals':[movement['animals'][0]]*2}, {'destination':str(self.origin.id)}]
        for patch in patches:self.assertEqual(self.push(paddock_movements=[{**movement,**patch}]).status_code,400)
        self.other.lot=None;self.other.save()
        self.assertEqual(self.push(paddock_movements=[movement]).status_code,400)

    def test_confirmed_transfer_immutable_and_correction_is_new_transfer(self):
        movement=self.prepare();self.assertEqual(self.push(paddock_movements=[movement]).status_code,200)
        self.assertEqual(self.push(paddock_movements=[{**movement,'notes':'Cambio'}]).status_code,400)
        previous={**movement,'id':str(uuid.uuid4()),'date':(timezone.localdate()-timedelta(days=1)).isoformat(),'destination':str(self.origin.id),'animals':[{'animal':str(self.other.id),'from_paddock':str(self.destination.id),'previous_movement':movement['id']}]}
        self.assertEqual(self.push(paddock_movements=[previous]).status_code,400)

    def test_technician_can_move_but_operator_only_reads_and_financial_privacy_preserved(self):
        movement=self.prepare();FarmMembership.objects.filter(user=self.user,farm=self.farm).update(role='technician');self.login()
        self.assertEqual(self.push(paddock_movements=[movement]).status_code,200)
        response=self.client.get('/api/sales/receipt',{'farm':str(self.farm.id),'collection':'paddock_movements','id':movement['id']})
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(self.client.get('/api/sales/receipt',{'farm':str(self.farm.id),'collection':'sales','id':movement['id']}).status_code,403)
        FarmMembership.objects.filter(user=self.user,farm=self.farm).update(role='operator');self.login()
        self.assertEqual(self.push(paddock_movements=[movement]).status_code,400)
        self.assertEqual(len(self.client.get('/api/sync/pull',{'farm':str(self.farm.id)}).data['paddock_movements']),1)

    def test_animal_edits_cannot_silently_revert_a_transfer(self):
        movement=self.prepare();self.assertEqual(self.push(paddock_movements=[movement]).status_code,200)
        from .serializers import AnimalSerializer
        self.animal.refresh_from_db();data=dict(AnimalSerializer(self.animal).data);data['paddock']=str(self.origin.id)
        self.assertEqual(self.push(animals=[data]).status_code,400)
        data['paddock']=str(self.destination.id);data['name']='Actualizado'
        self.assertEqual(self.push(animals=[data]).status_code,200)
        self.animal.refresh_from_db();self.assertEqual(self.animal.paddock_movement,uuid.UUID(movement['id']))
