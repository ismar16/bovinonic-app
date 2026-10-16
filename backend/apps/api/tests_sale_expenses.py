import uuid
from decimal import Decimal
from django.test import TestCase
from apps.core.models import Farm
from apps.livestock.models import Animal, AnimalSale, SaleExpense, SalePayment
from . import tests_sales


class SaleExpenseTests(TestCase):
    setUp = tests_sales.SaleApiTests.setUp
    login = tests_sales.SaleApiTests.login
    sale = tests_sales.SaleApiTests.sale
    push = tests_sales.SaleApiTests.push
    agreement = tests_sales.SaleApiTests.agreement
    attach = tests_sales.SaleApiTests.attach
    expense = tests_sales.SaleApiTests.expense

    def adjustment(self, sale, **overrides):
        data = {'id':str(uuid.uuid4()), 'sale':sale['id'], 'animal':str(self.animal.id), 'date':'2026-09-15',
                'concept':'Medicamento olvidado', 'amount':'1000.00', 'paid_by':'owner'}
        data.update(overrides)
        return data

    def receipt(self, sale_id):
        response = self.client.get('/api/sales/receipt',{'farm':str(self.farm.id),'collection':'sales','id':sale_id})
        self.assertEqual(response.status_code,200,response.content)
        return response.data['record']

    def test_add_expense_recalculates_closed_agreement_preserves_sale_payments_and_retry(self):
        self.login('boss'); agreement=self.agreement(); sale=self.attach(self.sale(),agreement)
        self.assertEqual(self.push(sales=[sale]).status_code,200)
        original=AnimalSale.objects.get(pk=sale['id']); original_lines=original.lines.copy(); cursor=original.updated_at.isoformat()
        payment={'id':str(uuid.uuid4()),'sale':sale['id'],'date':sale['date'],'amount':'10000','method':'cash'}
        self.assertEqual(self.push(sale_payments=[payment]).status_code,200)
        expense=self.adjustment(sale)
        for _ in range(3):
            response=self.push(sale_expenses=[expense]); self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(SaleExpense.objects.count(),1)
        record=self.receipt(sale['id']); line=record['lines'][0]
        self.assertEqual(line['settlement']['net_gain'],'9000.00')
        self.assertEqual(line['settlement']['owner_total'],'23500.00'); self.assertEqual(line['settlement']['partner_total'],'4500.00')
        self.assertEqual(line['original_settlement']['net_gain'],'10000.00')
        original.refresh_from_db(); self.assertEqual(original.lines,original_lines); self.assertEqual(original.total,Decimal('28000.00'))
        self.assertEqual(SalePayment.objects.get().amount,Decimal('10000.00'))
        agreement.refresh_from_db(); self.assertEqual(agreement.status,'settled'); self.assertEqual(agreement.settlement['net_gain'],'9000.00')
        delta=self.client.get('/api/sync/pull',{'farm':str(self.farm.id),'since':cursor}).data
        self.assertEqual(len(delta['sales']),1); self.assertEqual(len(delta['sale_expenses']),1); self.assertEqual(len(delta['agreements']),1)
        # Re-uploading the original receipt remains idempotent after adjustments.
        self.assertEqual(self.push(sales=[sale]).status_code,200)

    def test_partial_agreement_adjustment_only_changes_sold_animal_then_final_totals(self):
        self.login('boss'); second=Animal.objects.create(farm=self.farm,tag='UNSOLD',sex='M',category='calf')
        agreement=self.agreement([self.animal,second], [self.expense('1000.01')]); sale=self.attach(self.sale(),agreement)
        self.assertEqual(self.push(sales=[sale]).status_code,200)
        response=self.push(sale_expenses=[self.adjustment(sale,amount='500',paid_by='partner')]); self.assertEqual(response.status_code,200,response.content)
        agreement.refresh_from_db(); self.assertEqual(agreement.status,'active'); second.refresh_from_db(); self.assertEqual(second.status,'active')
        last=self.attach(self.sale(second),agreement); self.assertEqual(self.push(sales=[last]).status_code,200)
        agreement.refresh_from_db(); self.assertEqual(agreement.settlement['expenses'],'1500.01')
        self.assertEqual(Decimal(agreement.settlement['owner_total'])+Decimal(agreement.settlement['partner_total']),Decimal('56000.00'))

    def test_multiple_adjustments_and_both_payers_conserve_money(self):
        self.login('boss'); agreement=self.agreement(); sale=self.attach(self.sale(),agreement); self.assertEqual(self.push(sales=[sale]).status_code,200)
        response=self.push(sale_expenses=[self.adjustment(sale,amount='1000'),self.adjustment(sale,amount='500',paid_by='partner')]); self.assertEqual(response.status_code,200,response.content)
        line=self.receipt(sale['id'])['lines'][0]
        self.assertEqual(line['settlement']['expenses'],'1500.00'); self.assertEqual(line['settlement']['net_gain'],'8500.00')
        self.assertEqual(line['settlement']['owner_total'],'23250.00'); self.assertEqual(line['settlement']['partner_total'],'4750.00')

    def test_loss_requires_true_and_batch_rollback(self):
        self.login('boss'); agreement=self.agreement(); sale=self.attach(self.sale(),agreement); self.assertEqual(self.push(sales=[sale]).status_code,200)
        expense=self.adjustment(sale,amount='11000')
        for flag in (False,'true',1):
            expense['accept_loss']=flag; self.assertEqual(self.push(sale_expenses=[expense]).status_code,400)
        expense['accept_loss']=True; self.assertEqual(self.push(sale_expenses=[expense]).status_code,200)
        self.assertEqual(self.receipt(sale['id'])['lines'][0]['settlement']['net_gain'],'-1000.00')
        bad=self.adjustment(sale,amount='-1'); before=SaleExpense.objects.count()
        self.assertEqual(self.push(sale_expenses=[self.adjustment(sale,accept_loss=True),bad]).status_code,400)
        self.assertEqual(SaleExpense.objects.count(),before)

    def test_expenses_are_immutable_and_permissions_farm_and_membership_are_checked(self):
        self.login('boss'); sale=self.sale(); self.assertEqual(self.push(sales=[sale]).status_code,200)
        expense=self.adjustment(sale); self.assertEqual(self.push(sale_expenses=[expense]).status_code,200)
        expense['amount']='2'; self.assertEqual(self.push(sale_expenses=[expense]).status_code,400)
        outsider=self.adjustment(sale,animal=str(self.sold_animal.id)); self.assertEqual(self.push(sale_expenses=[outsider]).status_code,400)
        other=Farm.objects.create(name='Other'); animal=Animal.objects.create(farm=other,tag='PRIVATE-GASTO',sex='M',category='calf')
        self.assertEqual(self.push(sale_expenses=[self.adjustment(sale,animal=str(animal.id))]).status_code,400)
        self.assertEqual(self.push(sale_expenses=[self.adjustment(sale,date='2099-01-01')]).status_code,400)
        self.assertEqual(self.push(sale_expenses=[self.adjustment(sale,amount='NaN')]).status_code,400)
        self.login(); self.assertEqual(self.push(sale_expenses=[self.adjustment(sale)]).status_code,400)
        self.assertEqual(self.client.get('/api/sync/pull',{'farm':str(self.farm.id)}).data['sale_expenses'],[])

    def test_own_animals_and_pasture(self):
        self.login('boss'); sale=self.sale(); self.assertEqual(self.push(sales=[sale]).status_code,200)
        self.assertEqual(self.push(sale_expenses=[self.adjustment(sale,paid_by='partner')]).status_code,400)
        self.assertEqual(self.push(sale_expenses=[self.adjustment(sale)]).status_code,200)
        line=self.receipt(sale['id'])['lines'][0]; self.assertIsNone(line['settlement']); self.assertEqual(line['net_after_expenses'],'27000.00')
        animal=Animal.objects.create(farm=self.farm,tag='PASTURE-GASTO',sex='M',category='calf')
        agreement=self.agreement([animal],kind='pasture'); pasture=self.attach(self.sale(animal),agreement)
        self.assertEqual(self.push(sales=[pasture]).status_code,200)
        response=self.push(sale_expenses=[self.adjustment(pasture,animal=str(animal.id),paid_by='partner',amount='500')]); self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(self.receipt(pasture['id'])['lines'][0]['settlement']['partner_reimbursement'],'500.00')
