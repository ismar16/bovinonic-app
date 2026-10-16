from django.test import TestCase

# Create your tests here.
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.core.models import Farm, FarmMembership
from apps.livestock.models import Animal, Brand, Owner


class TestDataResetTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username='admin', password='KeepThisPassword2026!')
        get_user_model().objects.create_user(username='other')
        get_user_model().objects.create_user(username='third')
        self.farm = Farm.objects.create(name='Test farm', location='Test location')
        FarmMembership.objects.create(farm=self.farm, user=self.admin, role='admin')
        owner = Owner.objects.create(farm=self.farm, name='Test owner')
        brand = Brand.objects.create(farm=self.farm, code='TEST', title_owner=owner)
        Animal.objects.create(farm=self.farm, tag='TEST-1', sex='H', category='calf', owner=owner, brand=brand)
        self.options = {'farm': str(self.farm.id), 'name': 'Finca La Bendición', 'keep_user': 'admin',
                        'expected_records': 3, 'expected_users': 3, 'stdout': StringIO()}

    def test_preview_changes_nothing(self):
        call_command('reset_test_data', **self.options)
        self.assertEqual(Animal.objects.count(), 1)
        self.assertEqual(get_user_model().objects.count(), 3)
        self.farm.refresh_from_db()
        self.assertEqual(self.farm.data_version, 0)

    def test_reset_keeps_admin_password_and_renames_empty_farm(self):
        password_hash = self.admin.password
        call_command('reset_test_data', execute=True, **self.options)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.password, password_hash)
        self.assertEqual(Animal.objects.count(), 0)
        self.assertEqual(Owner.objects.count(), 0)
        self.assertEqual(Brand.objects.count(), 0)
        self.farm.refresh_from_db()
        self.assertEqual(self.farm.name, 'Finca La Bendición')
        self.assertEqual(self.farm.location, '')
        self.assertEqual(self.farm.data_version, 1)
        self.assertTrue(FarmMembership.objects.filter(user=self.admin, farm=self.farm, role='admin').exists())

    def test_wrong_counts_or_second_farm_prevent_reset(self):
        with self.assertRaises(CommandError):
            call_command('reset_test_data', execute=True, **{**self.options, 'expected_records': 0})
        Farm.objects.create(name='Must keep')
        with self.assertRaises(CommandError):
            call_command('reset_test_data', execute=True, **self.options)
        self.assertEqual(get_user_model().objects.count(), 3)
        self.assertEqual(Animal.objects.count(), 1)
