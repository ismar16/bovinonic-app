from copy import deepcopy
from decimal import Decimal
from django.test import TestCase
from django.apps import apps
from apps.production.models import Weighing
from apps.production.linked_weights import reconcile_weights
from . import tests_agreements, tests_sales


class LinkedWeightsTests(TestCase):
    setUp = tests_sales.SaleApiTests.setUp
    login = tests_sales.SaleApiTests.login
    sale = tests_sales.SaleApiTests.sale
    attach = tests_sales.SaleApiTests.attach

    def push(self, **data):
        return self.client.post('/api/sync/batch',{'farm':str(self.farm.id),**data},format='json')

    def agreement(self):
        return tests_agreements.AgreementApiTests.agreement(self)

    def test_initial_and_final_weights_connect_to_history_and_sale_wins(self):
        self.login('boss'); agreement=self.agreement()
        response=self.push(agreements=[agreement]); self.assertEqual(response.status_code,200,response.content)
        initial=Weighing.objects.get(source_type='agreement_initial')
        self.assertEqual(initial.weight_kg,Decimal('180'));self.assertEqual(initial.date.isoformat(),'2026-09-01')
        self.assertEqual(str(initial.source_id),agreement['id'])
        agreement['animals'][0].update(final_weight='280.00',price_per_kg='100.00',final_date='2026-09-30')
        self.assertEqual(self.push(agreements=[agreement]).status_code,200)
        self.assertEqual(Weighing.objects.filter(voided=False).count(),2)
        from apps.livestock.models import AnimalAgreement
        stored=AnimalAgreement.objects.get(pk=agreement['id'])
        sale=self.attach(self.sale(),stored)
        for _ in range(2):
            response=self.push(sales=[sale]);self.assertEqual(response.status_code,200,response.content)
        final=Weighing.objects.get(source_type='sale',voided=False)
        self.assertEqual(final.weight_kg,Decimal('280'));self.assertEqual(final.date.isoformat(),'2026-10-01')
        self.assertTrue(Weighing.objects.get(source_type='agreement_final').voided)
        self.assertEqual(Weighing.objects.filter(voided=False).count(),2)

    def test_agreement_correction_updates_same_generated_record(self):
        self.login('boss'); agreement=self.agreement();self.assertEqual(self.push(agreements=[agreement]).status_code,200)
        old=Weighing.objects.get(source_type='agreement_initial'); old_id=old.id;cursor=old.updated_at.isoformat()
        agreement['animals'][0]['initial_weight']='185.00';self.assertEqual(self.push(agreements=[agreement]).status_code,200)
        updated=Weighing.objects.get(source_type='agreement_initial')
        self.assertEqual(updated.id,old_id);self.assertEqual(updated.weight_kg,Decimal('185'))
        delta=self.client.get('/api/sync/pull',{'farm':str(self.farm.id),'since':cursor}).data
        self.assertEqual(delta['weighings'][0]['weight_kg'],'185.00')

    def test_generated_weights_cannot_be_changed_directly_and_manual_duplicates_reconcile(self):
        self.login('boss'); agreement=self.agreement();self.assertEqual(self.push(agreements=[agreement]).status_code,200)
        generated=Weighing.objects.get(source_type='agreement_initial')
        response=self.push(weighings=[{'id':str(generated.id),'animal':str(self.animal.id),'date':'2026-09-01','weight_kg':'999'}])
        self.assertEqual(response.status_code,400)
        manual=Weighing.objects.create(farm=self.farm,animal=self.animal,date='2026-09-01',weight_kg='180')
        reconcile_weights(self.farm.id)
        generated.refresh_from_db();self.assertTrue(generated.voided)
        self.assertEqual(Weighing.objects.filter(voided=False).count(),1)
        self.assertEqual(Weighing.objects.get(voided=False).id,manual.id)

    def test_sale_correction_backfill_uses_401_and_keeps_financial_values(self):
        self.login('boss'); sale=self.sale();sale['lines'][0]['weight_kg']='405.00'
        self.assertEqual(self.push(sales=[sale]).status_code,200)
        from apps.livestock.models import AnimalSale
        stored=AnimalSale.objects.get(pk=sale['id']);stored.lines[0]['weight_kg']='401.00';stored.lines[0]['value']='40100.00';stored.total=Decimal('40100.00');stored.save()
        prior=deepcopy(stored.lines)
        reconcile_weights(self.farm.id,apps=apps)
        row=Weighing.objects.get(source_type='sale',voided=False)
        self.assertEqual(row.weight_kg,Decimal('401'))
        stored.refresh_from_db();self.assertEqual(stored.lines,prior);self.assertEqual(stored.total,Decimal('40100'))

    def test_operators_can_read_linked_weights_without_financial_agreement_data(self):
        self.login('boss');self.assertEqual(self.push(agreements=[self.agreement()]).status_code,200)
        self.login();data=self.client.get('/api/sync/pull',{'farm':str(self.farm.id)}).data
        self.assertEqual(data['agreements'],[]);self.assertEqual(data['weighings'][0]['source_type'],'agreement_initial')

    def test_unrelated_sync_does_not_retimestamp_unchanged_weights(self):
        self.login('boss');agreement=self.agreement();self.assertEqual(self.push(agreements=[agreement]).status_code,200)
        row=Weighing.objects.get(source_type='agreement_initial');before=row.updated_at
        self.assertEqual(self.push(agreements=[agreement]).status_code,200)
        row.refresh_from_db();self.assertEqual(row.updated_at,before)
