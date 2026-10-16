"""Explicit, counted reset of a single-farm test installation. Never makes backups."""
import json

from django.apps import apps
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Farm, FarmMembership


LABELS = (
    'livestock.SalePayment', 'livestock.AnimalSale',
    'livestock.AnimalAgreement',
    'health.HealthEvent', 'reproduction.ReproductiveEvent',
    'production.Milking', 'production.Weighing', 'livestock.Animal',
    'livestock.Brand', 'livestock.Owner', 'livestock.Paddock', 'livestock.AnimalLot',
)


class Command(BaseCommand):
    help = 'Preview a test-data reset; --execute deletes data without backup and keeps one named admin.'

    def add_arguments(self, parser):
        parser.add_argument('--farm', required=True)
        parser.add_argument('--name', required=True)
        parser.add_argument('--keep-user', required=True)
        parser.add_argument('--expected-records', type=int, required=True)
        parser.add_argument('--expected-users', type=int, required=True)
        parser.add_argument('--execute', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        if Farm.objects.count() != 1:
            raise CommandError('Solo se permite reiniciar una instalación con una única finca.')
        farm = Farm.objects.select_for_update().filter(pk=options['farm']).first()
        if not farm:
            raise CommandError('La finca indicada no existe.')
        user_model = get_user_model()
        users = list(user_model.objects.select_for_update().all())
        admin = next((user for user in users if user.username == options['keep_user']), None)
        if not admin or not admin.is_active or not FarmMembership.objects.filter(user=admin, farm=farm, role='admin').exists():
            raise CommandError('La cuenta a conservar debe ser un administrador activo de esta finca.')
        name = options['name'].strip()
        if not name or len(name) > 150:
            raise CommandError('El nombre de la finca debe tener entre 1 y 150 caracteres.')
        counts = {label: apps.get_model(label).objects.filter(farm=farm).count() for label in LABELS}
        if sum(counts.values()) != options['expected_records'] or len(users) != options['expected_users']:
            raise CommandError('Los conteos cambiaron. Revisá los registros antes de ejecutar la limpieza.')
        summary = {'execute': options['execute'], 'old_name': farm.name, 'new_name': name,
                   'keep_user': admin.username, 'users_to_delete': len(users) - 1,
                   'records_to_delete': counts}
        if options['execute']:
            for label in LABELS:
                apps.get_model(label).objects.filter(farm=farm).delete()
            LogEntry.objects.all().delete()
            Session.objects.all().delete()
            user_model.objects.exclude(pk=admin.pk).delete()
            farm.name = name
            farm.location = ''
            farm.data_version += 1
            farm.save(update_fields=['name', 'location', 'data_version', 'updated_at'])
            summary['data_version'] = farm.data_version
        self.stdout.write(json.dumps(summary, ensure_ascii=False))
