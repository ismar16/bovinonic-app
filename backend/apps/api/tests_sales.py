import copy
import uuid
from decimal import Decimal

from django.test import TestCase
from apps.core.models import Farm
from apps.livestock.models import Animal, AnimalAgreement, AnimalSale, SalePayment
from apps.livestock.sales import allocated_expenses
from . import tests as sync_tests


class SaleApiTests(TestCase):
    setUp = sync_tests.SyncApiTests.setUp
    login = sync_tests.SyncApiTests.login

    def sale(self, animal=None, **overrides):
        data = {'id': str(uuid.uuid4()), 'date': '2026-10-01', 'buyer': 'Comprador',
                'buyer_phone': '', 'currency': 'NIO', 'notes': '',
                'lines': [{'animal': str((animal or self.animal).id), 'weight_kg': '280.00', 'price_per_kg': '100.00',
                           'agreement': None, 'agreement_version': None, 'expenses': []}]}
        data.update(overrides)
        return data

    def push(self, **collections):
        return self.client.post('/api/sync/batch', {'farm': str(self.farm.id), **collections}, format='json')

    def agreement(self, animals=None, expenses=None, kind='weight_gain'):
        return AnimalAgreement.objects.create(farm=self.farm, title='A medias', owner_name='Dueño', partner_name='Socio', external_farm='Otra finca',
            kind=kind, currency='NIO', owner_share=50, start_date='2026-09-01',
            animals=[{'animal': str(a.id), 'tag': a.tag, 'name': a.name, 'initial_weight':'180.00', 'final_weight':None, 'price_per_kg':None, 'final_date':None} for a in (animals or [self.animal])],
            expenses=expenses or [])

    def attach(self, data, agreement):
        data['lines'][0].update(agreement=str(agreement.id), agreement_version=agreement.updated_at.isoformat().replace('+00:00','Z'))
        return data

    def expense(self, amount='1000.00', animal=None, paid_by='owner'):
        return {'id':str(uuid.uuid4()),'date':'2026-09-15','concept':'Medicamentos','amount':amount,'animal':str(animal.id) if animal else None,'paid_by':paid_by}

    def test_sale_is_atomic_idempotent_and_immutable(self):
        self.login('boss')
        data = self.sale(); data['total'] = '1.00'; data['lines'][0]['value'] = '1.00'
        for _ in range(2):
            response = self.push(sales=[data]); self.assertEqual(response.status_code,200,response.content)
        sale = AnimalSale.objects.get(); self.assertEqual(sale.total,Decimal('28000.00'))
        self.animal.refresh_from_db(); self.assertEqual(self.animal.status,'sold'); self.assertEqual(self.animal.owner_id,self.owner.id)
        self.assertEqual(self.animal.status_changed_at.isoformat(),'2026-10-01')
        data['buyer']='Cambio'; self.assertEqual(self.push(sales=[data]).status_code,400)
        sale.refresh_from_db(); self.assertEqual(sale.buyer,'Comprador')
        self.assertEqual(self.push(sales=[self.sale()]).status_code,400)
        self.assertEqual(AnimalSale.objects.count(),1)

    def test_partial_sales_split_common_costs_once_and_close_only_at_end(self):
        self.login('boss')
        second = Animal.objects.create(farm=self.farm,tag='SECOND',sex='M',category='calf')
        agreement = self.agreement([self.animal,second], [self.expense('1000.01'),self.expense('100.00',second,'partner')])
        cursor = agreement.updated_at.isoformat()
        first = self.attach(self.sale(),agreement)
        response = self.push(sales=[first]); self.assertEqual(response.status_code,200,response.content)
        receipt = AnimalSale.objects.get().lines[0]['settlement']
        self.assertEqual(receipt['expenses'],'500.01'); self.assertEqual(receipt['owner_total'],'23250.01'); self.assertEqual(receipt['partner_total'],'4749.99')
        agreement.refresh_from_db(); self.assertEqual(agreement.status,'active')
        self.assertGreater(agreement.updated_at.isoformat(),cursor)
        delta=self.client.get('/api/sync/pull',{'farm':str(self.farm.id),'since':cursor}).data
        self.assertEqual(len(delta['agreements'][0]['sale_receipts']),1)
        second.refresh_from_db(); self.assertEqual(second.status,'active')
        last = self.attach(self.sale(second),agreement)
        response = self.push(sales=[last]); self.assertEqual(response.status_code,200,response.content)
        agreement.refresh_from_db(); self.assertEqual(agreement.status,'settled')
        self.assertEqual(agreement.settlement['expenses'],'1100.01')
        self.assertEqual(Decimal(agreement.settlement['owner_total']) + Decimal(agreement.settlement['partner_total']),Decimal('56000.00'))
        for _ in range(2): self.assertEqual(self.push(sales=[first,last]).status_code,200)
        self.assertEqual(AnimalSale.objects.count(),2)
        pull=self.client.get('/api/sync/pull',{'farm':str(self.farm.id)}).data
        self.assertEqual(len(pull['agreements'][0]['sale_receipts']),2)

    def test_duplicate_in_batch_rolls_back_sales_and_inventory(self):
        self.login('boss'); first=self.sale(); second=self.sale()
        response=self.push(sales=[first,second]); self.assertEqual(response.status_code,400,response.content)
        self.assertEqual(AnimalSale.objects.count(),0); self.animal.refresh_from_db(); self.assertEqual(self.animal.status,'active')

    def test_multi_animal_failure_rolls_back_whole_sale(self):
        self.login('boss'); data=self.sale(); data['lines'].append(self.sale(self.sold_animal)['lines'][0])
        self.assertEqual(self.push(sales=[data]).status_code,400)
        self.assertEqual(AnimalSale.objects.count(),0); self.animal.refresh_from_db(); self.assertEqual(self.animal.status,'active')

    def test_cross_farm_permissions_and_financial_privacy(self):
        self.login(); self.assertEqual(self.push(sales=[self.sale()]).status_code,400)
        self.login('boss'); other=Farm.objects.create(name='Other'); animal=Animal.objects.create(farm=other,tag='FOREIGN',sex='M',category='calf')
        self.assertEqual(self.push(sales=[self.sale(animal)]).status_code,400)
        self.assertEqual(self.push(sales=[self.sale()]).status_code,200)
        self.login(); data=self.client.get('/api/sync/pull',{'farm':str(self.farm.id)}).data
        self.assertEqual(data['sales'],[]); self.assertEqual(data['sale_payments'],[])

    def test_cobros_append_only_cap_and_retry(self):
        self.login('boss'); data=self.sale(); self.assertEqual(self.push(sales=[data]).status_code,200)
        payment={'id':str(uuid.uuid4()),'sale':data['id'],'date':'2026-10-01','amount':'10000.00','method':'cash','reference':''}
        for _ in range(2):
            response=self.push(sale_payments=[payment]); self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(SalePayment.objects.count(),1)
        changed={**payment,'amount':'9999.00'}; self.assertEqual(self.push(sale_payments=[changed]).status_code,400)
        extra={**payment,'id':str(uuid.uuid4()),'amount':'18000.01'}; self.assertEqual(self.push(sale_payments=[extra]).status_code,400)
        extra['amount']='18000.00'; self.assertEqual(self.push(sale_payments=[extra]).status_code,200)
        self.assertEqual(SalePayment.objects.count(),2)

    def test_payment_batch_overcharge_rolls_back(self):
        self.login('boss'); data=self.sale(); self.assertEqual(self.push(sales=[data]).status_code,200)
        payments=[{'id':str(uuid.uuid4()),'sale':data['id'],'date':'2026-10-01','amount':'20000.00','method':'transfer'} for _ in range(2)]
        self.assertEqual(self.push(sale_payments=payments).status_code,400); self.assertEqual(SalePayment.objects.count(),0)

    def test_stale_agreement_and_currency_rejected(self):
        self.login('boss'); agreement=self.agreement()
        data=self.attach(self.sale(),agreement); data['lines'][0]['agreement_version']='old'
        self.assertEqual(self.push(sales=[data]).status_code,400)
        data=self.attach(self.sale(currency='USD'),agreement); self.assertEqual(self.push(sales=[data]).status_code,400)
        self.assertEqual(self.push(sales=[self.sale()]).status_code,400)

    def test_loss_requires_true_and_includes_extra_costs(self):
        self.login('boss'); agreement=self.agreement(expenses=[self.expense('11000.00')]); data=self.attach(self.sale(),agreement)
        data['lines'][0]['expenses']=[{'concept':'Transporte','amount':'500.00','paid_by':'partner'}]
        for flag in (False,'true',1):
            data['accept_loss']=flag; self.assertEqual(self.push(sales=[data]).status_code,400)
        data['accept_loss']=True; response=self.push(sales=[data]); self.assertEqual(response.status_code,200,response.content)
        receipt=AnimalSale.objects.get().lines[0]['settlement']; self.assertEqual(receipt['net_gain'],'-1500.00')
        self.assertEqual(Decimal(receipt['owner_total'])+Decimal(receipt['partner_total']),Decimal('28000.00'))

    def test_pasture_reimbursement_and_expense_cents(self):
        self.login('boss'); agreement=self.agreement(expenses=[self.expense('500.00',paid_by='partner')],kind='pasture')
        data=self.attach(self.sale(),agreement); response=self.push(sales=[data]); self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(AnimalSale.objects.get().lines[0]['settlement']['partner_reimbursement'],'500.00')

    def test_invalid_values_and_dates(self):
        self.login('boss')
        for field,value in [('weight_kg','NaN'),('price_per_kg','0'),('weight_kg','1.001')]:
            data=self.sale(); data['lines'][0][field]=value; self.assertEqual(self.push(sales=[data]).status_code,400)
        self.assertEqual(self.push(sales=[self.sale(date='2099-01-01')]).status_code,400)
        data=self.sale(); data['lines']*=2; self.assertEqual(self.push(sales=[data]).status_code,400)

    def test_partial_agreement_terms_cannot_change_and_animal_cannot_reactivate(self):
        self.login('boss'); second=Animal.objects.create(farm=self.farm,tag='REST',sex='M',category='calf')
        agreement=self.agreement([self.animal,second]); data=self.attach(self.sale(),agreement)
        self.assertEqual(self.push(sales=[data]).status_code,200)
        from .serializers import AnimalAgreementSerializer,AnimalSerializer
        payload=dict(AnimalAgreementSerializer(agreement).data); payload['owner_share']='99.00'
        self.assertEqual(self.push(agreements=[payload]).status_code,400)
        self.animal.refresh_from_db(); animal=dict(AnimalSerializer(self.animal).data); animal['status']='active'
        self.assertEqual(self.push(animals=[animal]).status_code,400)
        self.animal.refresh_from_db(); self.assertEqual(self.animal.status,'sold')

    def test_receipt_recovery_is_admin_only_and_farm_scoped(self):
        self.login('boss'); data=self.sale(); self.assertEqual(self.push(sales=[data]).status_code,200)
        params={'farm':str(self.farm.id),'collection':'sales','id':data['id']}
        response=self.client.get('/api/sales/receipt',params); self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.data['record']['total'],'28000.00')
        params['id']=str(uuid.uuid4()); self.assertIsNone(self.client.get('/api/sales/receipt',params).data['record'])
        params['id']='bad'; self.assertEqual(self.client.get('/api/sales/receipt',params).status_code,400)
        self.login(); params['id']=data['id']; self.assertEqual(self.client.get('/api/sales/receipt',params).status_code,403)
