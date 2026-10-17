import copy
import uuid
from decimal import Decimal
from django.test import TestCase
from apps.core.models import Farm, FarmMembership
from apps.livestock.models import Animal, AnimalSale, AnimalAgreement, PasturePayment, SalePayment
from apps.livestock.sales import effective_sale_lines
from . import tests_sales
from .serializers import AnimalAgreementSerializer


class PasturePaymentTests(TestCase):
    setUp = tests_sales.SaleApiTests.setUp
    login = tests_sales.SaleApiTests.login
    agreement = tests_sales.SaleApiTests.agreement
    push = tests_sales.SaleApiTests.push
    sale = tests_sales.SaleApiTests.sale
    attach = tests_sales.SaleApiTests.attach
    expense = tests_sales.SaleApiTests.expense

    def payment(self, agreement, **changes):
        data={'id':str(uuid.uuid4()),'agreement':str(agreement.id),'period':'2026-09-01','date':'2026-10-01',
              'price_per_animal':'200.10','animal_ids':[r['animal'] for r in agreement.animals],'notes':''}
        data.update(changes);return data

    def test_fifteen_animals_calculate_server_total_retry_and_keep_agreement_originals(self):
        self.login('boss');animals=[self.animal]+[Animal.objects.create(farm=self.farm,tag=f'RENT-{i}',sex='M',category='calf') for i in range(14)]
        agreement=self.agreement(animals,kind='pasture');before=copy.deepcopy(agreement.animals);old=agreement.updated_at
        payment=self.payment(agreement,total='1',currency='USD',recipient='Forjado')
        for _ in range(2):
            response=self.push(pasture_payments=[payment]);self.assertEqual(response.status_code,200,response.content)
        stored=PasturePayment.objects.get();self.assertEqual(stored.total,Decimal('3001.50'));self.assertEqual(stored.currency,'NIO');self.assertEqual(stored.recipient,'Socio')
        agreement.refresh_from_db();self.assertEqual(agreement.animals,before);self.assertEqual(agreement.expenses,[]);self.assertEqual(agreement.status,'active');self.assertGreater(agreement.updated_at,old)
        data=self.client.get('/api/sync/pull',{'farm':str(self.farm.id),'since':old.isoformat()}).data
        self.assertEqual(len(data['pasture_payments']),1);self.assertEqual(len(data['agreements'][0]['pasture_costs']),15)

    def test_duplicate_animal_month_rejected_but_another_month_or_remaining_animals_allowed(self):
        self.login('boss');other=Animal.objects.create(farm=self.farm,tag='RENT-OTHER',sex='H',category='cow_dry')
        agreement=self.agreement([self.animal,other],kind='pasture')
        self.assertEqual(self.push(pasture_payments=[self.payment(agreement,animal_ids=[str(self.animal.id)])]).status_code,200)
        self.assertEqual(self.push(pasture_payments=[self.payment(agreement)]).status_code,400)
        self.assertEqual(self.push(pasture_payments=[self.payment(agreement,animal_ids=[str(other.id)])]).status_code,200)
        self.assertEqual(self.push(pasture_payments=[self.payment(agreement,period='2026-10-01')]).status_code,200)
        self.assertEqual(PasturePayment.objects.count(),3)

    def test_permissions_privacy_and_cross_farm_and_kind(self):
        self.login('boss');agreement=self.agreement(kind='pasture');payment=self.payment(agreement)
        alien=Farm.objects.create(name='Other');other=Animal.objects.create(farm=alien,tag='RENT-ALIEN',sex='M',category='calf')
        self.assertEqual(self.push(pasture_payments=[{**payment,'animal_ids':[str(other.id)]}]).status_code,400)
        other_agreement=self.agreement();self.assertEqual(self.push(pasture_payments=[self.payment(other_agreement)]).status_code,400)
        self.assertEqual(self.push(pasture_payments=[payment]).status_code,200)
        for role in ['operator','technician']:
            FarmMembership.objects.filter(user=self.user,farm=self.farm).update(role=role);self.login()
            self.assertEqual(self.push(pasture_payments=[payment]).status_code,400)
            self.assertEqual(self.client.get('/api/sync/pull',{'farm':str(self.farm.id)}).data['pasture_payments'],[])
            self.assertEqual(self.client.get('/api/sales/receipt',{'farm':str(self.farm.id),'collection':'pasture_payments','id':payment['id']}).status_code,403)

    def test_dates_invalid_amounts_membership_and_atomic_batch(self):
        self.login('boss');agreement=self.agreement(kind='pasture');base=self.payment(agreement)
        patches=[{'period':'2026-09-02'},{'period':'2026-08-01'},{'period':'2099-01-01'},{'date':'2026-08-31'},{'date':'2099-01-01'},{'price_per_animal':'0'},{'price_per_animal':'-1'},{'price_per_animal':'NaN'},{'price_per_animal':'1.001'},{'animal_ids':[]},{'animal_ids':[str(self.animal.id)]*2},{'animal_ids':[str(self.sold_animal.id)]}]
        for patch in patches:self.assertEqual(self.push(pasture_payments=[{**base,**patch}]).status_code,400,patch)
        duplicate=self.payment(agreement)
        self.assertEqual(self.push(pasture_payments=[base,duplicate]).status_code,400);self.assertFalse(PasturePayment.objects.exists())

    def test_confirmed_payment_immutable_and_recoverable_after_response_loss(self):
        self.login('boss');agreement=self.agreement(kind='pasture');payment=self.payment(agreement)
        self.assertEqual(self.push(pasture_payments=[payment]).status_code,200)
        self.assertEqual(self.push(pasture_payments=[{**payment,'price_per_animal':'300'}]).status_code,400)
        self.assertEqual(self.push(pasture_payments=[{**payment,'notes':'Cambiar'}]).status_code,400)
        response=self.client.get('/api/sales/receipt',{'farm':str(self.farm.id),'collection':'pasture_payments','id':payment['id']})
        self.assertEqual(response.status_code,200);self.assertEqual(response.data['record']['total'],'200.10')

    def test_pasture_close_includes_rent_without_copying_it_to_original_expenses(self):
        self.login('boss');agreement=self.agreement(expenses=[self.expense('50',paid_by='partner')],kind='pasture')
        self.assertEqual(self.push(pasture_payments=[self.payment(agreement)]).status_code,200)
        data=dict(AnimalAgreementSerializer(agreement).data);data.update(status='settled',end_date='2026-10-01')
        response=self.push(agreements=[data]);self.assertEqual(response.status_code,200,response.content)
        agreement.refresh_from_db();self.assertEqual(agreement.settlement['expenses'],'250.10');self.assertEqual(agreement.settlement['owner_paid'],'200.10');self.assertEqual(agreement.settlement['partner_reimbursement'],'50.00');self.assertEqual(len(agreement.expenses),1)
        self.assertEqual(self.push(pasture_payments=[self.payment(agreement,period='2026-10-01',date='2026-10-17')]).status_code,200)
        agreement.refresh_from_db();self.assertEqual(agreement.settlement['expenses'],'450.20')

    def test_rent_before_and_after_sale_updates_costs_once_keeps_sale_amount_and_payment(self):
        self.login('boss');agreement=self.agreement(kind='pasture')
        first=self.payment(agreement);self.assertEqual(self.push(pasture_payments=[first]).status_code,200);agreement.refresh_from_db()
        sale=self.attach(self.sale(),agreement);self.assertEqual(self.push(sales=[sale]).status_code,200)
        stored=AnimalSale.objects.get();snapshot=copy.deepcopy(stored.lines);self.assertEqual(effective_sale_lines(stored)[0]['expenses_total'],'200.10')
        payment={'id':str(uuid.uuid4()),'sale':str(stored.id),'date':'2026-10-01','amount':'100','method':'cash','reference':''}
        self.assertEqual(self.push(sale_payments=[payment]).status_code,200)
        later=self.payment(agreement,period='2026-10-01',date='2026-10-17',price_per_animal='300')
        for _ in range(2):self.assertEqual(self.push(pasture_payments=[later]).status_code,200)
        stored.refresh_from_db();self.assertEqual(stored.lines,snapshot);self.assertEqual(stored.total,Decimal('28000'));self.assertEqual(SalePayment.objects.get().amount,Decimal('100'))
        line=effective_sale_lines(stored)[0];self.assertEqual(line['expenses_total'],'500.10');self.assertEqual(line['settlement']['owner_paid'],'500.10');self.assertEqual(len(line['subsequent_pasture_costs']),1)
        agreement.refresh_from_db();self.assertEqual(agreement.settlement['expenses'],'500.10')
        self.assertEqual(self.push(pasture_payments=[self.payment(agreement,period='2026-11-01')]).status_code,400)

    def test_paid_agreement_currency_and_kind_are_protected(self):
        self.login('boss');agreement=self.agreement(kind='pasture');self.assertEqual(self.push(pasture_payments=[self.payment(agreement)]).status_code,200)
        data=dict(AnimalAgreementSerializer(agreement).data)
        for patch in [{'currency':'USD'},{'kind':'weight_gain'},{'start_date':'2026-10-01'}]:
            self.assertEqual(self.push(agreements=[{**data,**patch}]).status_code,400)
