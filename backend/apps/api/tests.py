import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Farm, FarmMembership
from apps.livestock.models import Animal, Owner
from apps.production.models import Milking, Weighing
from apps.reproduction.models import ReproductiveEvent

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
