import uuid
from datetime import date
from django.test import TestCase
from apps.core.models import Farm, FarmMembership
from apps.health.models import HealthEvent
from apps.livestock.models import Animal, AnimalLot
from . import tests


class LotHealthTests(TestCase):
    setUp = tests.SyncApiTests.setUp
    login = tests.SyncApiTests.login

    def prepare(self):
        FarmMembership.objects.filter(user=self.user,farm=self.farm).update(role='technician')
        self.login()
        lot=AnimalLot.objects.create(farm=self.farm,name='Lote sanitario')
        self.animal.lot=lot;self.animal.save()
        self.other=Animal.objects.create(farm=self.farm,lot=lot,tag='OTRA-LOTE',sex='M',category='calf')
        return [{'id':str(uuid.uuid4()),'animal':str(a.id),'date':'2026-10-17','type':'vaccine','product':'Producto DEMO','dose':dose,'withdrawal_days':7,'withdrawal_end_date':'2099-01-01'} for a,dose in [(self.animal,'2 ml'),(self.other,'3 ml')]]

    def push(self, records):
        return self.client.post('/api/sync/batch',{'farm':str(self.farm.id),'health_events':records},format='json')

    def test_common_product_individual_doses_and_server_withdrawal_survive_retries_and_pull(self):
        records=self.prepare()
        for _ in range(2):
            response=self.push(records);self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(HealthEvent.objects.count(),2)
        for record in records:
            stored=HealthEvent.objects.get(pk=record['id']);self.assertEqual(stored.dose,record['dose']);self.assertEqual(stored.withdrawal_end_date,date(2026,10,24));self.assertEqual(stored.farm_id,self.farm.id)
        pulled=self.client.get('/api/sync/pull',{'farm':str(self.farm.id)}).data['health_events']
        self.assertEqual({str(r['animal']):r['dose'] for r in pulled},{records[0]['animal']:'2 ml',records[1]['animal']:'3 ml'})

    def test_one_invalid_event_rolls_back_every_event_in_the_uploaded_chunk(self):
        records=self.prepare();records[1]['dose']='x'*101
        self.assertEqual(self.push(records).status_code,400);self.assertFalse(HealthEvent.objects.exists())
        records[1]['dose']='3 ml';self.other.birth_date=date(2026,10,17);self.other.save();records[1]['date']='2026-10-16'
        self.assertEqual(self.push(records).status_code,400);self.assertFalse(HealthEvent.objects.exists())

    def test_operator_and_foreign_animals_cannot_receive_bulk_writes(self):
        records=self.prepare();FarmMembership.objects.filter(user=self.user,farm=self.farm).update(role='operator');self.login()
        self.assertEqual(self.push(records).status_code,400);self.assertFalse(HealthEvent.objects.exists())
        FarmMembership.objects.filter(user=self.user,farm=self.farm).update(role='technician');self.login()
        farm=Farm.objects.create(name='Otra finca');alien=Animal.objects.create(farm=farm,tag='AJENO-LOTE',sex='M',category='calf');records[1]['animal']=str(alien.id)
        self.assertEqual(self.push(records).status_code,400);self.assertFalse(HealthEvent.objects.exists())
