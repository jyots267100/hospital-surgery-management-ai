from __future__ import annotations

from app.core.exceptions import RepositoryError
from app.models.schemas import Surgeon, SurgeryStatus
from app.repositories.surgeon_repository import SurgeonRepository
from app.repositories.surgery_repository import SurgeryRepository
import pytest


def test_list_all_returns_seeded_records(repos):
    surgeries = repos["surgery"].list_all()
    assert len(surgeries) == 4
    assert {s.surgery_id for s in surgeries} == {"S1001", "S1002", "S1003", "S1004"}


def test_get_by_id_found_and_missing(repos):
    assert repos["surgery"].get_by_id("S1001").surgery_id == "S1001"
    assert repos["surgery"].get_by_id("S9999") is None


def test_create_appends_record(data_dir):
    repo = SurgeonRepository(data_dir)
    new_surgeon = Surgeon(surgeon_id="SG099", name="Dr. New Surgeon", specialty="Neurology")
    created = repo.create(new_surgeon)
    assert created.surgeon_id == "SG099"
    assert repo.get_by_id("SG099") is not None
    assert len(repo.list_all()) == 3


def test_create_duplicate_id_raises(data_dir):
    repo = SurgeonRepository(data_dir)
    dup = Surgeon(surgeon_id="SG001", name="Duplicate", specialty="X")
    with pytest.raises(RepositoryError):
        repo.create(dup)


def test_update_persists_change(repos, data_dir):
    repo = repos["surgery"]
    surgery = repo.get_by_id("S1001")
    surgery.status = SurgeryStatus.CONFIRMED
    updated = repo.update("S1001", surgery)
    assert updated.status.value == "confirmed"

    reloaded = SurgeryRepository(data_dir).get_by_id("S1001")
    assert reloaded.status.value == "confirmed"


def test_delete_removes_record(repos):
    assert repos["surgery"].delete("S1001") is True
    assert repos["surgery"].get_by_id("S1001") is None
    assert repos["surgery"].delete("S1001") is False


def test_persistence_survives_new_repository_instance(data_dir):
    repo_a = SurgeonRepository(data_dir)
    repo_a.create(Surgeon(surgeon_id="SG050", name="Persisted", specialty="Y"))

    repo_b = SurgeonRepository(data_dir)
    assert repo_b.get_by_id("SG050") is not None
