import uuid
from django.test import TestCase
from apps.core.models import Farm
from apps.production.models import DailyMilkProduction, Milking
from . import tests as sync_tests


class DailyMilkTests(TestCase):
    setUp = sync_tests.SyncApiTests.setUp
    login = sync_tests.SyncApiTests.login

    def row(self, **overrides):
        data={'id':str(uuid.uuid4()),'date':'2026-10-01','liters':'125.50','notes':'Total de la finca'}
        data.update(overrides)
        return data

    def push(self, rows):
        return self.client.post('/api/sync/batch',{'farm':str(self.farm.id),'daily_milk':rows},format='json')

    def test_operator_creates_without_animal_updates_and_retries(self):
        self.login(); row=self.row()
        for _ in range(2):
            response=self.push([row]); self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(DailyMilkProduction.objects.count(),1); self.assertEqual(Milking.objects.count(),0)
        row['liters']='130.00';row['notes']='Corregido'
        self.assertEqual(self.push([row]).status_code,200)
        record=DailyMilkProduction.objects.get();self.assertEqual(str(record.liters),'130.00');self.assertEqual(record.notes,'Corregido')
        data=self.client.get('/api/sync/pull',{'farm':str(self.farm.id)}).data
        self.assertEqual(data['daily_milk'][0]['liters'],'130.00');self.assertNotIn('animal',data['daily_milk'][0])

    def test_two_devices_merge_same_day_and_never_add_liters(self):
        self.login();first=self.row();second=self.row(liters='140.25')
        response=self.push([first,second]);self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(DailyMilkProduction.objects.count(),1);self.assertEqual(str(DailyMilkProduction.objects.get().liters),'140.25')
        self.assertEqual(response.data['results']['daily_milk'][1]['merged_into'],first['id'])
        self.assertTrue(response.data['results']['daily_milk'][1]['conflict'])
        self.assertEqual(self.push([second]).status_code,200);self.assertEqual(DailyMilkProduction.objects.count(),1)

    def test_zero_individual_history_and_independent_days(self):
        self.login();Milking.objects.create(farm=self.farm,animal=self.animal,date='2026-10-01',shift='AM',liters='10')
        response=self.push([self.row(liters='0'),self.row(date='2026-10-02',liters='150')]);self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(DailyMilkProduction.objects.count(),2);self.assertEqual(Milking.objects.count(),1)

    def test_date_id_and_farm_protection(self):
        self.login();row=self.row();self.assertEqual(self.push([row]).status_code,200)
        row['date']='2026-10-02';self.assertEqual(self.push([row]).status_code,400)
        other=Farm.objects.create(name='Other');record=DailyMilkProduction.objects.create(farm=other,date='2026-10-01',liters=99)
        self.assertEqual(self.push([self.row(id=str(record.id))]).status_code,400)
        pulled=self.client.get('/api/sync/pull',{'farm':str(self.farm.id)}).data['daily_milk']
        self.assertEqual(len(pulled),1);self.assertEqual(str(pulled[0]['farm']),str(self.farm.id))

    def test_invalid_data_rolls_back_all_days(self):
        self.login()
        for overrides in [{'liters':'-1'},{'liters':'NaN'},{'liters':'1.001'},{'liters':'1000000'},{'date':'2099-01-01'},{'date':'2026-02-30'},{'id':'bad'}]:
            response=self.push([self.row(),self.row(date='2026-10-02',**{k:v for k,v in overrides.items() if k!='date'})] if 'date' not in overrides else [self.row(),self.row(**overrides)])
            self.assertEqual(response.status_code,400,response.content);self.assertEqual(DailyMilkProduction.objects.count(),0)
