import copy
import json
import uuid
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from apps.core.models import Farm
from apps.livestock.models import Animal, AnimalAgreement
from apps.livestock.agreements import calculate_settlement
from . import tests as sync_tests


class SettlementMathTests(SimpleTestCase):
    def test_shared_settlement_vectors_and_conservation(self):
        vectors = json.loads((Path(__file__).resolve().parents[1] / 'livestock' / 'settlement_vectors.json').read_text(encoding='utf-8-sig'))
        for vector in vectors:
            with self.subTest(vector['name']):
                result = calculate_settlement(vector['kind'], vector['animals'], vector['expenses'], vector['owner_share'])
                for key, expected in vector['expected'].items():
                    self.assertEqual(result[key], expected)
                if vector['kind'] != 'pasture':
                    self.assertEqual(Decimal(result['owner_total']) + Decimal(result['partner_total']), Decimal(result['sale_value']))


class AgreementApiTests(TestCase):
    setUp = sync_tests.SyncApiTests.setUp
    login = sync_tests.SyncApiTests.login

    def agreement(self, **overrides):
        data = {'id': str(uuid.uuid4()), 'title': 'Terneros a medias', 'owner_name': 'Dueño',
                'partner_name': 'Responsable', 'external_farm': 'Otra finca', 'kind': 'weight_gain',
                'currency': 'NIO', 'owner_share': '50.00', 'start_date': '2026-09-01',
                'end_date': None, 'status': 'active', 'notes': '',
                'animals': [{'animal': str(self.animal.id), 'initial_weight': '180.00', 'final_weight': None, 'price_per_kg': None, 'final_date': None}], 'expenses': []}
        data.update(overrides)
        return data

    def push(self, data):
        return self.client.post('/api/sync/batch', {'farm': str(self.farm.id), 'agreements': [data]}, format='json')

    def final_data(self):
        data = self.agreement(status='settled', end_date='2026-09-30')
        data['animals'][0].update(final_weight='280.00', price_per_kg='100.00', final_date='2026-09-30')
        data['expenses'] = [{'id': str(uuid.uuid4()), 'concept': 'Medicamentos', 'date': '2026-09-15', 'amount': '1000.00', 'paid_by': 'owner', 'animal': None}]
        return data

    def test_create_settle_retry_and_freeze_keeps_animal_ownership(self):
        self.login('boss')
        data = self.agreement()
        response = self.push(data)
        self.assertEqual(response.status_code, 200, response.content)
        original_owner = self.animal.owner_id
        final = self.final_data()
        final['id'] = data['id']
        final['settlement'] = {'owner_total': '999999.99'}
        for _ in range(2):
            response = self.push(final)
            self.assertEqual(response.status_code, 200, response.content)
        record = AnimalAgreement.objects.get(pk=data['id'])
        self.assertEqual(record.settlement['owner_total'], '23500.00')
        self.assertEqual(record.settlement['partner_total'], '4500.00')
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.owner_id, original_owner)
        self.assertEqual(self.animal.status, 'active')
        final['expenses'][0]['amount'] = '5000.00'
        self.assertEqual(self.push(final).status_code, 400)
        record.refresh_from_db()
        self.assertEqual(record.expenses[0]['amount'], '1000.00')

    def test_foreign_farm_animal_and_expense_are_rejected(self):
        self.login('boss')
        other = Farm.objects.create(name='Private')
        animal = Animal.objects.create(farm=other, tag='PRIVATE', sex='H', category='calf')
        data = self.agreement()
        data['animals'][0]['animal'] = str(animal.id)
        self.assertEqual(self.push(data).status_code, 400)
        data = self.final_data()
        data['expenses'][0]['animal'] = str(animal.id)
        self.assertEqual(self.push(data).status_code, 400)
        self.assertEqual(AnimalAgreement.objects.count(), 0)

    def test_duplicate_animals_and_overlapping_active_agreements_are_rejected(self):
        self.login('boss')
        data = self.agreement()
        data['animals'].append(copy.deepcopy(data['animals'][0]))
        self.assertEqual(self.push(data).status_code, 400)
        first, second = self.agreement(), self.agreement()
        response = self.client.post('/api/sync/batch', {'farm': str(self.farm.id), 'agreements': [first,second]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(AnimalAgreement.objects.count(), 0)
        self.assertEqual(self.push(first).status_code, 200)
        self.assertEqual(self.push(second).status_code, 400)

    def test_loss_requires_explicit_confirmation_and_is_not_clamped(self):
        self.login('boss')
        data = self.final_data()
        data['animals'][0]['final_weight'] = '170.00'
        self.assertEqual(self.push(data).status_code, 400)
        data['accept_loss'] = 'false'
        self.assertEqual(self.push(data).status_code, 400)
        data['accept_loss'] = True
        response = self.push(data)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(AnimalAgreement.objects.get().settlement['partner_total'], '-1000.00')

    def test_pasture_closes_without_sale_weights_or_profit_split(self):
        self.login('boss')
        data = self.final_data()
        data['kind'] = 'pasture'
        data['animals'][0].update(initial_weight=None, final_weight=None, price_per_kg=None, final_date=None)
        data['expenses'][0]['paid_by'] = 'partner'
        response = self.push(data)
        self.assertEqual(response.status_code, 200, response.content)
        result = AnimalAgreement.objects.get().settlement
        self.assertEqual(result['partner_reimbursement'], '1000.00')
        self.assertNotIn('owner_part', result)

    def test_permissions_and_farm_scoped_pull(self):
        self.login('boss')
        data = self.agreement()
        self.assertEqual(self.push(data).status_code, 200)
        self.login()
        self.assertEqual(self.push(self.agreement()).status_code, 400)
        response = self.client.get('/api/sync/pull', {'farm': str(self.farm.id)})
        self.assertEqual(response.data['agreements'], [])
        self.login('boss')
        response = self.client.get('/api/sync/pull', {'farm': str(self.farm.id)})
        self.assertEqual(len(response.data['agreements']), 1)

    def test_invalid_dates_prices_percent_and_ledger_do_not_save(self):
        self.login('boss')
        for change in ('date', 'price', 'percent', 'expense', 'initial', 'missing_final', 'nan'):
            data = self.final_data()
            if change == 'date': data['expenses'][0]['date'] = '2026-08-01'
            elif change == 'price': data['animals'][0]['price_per_kg'] = '0'
            elif change == 'percent': data['owner_share'] = '110'
            elif change == 'expense': data['expenses'][0]['amount'] = '-5'
            elif change == 'initial': data['animals'][0]['initial_weight'] = None
            elif change == 'missing_final': data['animals'][0]['final_date'] = None
            elif change == 'nan': data['expenses'][0]['amount'] = 'NaN'
            response = self.push(data)
            self.assertEqual(response.status_code, 400, (change,response.content))
        self.assertEqual(AnimalAgreement.objects.count(), 0)
