"""Offline FastAPI TestClient tests for TruthLens API and SQLite persistence."""
from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.session import get_db
from app.main import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary SQLite database for each test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db_url = f"sqlite:///{self.db_path}"

        self.engine = create_engine(self.db_url, connect_args={"check_same_thread": False})
        self.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        self.app = create_app()

        def override_get_db():
            db = self.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_health_check(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["version"], "0.1.0")
        self.assertEqual(data["database"], "connected")

    def test_list_providers(self):
        response = self.client.get("/api/providers")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("providers", data)
        self.assertTrue(len(data["providers"]) > 0)
        for p in data["providers"]:
            self.assertIn("provider", p)
            self.assertIn("configured", p)
            self.assertIn("setup_hint", p)
            # Ensure no raw secrets exist
            self.assertNotIn("sk-", str(p))

    def test_successful_evaluation(self):
        payload = {
            "question": "When was the Eiffel Tower built?",
            "answer": "The Eiffel Tower was completed in 1889. The tower is 330 metres tall.",
            "sources": [
                {
                    "id": "S1",
                    "text": "The Eiffel Tower was completed in 1889. The tower is 330 metres tall.",
                    "title": "Tower info",
                }
            ],
            "config": {
                "verifier_type": "rule_based",
                "max_concurrency": 2,
            },
        }
        response = self.client.post("/api/evaluations", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("run_id", data)
        self.assertEqual(data["status"], "completed")
        self.assertEqual(len(data["claims"]), 2)
        self.assertEqual(len(data["verifications"]), 2)
        for v in data["verifications"]:
            self.assertEqual(v["classification"], "SUPPORTED")
        self.assertEqual(data["metrics"]["supported"], 2)
        self.assertEqual(data["metrics"]["errors"], 0)

    def test_invalid_requests_handled(self):
        # 1. Empty question -> 400 Bad Request
        res1 = self.client.post(
            "/api/evaluations",
            json={"question": "   ", "answer": "Valid answer text.", "sources": [{"text": "Source text"}]},
        )
        self.assertEqual(res1.status_code, 400)
        self.assertIn("Question is required", res1.json()["detail"])

        # 2. Empty answer -> 400 Bad Request
        res2 = self.client.post(
            "/api/evaluations",
            json={"question": "Valid question?", "answer": "", "sources": [{"text": "Source text"}]},
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn("Answer is required", res2.json()["detail"])

        # 3. Empty sources list -> 400 Bad Request
        res3 = self.client.post(
            "/api/evaluations",
            json={"question": "Valid question?", "answer": "Valid answer.", "sources": []},
        )
        self.assertEqual(res3.status_code, 400)
        self.assertIn("At least one source document is required", res3.json()["detail"])

        # 4. Invalid source URL -> 400 Bad Request
        res4 = self.client.post(
            "/api/evaluations",
            json={
                "question": "Valid question?",
                "answer": "Valid answer.",
                "sources": [{"text": "Source text", "url": "javascript:alert(1)"}],
            },
        )
        self.assertEqual(res4.status_code, 400)
        self.assertIn("only http(s) URLs are accepted", res4.json()["detail"])

        # 5. Invalid body types -> 422 Unprocessable Entity
        res5 = self.client.post("/api/evaluations", json={"question": 12345})
        self.assertEqual(res5.status_code, 422)

    def test_persistence_and_application_restart(self):
        """Verify report persistence across distinct application and engine lifecycles."""
        payload = {
            "question": "When was it built?",
            "answer": "The bridge opened in 1932.",
            "sources": [{"id": "S1", "text": "The bridge opened in 1932."}],
        }
        # Step 1: Create evaluation with first client
        post_res = self.client.post("/api/evaluations", json=payload)
        self.assertEqual(post_res.status_code, 201)
        run_id = post_res.json()["run_id"]

        # Step 2: Simulate application shutdown by disposing engine and clearing overrides
        self.app.dependency_overrides.clear()
        self.engine.dispose()

        # Step 3: Simulate application restart by creating a new app, new engine pointing to same db_url
        new_engine = create_engine(self.db_url, connect_args={"check_same_thread": False})
        NewSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=new_engine)
        restarted_app = create_app()

        def restart_get_db():
            db = NewSessionLocal()
            try:
                yield db
            finally:
                db.close()

        restarted_app.dependency_overrides[get_db] = restart_get_db
        restarted_client = TestClient(restarted_app)

        # Step 4: Retrieve evaluation from restarted application
        get_res = restarted_client.get(f"/api/evaluations/{run_id}")
        self.assertEqual(get_res.status_code, 200)
        data = get_res.json()
        self.assertEqual(data["run_id"], run_id)
        self.assertEqual(data["question"], "When was it built?")
        self.assertEqual(data["answer"], "The bridge opened in 1932.")
        self.assertEqual(data["claims"][0]["text"], "The bridge opened in 1932.")
        self.assertEqual(data["verifications"][0]["classification"], "SUPPORTED")

        new_engine.dispose()

    def test_report_retrieval(self):
        payload = {
            "question": "When was the Eiffel Tower built?",
            "answer": "The Eiffel Tower was completed in 1889.",
            "sources": [{"id": "S1", "text": "The Eiffel Tower was completed in 1889."}],
        }
        post_res = self.client.post("/api/evaluations", json=payload)
        run_id = post_res.json()["run_id"]

        get_res = self.client.get(f"/api/evaluations/{run_id}")
        self.assertEqual(get_res.status_code, 200)
        data = get_res.json()
        self.assertEqual(data["run_id"], run_id)
        self.assertIn("metric_definitions", data)
        self.assertIn("limitations", data)
        self.assertEqual(data["metrics"]["supported"], 1)

    def test_json_export(self):
        payload = {
            "question": "When was the Eiffel Tower built?",
            "answer": "The Eiffel Tower was completed in 1889.",
            "sources": [{"id": "S1", "text": "The Eiffel Tower was completed in 1889."}],
        }
        post_res = self.client.post("/api/evaluations", json=payload)
        run_id = post_res.json()["run_id"]

        export_res = self.client.get(f"/api/evaluations/{run_id}/export?format=json")
        self.assertEqual(export_res.status_code, 200)
        self.assertIn("application/json", export_res.headers.get("content-type", ""))
        self.assertIn(f'filename="truthlens-{run_id}.json"', export_res.headers.get("content-disposition", ""))

        data = json.loads(export_res.text)
        self.assertEqual(data["run_id"], run_id)
        self.assertIn("metric_definitions", data)

    def test_csv_export(self):
        payload = {
            "question": "When was the Eiffel Tower built?",
            "answer": "The Eiffel Tower was completed in 1889. The tower is 330 metres tall.",
            "sources": [{"id": "S1", "text": "The Eiffel Tower was completed in 1889. The tower is 330 metres tall."}],
        }
        post_res = self.client.post("/api/evaluations", json=payload)
        run_id = post_res.json()["run_id"]

        export_res = self.client.get(f"/api/evaluations/{run_id}/export?format=csv")
        self.assertEqual(export_res.status_code, 200)
        self.assertIn("text/csv", export_res.headers.get("content-type", ""))
        self.assertIn(f'filename="truthlens-{run_id}.csv"', export_res.headers.get("content-disposition", ""))

        reader = list(csv.reader(io.StringIO(export_res.text)))
        headers = reader[0]
        self.assertEqual(headers[0], "claim_id")
        self.assertEqual(headers[1], "claim_text")
        self.assertEqual(len(reader), 3)  # header + 2 claims

    def test_missing_and_invalid_run_ids(self):
        # 404 for unknown run_id
        res1 = self.client.get("/api/evaluations/non-existent-uuid")
        self.assertEqual(res1.status_code, 404)
        self.assertIn("not found", res1.json()["detail"])

        # 404 for export of unknown run_id
        res2 = self.client.get("/api/evaluations/non-existent-uuid/export?format=json")
        self.assertEqual(res2.status_code, 404)

        # Create valid evaluation to test invalid export formats
        payload = {
            "question": "q",
            "answer": "The Eiffel Tower was completed in 1889.",
            "sources": [{"id": "S1", "text": "The Eiffel Tower was completed in 1889."}],
        }
        post_res = self.client.post("/api/evaluations", json=payload)
        run_id = post_res.json()["run_id"]

        # 400 for unsupported format
        res3 = self.client.get(f"/api/evaluations/{run_id}/export?format=xml")
        self.assertEqual(res3.status_code, 400)
        self.assertIn("Unsupported export format", res3.json()["detail"])

        # 422 for missing required format query param
        res4 = self.client.get(f"/api/evaluations/{run_id}/export")
        self.assertEqual(res4.status_code, 422)

    def test_list_evaluations(self):
        # Empty list initially
        res = self.client.get("/api/evaluations")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["items"], [])

        # Create two evaluations
        payload1 = {
            "question": "First question?",
            "answer": "First answer with factual content.",
            "sources": [{"id": "S1", "text": "First answer with factual content."}],
        }
        payload2 = {
            "question": "Second question?",
            "answer": "Second answer with factual content.",
            "sources": [{"id": "S1", "text": "Second answer with factual content."}],
        }
        self.client.post("/api/evaluations", json=payload1)
        self.client.post("/api/evaluations", json=payload2)

        res2 = self.client.get("/api/evaluations?limit=10&offset=0")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["total"], 2)
        self.assertEqual(len(data2["items"]), 2)
        # Newest first
        self.assertEqual(data2["items"][0]["question"], "Second question?")
        self.assertEqual(data2["items"][1]["question"], "First question?")
        self.assertIn("metrics", data2["items"][0])
        self.assertIn("total_claims", data2["items"][0]["metrics"])



if __name__ == "__main__":
    unittest.main()
