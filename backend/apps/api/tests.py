import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Farm, FarmMembership
from apps.livestock.models import Animal, Brand, Owner, Paddock
from apps.health.models import HealthEvent
from apps.production.models import Milking, Weighing
from apps.reproduction.models import ReproductiveEvent
from .serializers import OwnerSerializer

User = get_user_model()


class SyncApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="op1", password="pass1234")
        self.admin_user = User.objects.create_user(username="boss", password="pass1234")
        self.farm = Farm.objects.create(name="Hacienda Test")
        FarmMembership.objects.create(
            user=self.user, farm=self.farm, role=FarmMembership.Role.OPERATOR
        )
        FarmMembership.objects.create(
            user=self.admin_user, farm=self.farm, role=FarmMembership.Role.ADMIN
        )
        self.owner = Owner.objects.create(farm=self.farm, name="Juan")
        self.animal = Animal.objects.create(
            farm=self.farm, tag="NI-100", sex="H",
            category="cow_lactating", owner=self.owner,
        )
        self.sold_animal = Animal.objects.create(
            farm=self.farm, tag="NI-101", sex="H",
            category="cow_dry", status="sold", owner=self.owner,
        )
        self.client = APIClient()

    def login(self, username="op1"):
        response = self.client.post(
            "/api/auth/login", {"username": username, "password": "pass1234"}
        )
        assert response.status_code == 200, response.content
        return response

    def test_login_sets_httponly_cookies(self):
        response = self.login()
        self.assertIn("ganaderia_access", response.cookies)
        self.assertIn("ganaderia_refresh", response.cookies)
        self.assertTrue(response.cookies["ganaderia_access"]["httponly"])

    def test_me_requires_auth(self):
        response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_batch_sync_creates_and_is_idempotent(self):
        self.login()
        weighing_id = str(uuid.uuid4())
        payload = {
            "farm": str(self.farm.id),
            "weighings": [
                {
                    "id": weighing_id,
                    "animal": str(self.animal.id),
                    "date": "2026-09-28",
                    "weight_kg": "250.50",
                }
            ],
        }
        response = self.client.post("/api/sync/batch", payload, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["results"]["weighings"][0]["status"], "created")
        self.assertEqual(Weighing.objects.count(), 1)
        self.assertEqual(str(Weighing.objects.first().id), weighing_id)
        self.assertEqual(Weighing.objects.first().farm_id, self.farm.id)

        payload["weighings"][0]["weight_kg"] = "251.00"
        response = self.client.post("/api/sync/batch", payload, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["results"]["weighings"][0]["status"], "updated")
        self.assertEqual(Weighing.objects.count(), 1)
        self.assertEqual(float(Weighing.objects.first().weight_kg), 251.0)

    def test_historical_warning_on_sold_animal(self):
        self.login()
        payload = {
            "farm": str(self.farm.id),
            "milkings": [
                {
                    "id": str(uuid.uuid4()),
                    "animal": str(self.sold_animal.id),
                    "date": "2026-09-27",
                    "shift": "AM",
                    "liters": "7.25",
                }
            ],
        }
        response = self.client.post("/api/sync/batch", payload, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        entry = response.data["results"]["milkings"][0]
        self.assertTrue(entry["historical_warning"])
        self.assertEqual(Milking.objects.count(), 1)

    def test_operator_cannot_write_reproductive_events(self):
        self.login()
        payload = {
            "farm": str(self.farm.id),
            "reproductive_events": [
                {
                    "id": str(uuid.uuid4()),
                    "animal": str(self.animal.id),
                    "date": "2026-09-28",
                    "type": "service",
                    "service_method": "ai",
                }
            ],
        }
        response = self.client.post("/api/sync/batch", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ReproductiveEvent.objects.count(), 0)

        self.login("boss")
        response = self.client.post("/api/sync/batch", payload, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        event = ReproductiveEvent.objects.get()
        self.assertIsNotNone(event.estimated_calving_date)
        self.assertIsNotNone(event.suggested_drying_off_date)

    def test_batch_is_atomic_on_validation_error(self):
        self.login("boss")
        payload = {
            "farm": str(self.farm.id),
            "weighings": [
                {
                    "id": str(uuid.uuid4()),
                    "animal": str(self.animal.id),
                    "date": "2026-09-28",
                    "weight_kg": "100",
                }
            ],
            "milkings": [
                {
                    "id": str(uuid.uuid4()),
                    "animal": str(self.animal.id),
                    "date": "2026-09-28",
                    "shift": "XX",
                    "liters": "5",
                }
            ],
        }
        response = self.client.post("/api/sync/batch", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Weighing.objects.count(), 0)
        self.assertEqual(Milking.objects.count(), 0)

    def test_pull_returns_farm_data_and_delta(self):
        self.login()
        response = self.client.get(f"/api/sync/pull?farm={self.farm.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["animals"]), 2)
        self.assertEqual(len(response.data["owners"]), 1)

        since = Animal.objects.order_by("-updated_at").first().updated_at.isoformat()
        response = self.client.get(f"/api/sync/pull?farm={self.farm.id}&since={since}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["animals"]), 0)

    def test_no_membership_no_access(self):
        outsider = User.objects.create_user(username="outsider", password="pass1234")
        self.client.post(
            "/api/auth/login", {"username": "outsider", "password": "pass1234"}
        )
        response = self.client.get(f"/api/sync/pull?farm={self.farm.id}")
        self.assertEqual(response.status_code, 403)

    def test_animal_create_and_idempotent_resend(self):
        self.login("boss")
        animal_id = str(uuid.uuid4())
        payload = {
            "farm": str(self.farm.id),
            "animals": [
                {
                    "id": animal_id,
                    "tag": "NEW-001",
                    "name": "Nueva Vaca",
                    "sex": "H",
                    "category": "calf",
                    "birth_date": None,
                    "mother": None,
                    "father": None,
                    "paddock": None,
                    "owner": str(self.owner.id),
                    "brand": None,
                    "status": "active",
                }
            ],
        }
        response = self.client.post("/api/sync/batch", payload, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["results"]["animals"][0]["status"], "created")

        response = self.client.post("/api/sync/batch", payload, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["results"]["animals"][0]["status"], "updated")
        self.assertEqual(Animal.objects.filter(tag="NEW-001").count(), 1)

    def test_duplicate_milking_merges_into_existing(self):
        self.login()
        first_id = str(uuid.uuid4())
        second_id = str(uuid.uuid4())
        payload = {
            "farm": str(self.farm.id),
            "milkings": [
                {
                    "id": first_id,
                    "animal": str(self.animal.id),
                    "date": "2026-09-29",
                    "shift": "AM",
                    "liters": "5.00",
                },
                {
                    "id": second_id,
                    "animal": str(self.animal.id),
                    "date": "2026-09-29",
                    "shift": "AM",
                    "liters": "6.50",
                },
            ],
        }
        response = self.client.post("/api/sync/batch", payload, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Milking.objects.count(), 1)
        self.assertEqual(float(Milking.objects.get().liters), 6.50)
        entries = response.data["results"]["milkings"]
        self.assertEqual(entries[0]["status"], "created")
        self.assertEqual(entries[1]["status"], "updated")
        self.assertEqual(entries[1]["id"], second_id)
        self.assertIn("merged_into", entries[1])

    def test_conflict_flag_when_server_record_is_newer(self):
        self.login("boss")
        animal_id = str(uuid.uuid4())
        payload = {
            "farm": str(self.farm.id),
            "animals": [
                {
                    "id": animal_id,
                    "tag": "CONF-001",
                    "name": "V1",
                    "sex": "H",
                    "category": "calf",
                    "birth_date": None,
                    "mother": None,
                    "father": None,
                    "paddock": None,
                    "owner": None,
                    "brand": None,
                    "status": "active",
                }
            ],
        }
        response = self.client.post("/api/sync/batch", payload, format="json")
        self.assertEqual(response.status_code, 200, response.content)

        payload["animals"][0]["name"] = "V2-older-copy"
        payload["animals"][0]["updated_at"] = "2020-01-01T00:00:00+00:00"
        response = self.client.post("/api/sync/batch", payload, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        entry = response.data["results"]["animals"][0]
        self.assertEqual(entry["status"], "updated")
        self.assertTrue(entry["conflict"])

    def test_catalog_sync_admin_only(self):
        paddock_id = str(uuid.uuid4())
        payload = {
            "farm": str(self.farm.id),
            "paddocks": [{"id": paddock_id, "name": "Potrero Sur"}],
        }
        response = self.client.post("/api/sync/batch", payload, format="json")
        self.assertEqual(response.status_code, 401)

        self.login()
        response = self.client.post("/api/sync/batch", payload, format="json")
        self.assertEqual(response.status_code, 400)

        self.login("boss")
        response = self.client.post("/api/sync/batch", payload, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        from apps.livestock.models import Paddock

        self.assertEqual(Paddock.objects.filter(name="Potrero Sur").count(), 1)
        response = self.client.post("/api/sync/batch", payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Paddock.objects.filter(name="Potrero Sur").count(), 1)

    def test_manage_users_admin_only(self):
        self.login("boss")
        response = self.client.post(
            "/api/manage/users",
            {
                "farm": str(self.farm.id),
                "username": "tecnico1",
                "password": "password123",
                "role": "technician",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        response = self.client.get(f"/api/manage/users?farm={self.farm.id}")
        self.assertEqual(response.status_code, 200)
        usernames = [u["username"] for u in response.data]
        self.assertIn("tecnico1", usernames)

        self.login()
        response = self.client.get(f"/api/manage/users?farm={self.farm.id}")
        self.assertEqual(response.status_code, 403)

    def test_offline_stress_100_records_idempotent_resend(self):
        self.login()
        animals = [
            Animal.objects.create(
                farm=self.farm, tag=f"STRESS-{i:03d}", sex="H", category="cow_lactating"
            )
            for i in range(50)
        ]
        weighings = [
            {
                "id": str(uuid.uuid4()),
                "animal": str(a.id),
                "date": "2026-09-28",
                "weight_kg": "200.00",
            }
            for a in animals[:50]
        ]
        milkings = [
            {
                "id": str(uuid.uuid4()),
                "animal": str(a.id),
                "date": "2026-09-28",
                "shift": "AM",
                "liters": "6.50",
            }
            for a in animals[25:]
        ]
        milkings_pm = [
            {
                "id": str(uuid.uuid4()),
                "animal": str(a.id),
                "date": "2026-09-28",
                "shift": "PM",
                "liters": "5.75",
            }
            for a in animals[:25]
        ]
        batch = {
            "farm": str(self.farm.id),
            "weighings": weighings,
            "milkings": milkings + milkings_pm,
        }
        assert len(weighings) + len(milkings) + len(milkings_pm) == 100

        response = self.client.post("/api/sync/batch", batch, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Weighing.objects.count(), 50)
        self.assertEqual(Milking.objects.count(), 50)

        # Reintento tras caída de red: mismo lote completo, no debe duplicar
        response = self.client.post("/api/sync/batch", batch, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Weighing.objects.count(), 50)
        self.assertEqual(Milking.objects.count(), 50)
        statuses = [
            entry["status"]
            for entries in response.data["results"].values()
            for entry in entries
        ]
        self.assertEqual(len(statuses), 100)
        self.assertTrue(all(s == "updated" for s in statuses))

        # Pull devuelve exactamente lo sincronizado, sin pérdida
        response = self.client.get(f"/api/sync/pull?farm={self.farm.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["weighings"]), 50)
        self.assertEqual(len(response.data["milkings"]), 50)

    def test_events_reject_animals_from_another_farm(self):
        self.client.force_authenticate(self.admin_user)
        other_farm = Farm.objects.create(name="Otra finca")
        foreign_animal = Animal.objects.create(
            farm=other_farm, tag="FOREIGN", sex="H", category="cow_lactating"
        )
        events = [
            ("weighings", Weighing, {"weight_kg": "250"}),
            ("milkings", Milking, {"shift": "AM", "liters": "6"}),
            ("reproductive_events", ReproductiveEvent, {"type": "heat"}),
            ("health_events", HealthEvent, {"type": "vaccine", "product": "Vacuna"}),
        ]
        for collection, model, fields in events:
            with self.subTest(collection=collection):
                response = self.client.post("/api/sync/batch", {
                    "farm": str(self.farm.id), collection: [{
                        "id": str(uuid.uuid4()), "animal": str(foreign_animal.id),
                        "date": "2026-09-28", **fields,
                    }],
                }, format="json")
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn("animal", response.data["errors"][collection][0]["error"])
                self.assertFalse(model.objects.exists())

    def test_animal_and_brand_reject_foreign_farm_relations(self):
        self.client.force_authenticate(self.admin_user)
        other = Farm.objects.create(name="Otra finca")
        owner = Owner.objects.create(farm=other, name="Propietario externo")
        brand = Brand.objects.create(farm=other, code="EXT")
        paddock = Paddock.objects.create(farm=other, name="Externo")
        mother = Animal.objects.create(farm=other, tag="MOTHER", sex="H", category="cow_dry")
        father = Animal.objects.create(farm=other, tag="FATHER", sex="M", category="bull")
        for field, related in [("owner", owner), ("brand", brand), ("paddock", paddock),
                               ("mother", mother), ("father", father)]:
            with self.subTest(field=field):
                response = self.client.post("/api/sync/batch", {
                    "farm": str(self.farm.id), "animals": [{
                        "id": str(uuid.uuid4()), "tag": "REJECTED", "sex": "H",
                        "category": "calf", field: str(related.id),
                    }],
                }, format="json")
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn(field, response.data["errors"]["animals"][0]["error"])
        response = self.client.post("/api/sync/batch", {
            "farm": str(self.farm.id), "brands": [{
                "id": str(uuid.uuid4()), "code": "REJECTED", "title_owner": str(owner.id),
            }],
        }, format="json")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Animal.objects.filter(tag="REJECTED").exists())
        self.assertFalse(Brand.objects.filter(code="REJECTED").exists())

    def test_foreign_event_uuid_cannot_be_overwritten(self):
        self.client.force_authenticate(self.admin_user)
        other = Farm.objects.create(name="Otra finca")
        animal = Animal.objects.create(farm=other, tag="OTHER", sex="H", category="calf")
        weighing = Weighing.objects.create(animal=animal, date="2026-09-28", weight_kg="200")
        response = self.client.post("/api/sync/batch", {
            "farm": str(self.farm.id), "weighings": [{
                "id": str(weighing.id), "animal": str(self.animal.id),
                "date": "2026-09-28", "weight_kg": "999",
            }],
        }, format="json")
        self.assertEqual(response.status_code, 400)
        weighing.refresh_from_db()
        self.assertEqual(weighing.animal_id, animal.id)
        self.assertEqual(float(weighing.weight_kg), 200)

    def test_pull_cursor_preserves_changes_made_during_download(self):
        self.client.force_authenticate(self.user)
        original = OwnerSerializer.to_representation

        def serialize_then_update(serializer, instance):
            data = original(serializer, instance)
            instance.name = "Modificado durante la descarga"
            instance.save()
            return data

        with patch.object(OwnerSerializer, "to_representation", serialize_then_update):
            first = self.client.get("/api/sync/pull", {"farm": str(self.farm.id)})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["owners"][0]["name"], "Juan")
        second = self.client.get("/api/sync/pull", {
            "farm": str(self.farm.id), "since": first.data["sync_cursor"],
        })
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["owners"][0]["name"], "Modificado durante la descarga")

    def test_pull_rejects_invalid_or_naive_cursor(self):
        self.client.force_authenticate(self.user)
        for cursor in ["invalid", "2026-99-99T00:00:00Z", "2026-09-28T00:00:00"]:
            with self.subTest(cursor=cursor):
                response = self.client.get("/api/sync/pull", {
                    "farm": str(self.farm.id), "since": cursor,
                })
                self.assertEqual(response.status_code, 400, response.content)

    def test_new_catalogs_and_animal_sync_in_dependency_order(self):
        self.client.force_authenticate(self.admin_user)
        owner_id, paddock_id, animal_id = [str(uuid.uuid4()) for _ in range(3)]
        response = self.client.post("/api/sync/batch", {
            "farm": str(self.farm.id),
            "animals": [{"id": animal_id, "tag": "OFFLINE-NEW", "sex": "H",
                         "category": "calf", "owner": owner_id, "paddock": paddock_id}],
            "owners": [{"id": owner_id, "name": "Propietario nuevo"}],
            "paddocks": [{"id": paddock_id, "name": "Potrero nuevo"}],
        }, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        animal = Animal.objects.get(pk=animal_id)
        self.assertEqual(str(animal.owner_id), owner_id)
        self.assertEqual(str(animal.paddock_id), paddock_id)

    def test_invalid_production_quantities_do_not_block_the_database(self):
        self.client.force_authenticate(self.user)
        for collection, fields in [
            ("weighings", {"weight_kg": "-1"}),
            ("weighings", {"weight_kg": "0"}),
            ("milkings", {"liters": "-1", "shift": "AM"}),
        ]:
            with self.subTest(collection=collection, fields=fields):
                response = self.client.post("/api/sync/batch", {
                    "farm": str(self.farm.id), collection: [{
                        "id": str(uuid.uuid4()), "animal": str(self.animal.id),
                        "date": "2026-10-15", **fields,
                    }],
                }, format="json")
                self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Weighing.objects.exists())
        self.assertFalse(Milking.objects.exists())
