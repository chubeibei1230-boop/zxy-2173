import pytest
from storage import storage
from models import (
    DeliveryArchiveCreate, ArchiveSourceType,
    DeliveryArchive, ArchiveFilterParams
)


def test_storage_instance_exists():
    assert storage is not None
    assert hasattr(storage, "cards")
    assert hasattr(storage, "resample_applications")
    assert hasattr(storage, "delivery_archives")
    print("[OK] Storage 实例存在，包含所需字段")
