import sys
import pytest
from fastapi.testclient import TestClient
from main import app
from storage import storage

client = TestClient(app)


@pytest.fixture(scope="session")
def token():
    response = client.post(
        "/token",
        data={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def sample_confirmed_card(token):
    import uuid as _uid
    suffix = _uid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/cards",
        headers=headers,
        json={
            "customer_code": f"FIXTURE-CUST-{suffix}",
            "fabric_type": f"FIXTURE-FAB-{suffix}",
            "color_card_version": "V1",
            "responsible_team": "A组"
        }
    )
    card_id = response.json()["id"]
    client.put(f"/cards/{card_id}/proofing/start", headers=headers)
    client.put(
        f"/cards/{card_id}/proofing/complete",
        headers=headers,
        json={"dye_vat_batch": f"BATCH-{suffix}", "proofing_process": "测试染色"}
    )
    client.put(
        f"/cards/{card_id}/inspection",
        headers=headers,
        json={
            "color_comparison_result": "ΔE=0.4",
            "color_difference_value": 0.4,
            "inspector": "质检员A",
            "conclusion": "合格"
        }
    )
    client.put(
        f"/cards/{card_id}/confirm",
        headers=headers,
        json={"result": "通过", "confirmer": "客户测试员"}
    )
    return card_id


@pytest.fixture(scope="session")
def sample_completed_resample(token, sample_confirmed_card):
    import uuid as _uid
    suffix = _uid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/resample",
        headers=headers,
        json={
            "original_card_id": sample_confirmed_card,
            "reason": f"测试复样-{suffix}",
            "applicant": "测试业务员",
            "expected_completion_date": "2025-06-30",
            "customer_feedback": "客户反馈",
            "priority": "中"
        }
    )
    app_id = response.json()["id"]
    client.put(f"/resample/{app_id}/accept", headers=headers,
               json={"operator": "测试主管", "remark": "同意"})
    client.put(f"/resample/{app_id}/proofing/start", headers=headers,
               json={"operator": "测试打样员"})
    client.put(
        f"/resample/{app_id}/proofing/complete",
        headers=headers,
        json={"dye_vat_batch": f"BATCH-R-{suffix}", "proofing_process": "复样染色", "operator": "测试打样员"}
    )
    client.put(
        f"/resample/{app_id}/inspection",
        headers=headers,
        json={
            "color_comparison_result": "ΔE=0.4",
            "color_difference_value": 0.4,
            "inspector": "测试质检员",
            "conclusion": "合格"
        }
    )
    client.put(
        f"/resample/{app_id}/confirm",
        headers=headers,
        json={"result": "通过", "confirmer": "测试客户"}
    )
    client.put(
        f"/resample/{app_id}/complete",
        headers=headers,
        json={"operator": "测试技术员", "remark": "完成"}
    )
    return app_id


@pytest.fixture(scope="session")
def card_id(token):
    import uuid as _uid
    suffix = _uid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/cards",
        headers=headers,
        json={
            "customer_code": f"PYTEST-CUST-{suffix}",
            "fabric_type": f"PYTEST-FAB-{suffix}",
            "color_card_version": "V1",
            "responsible_team": "C组"
        }
    )
    return response.json()["id"]


@pytest.fixture(scope="session")
def app_id(token, card_id):
    import uuid as _uid
    suffix = _uid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer {token}"}

    _card_detail = client.get(f"/cards/{card_id}").json()
    if _card_detail["status"] != "已确认":
        client.put(f"/cards/{card_id}/proofing/start", headers=headers)
        client.put(
            f"/cards/{card_id}/proofing/complete",
            headers=headers,
            json={"dye_vat_batch": f"BATCH-FIX-{suffix}", "proofing_process": "fix染色"}
        )
        client.put(
            f"/cards/{card_id}/inspection",
            headers=headers,
            json={"color_comparison_result": "ΔE=0.4", "color_difference_value": 0.4,
                  "inspector": "质检员A", "conclusion": "合格"}
        )
        client.put(
            f"/cards/{card_id}/confirm",
            headers=headers,
            json={"result": "通过", "confirmer": "fix客户"}
        )

    response = client.post(
        "/resample",
        headers=headers,
        json={
            "original_card_id": card_id,
            "reason": f"pytest fixture 复样-{suffix}",
            "applicant": "pytest业务员",
            "expected_completion_date": "2025-06-30",
            "customer_feedback": "pytest反馈",
            "priority": "中"
        }
    )
    return response.json()["id"]


@pytest.fixture(scope="session")
def resample_app_id(token, sample_confirmed_card):
    return sample_completed_resample.__wrapped__ if hasattr(sample_completed_resample, "__wrapped__") else None


def test_archive_empty_delivery_batch_no(token, sample_confirmed_card):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/archives",
        headers=headers,
        json={
            "source_type": "原色卡",
            "source_id": sample_confirmed_card,
            "delivery_batch_no": "",
            "delivery_target": "测试客户",
            "archivist": "测试归档人"
        }
    )
    assert response.status_code == 422
    print("[OK] 交付批次号为空校验测试通过")


def test_archive_whitespace_delivery_batch_no(token, sample_confirmed_card):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/archives",
        headers=headers,
        json={
            "source_type": "原色卡",
            "source_id": sample_confirmed_card,
            "delivery_batch_no": "   ",
            "delivery_target": "测试客户",
            "archivist": "测试归档人"
        }
    )
    assert response.status_code == 422
    print("[OK] 交付批次号全空格校验测试通过")


def test_archive_empty_delivery_target(token, sample_confirmed_card):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/archives",
        headers=headers,
        json={
            "source_type": "原色卡",
            "source_id": sample_confirmed_card,
            "delivery_batch_no": "VALID-BATCH-001",
            "delivery_target": "",
            "archivist": "测试归档人"
        }
    )
    assert response.status_code == 422
    print("[OK] 交付对象为空校验测试通过")


def test_archive_empty_archivist(token, sample_confirmed_card):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/archives",
        headers=headers,
        json={
            "source_type": "原色卡",
            "source_id": sample_confirmed_card,
            "delivery_batch_no": "VALID-BATCH-002",
            "delivery_target": "测试客户",
            "archivist": ""
        }
    )
    assert response.status_code == 422
    print("[OK] 归档人为空校验测试通过")


def test_resample_archive_contains_original_card_snapshot(token, sample_completed_resample):
    headers = {"Authorization": f"Bearer {token}"}
    import uuid as _uid
    suffix = _uid.uuid4().hex[:8]
    response = client.post(
        "/archives",
        headers=headers,
        json={
            "source_type": "复样申请",
            "source_id": sample_completed_resample,
            "delivery_batch_no": f"SNAPSHOT-TEST-{suffix}",
            "delivery_target": "快照测试客户",
            "delivery_remark": "测试复样归档是否包含原色卡快照",
            "archivist": "快照测试员"
        }
    )
    assert response.status_code == 200, f"归档失败: {response.status_code} {response.text}"
    archive_id = response.json()["id"]

    detail_response = client.get(f"/archives/{archive_id}", headers=headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()

    assert detail["color_card_snapshot"] is not None, "复样归档记录应包含 color_card_snapshot"
    oc_snapshot = detail["color_card_snapshot"]
    assert oc_snapshot["id"] is not None
    assert "proofing_records" in oc_snapshot
    assert "inspection_records" in oc_snapshot
    assert "rework_records" in oc_snapshot
    assert "risk_alerts" in oc_snapshot
    assert "confirmation_record" in oc_snapshot
    assert len(oc_snapshot["proofing_records"]) >= 1
    assert len(oc_snapshot["inspection_records"]) >= 1
    assert oc_snapshot["confirmation_record"] is not None

    assert detail["resample_snapshot"] is not None
    rs_snapshot = detail["resample_snapshot"]
    assert rs_snapshot["original_card_snapshot"] is not None, "复样快照中应包含 original_card_snapshot"
    inner_oc = rs_snapshot["original_card_snapshot"]
    assert inner_oc["id"] == oc_snapshot["id"]
    assert "proofing_records" in inner_oc
    assert "inspection_records" in inner_oc
    assert "rework_records" in inner_oc
    assert "risk_alerts" in inner_oc

    print("[OK] 复样归档包含原色卡完整快照测试通过")


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    print("[OK] 根接口测试通过")

def test_login():
    response = client.post(
        "/token",
        data={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    print("[OK] 登录接口测试通过")
    return token

def test_create_card(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/cards",
        headers=headers,
        json={
            "customer_code": "C100",
            "fabric_type": "棉麻混纺",
            "color_card_version": "V1",
            "responsible_team": "C组"
        }
    )
    assert response.status_code == 200
    card_id = response.json()["id"]
    assert response.json()["status"] == "待打样"
    print("[OK] 创建色卡接口测试通过")
    return card_id

def test_duplicate_card(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/cards",
        headers=headers,
        json={
            "customer_code": "C100",
            "fabric_type": "棉麻混纺",
            "color_card_version": "V1",
            "responsible_team": "C组"
        }
    )
    assert response.status_code == 400
    print("[OK] 重复创建校验测试通过")

def test_get_card(card_id):
    response = client.get(f"/cards/{card_id}")
    assert response.status_code == 200
    assert response.json()["id"] == card_id
    print("[OK] 获取色卡详情测试通过")

def test_list_cards():
    response = client.get("/cards")
    assert response.status_code == 200
    assert "items" in response.json()
    assert "total" in response.json()
    print("[OK] 列表接口测试通过")

def test_filter_cards():
    response = client.get("/cards?customer_code=C100")
    assert response.status_code == 200
    print("[OK] 筛选接口测试通过")

def test_proofing(token, card_id):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.put(
        f"/cards/{card_id}/proofing/start",
        headers=headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "打样中"
    
    response = client.put(
        f"/cards/{card_id}/proofing/complete",
        headers=headers,
        json={
            "dye_vat_batch": "BATCH100",
            "proofing_process": "高温高压染色"
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "待质检"
    print("[OK] 打样提交测试通过")

def test_inspection(token, card_id):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.put(
        f"/cards/{card_id}/inspection",
        headers=headers,
        json={
            "color_comparison_result": "ΔE=0.5",
            "color_difference_value": 0.5,
            "inspector": "质检员张三",
            "conclusion": "合格"
        }
    )
    assert response.status_code == 200
    print("[OK] 质检提交测试通过")

def test_confirm_without_inspection(token):
    headers = {"Authorization": f"Bearer {token}"}
    response2 = client.post(
        "/cards",
        headers=headers,
        json={
            "customer_code": "C101",
            "fabric_type": "纯毛",
            "color_card_version": "V1",
            "responsible_team": "A组"
        }
    )
    card_id2 = response2.json()["id"]
    client.put(
        f"/cards/{card_id2}/proofing/start",
        headers=headers
    )
    client.put(
        f"/cards/{card_id2}/proofing/complete",
        headers=headers,
        json={"dye_vat_batch": "BATCH101", "proofing_process": "低温染色"}
    )
    response = client.put(
        f"/cards/{card_id2}/confirm",
        headers=headers,
        json={"result": "通过", "confirmer": "客户"}
    )
    assert response.status_code == 400
    print("[OK] 确认前质检校验测试通过")

def test_confirm(token, card_id):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.put(
        f"/cards/{card_id}/confirm",
        headers=headers,
        json={"result": "通过", "confirmer": "客户李四"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "已确认"
    print("[OK] 确认色卡测试通过")

def test_stats_high_rework():
    response = client.get("/stats/high-rework-batches")
    assert response.status_code == 200
    print("[OK] 返调高发批次统计测试通过")

def test_stats_pending():
    response = client.get("/stats/pending-inspection")
    assert response.status_code == 200
    print("[OK] 待质检色卡统计测试通过")

def test_stats_cycle():
    response = client.get("/stats/confirmation-cycle")
    assert response.status_code == 200
    print("[OK] 客户确认周期统计测试通过")

def test_risks_detect():
    response = client.get("/risks/detect-all")
    assert response.status_code == 200
    print("[OK] 风险检测测试通过")

def test_export_json(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/export/json", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    print("[OK] JSON导出测试通过")


def test_dashboard_overview(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/dashboard/overview", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "filter_params" in data
    assert "status_summary" in data
    assert "customer_dimension_stats" in data
    assert "team_dimension_stats" in data
    assert "total_count" in data["status_summary"]
    print("[OK] 看板总览接口测试通过")


def test_dashboard_detail(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/dashboard/detail", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "filter_params" in data
    assert "total" in data
    assert "items" in data
    if data["items"]:
        item = data["items"][0]
        assert "card_id" in item
        assert "current_status" in item
        assert "next_suggested_action" in item
        assert "current_risk_status" in item
    print("[OK] 看表明细接口测试通过")


def test_dashboard_filter(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(
        "/dashboard/overview?customer_code=C001&responsible_team=A组",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filter_params"]["customer_code"] == "C001"
    assert data["filter_params"]["responsible_team"] == "A组"
    print("[OK] 看板筛选功能测试通过")


def test_dashboard_date_validation(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(
        "/dashboard/overview?start_date=2025-01-01&end_date=2024-01-01",
        headers=headers
    )
    assert response.status_code == 400
    assert "开始日期不能大于结束日期" in response.json()["detail"]
    print("[OK] 看板日期范围验证测试通过")


def test_dashboard_unauthorized():
    response = client.get("/dashboard/overview")
    assert response.status_code == 401
    print("[OK] 看板未授权访问校验测试通过")


def test_dashboard_pagination(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(
        "/dashboard/detail?skip=0&limit=10",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 10
    print("[OK] 看板分页功能测试通过")


def test_dashboard_fabric_dimension(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/dashboard/overview", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "fabric_dimension_stats" in data
    assert isinstance(data["fabric_dimension_stats"], list)
    print("[OK] 看板面料维度统计测试通过")


def test_dashboard_inspection_record_detail(token, card_id):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(
        f"/dashboard/detail?customer_code=C100",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    if data["items"]:
        item = data["items"][0]
        assert "last_inspection_record" in item
        if item["last_inspection_record"]:
            assert "conclusion" in item["last_inspection_record"]
            assert "inspector" in item["last_inspection_record"]
            assert "color_comparison_result" in item["last_inspection_record"]
    print("[OK] 看表明细质检记录详情测试通过")


def test_dashboard_date_field_filter(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(
        "/dashboard/overview?date_field=创建时间",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filter_params"]["date_field"] == "创建时间"
    print("[OK] 看板时间维度筛选测试通过")


def test_dashboard_confirmed_risk_resolved(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(
        "/dashboard/detail?status=已确认",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        if item["current_status"] == "已确认":
            assert item["current_risk_status"] == "正常"
            assert item["risk_level"] == "none"
    print("[OK] 已确认色卡风险自动解决测试通过")


def test_unauthorized():
    response = client.post(
        "/cards",
        json={
            "customer_code": "C200",
            "fabric_type": "测试",
            "color_card_version": "V1",
            "responsible_team": "A组"
        }
    )
    assert response.status_code == 401
    print("[OK] 未授权访问校验测试通过")


def test_create_resample_application(token, card_id):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/resample",
        headers=headers,
        json={
            "original_card_id": card_id,
            "reason": "客户反馈颜色偏浅，需要调整染色工艺",
            "applicant": "业务员王五",
            "expected_completion_date": "2025-02-01",
            "customer_feedback": "客户认为当前颜色与标准样相比偏浅，希望加深色调",
            "priority": "高"
        }
    )
    assert response.status_code == 200
    app_id = response.json()["id"]
    assert response.json()["status"] == "待受理"
    assert response.json()["priority"] == "高"
    assert response.json()["original_card_id"] == card_id
    assert len(response.json()["action_records"]) > 0
    print("[OK] 创建复样申请测试通过")
    return app_id


def test_create_resample_without_confirmed_card(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/cards",
        headers=headers,
        json={
            "customer_code": "C201",
            "fabric_type": "丝绸",
            "color_card_version": "V1",
            "responsible_team": "B组"
        }
    )
    new_card_id = response.json()["id"]
    response = client.post(
        "/resample",
        headers=headers,
        json={
            "original_card_id": new_card_id,
            "reason": "测试未确认色卡",
            "applicant": "测试员",
            "expected_completion_date": "2025-02-01",
            "customer_feedback": "测试反馈",
            "priority": "中"
        }
    )
    assert response.status_code == 400
    print("[OK] 非确认状态色卡不能发起复样测试通过")


def test_get_resample_application(token, app_id):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(f"/resample/{app_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == app_id
    assert "action_records" in response.json()
    assert "original_confirmation_record" in response.json()
    assert "resample_status" in response.json()
    assert "resample_proofing_records" in response.json()
    print("[OK] 获取复样申请详情测试通过")


def test_list_resample_applications(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/resample", headers=headers)
    assert response.status_code == 200
    assert "items" in response.json()
    assert "total" in response.json()
    print("[OK] 复样申请列表测试通过")


def test_filter_resample_applications(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/resample?status=待受理&priority=高", headers=headers)
    assert response.status_code == 200
    print("[OK] 复样申请筛选测试通过")


def test_accept_resample_application(token, app_id):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.put(
        f"/resample/{app_id}/accept",
        headers=headers,
        json={
            "operator": "主管赵六",
            "remark": "同意复样，请尽快安排"
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "处理中"
    assert len(response.json()["action_records"]) > 1
    print("[OK] 受理复样申请测试通过")


def test_reject_resample_application(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/cards",
        headers=headers,
        json={
            "customer_code": "C202",
            "fabric_type": "尼龙",
            "color_card_version": "V1",
            "responsible_team": "C组"
        }
    )
    card_id = response.json()["id"]
    
    client.put(f"/cards/{card_id}/proofing/start", headers=headers)
    client.put(
        f"/cards/{card_id}/proofing/complete",
        headers=headers,
        json={"dye_vat_batch": "B202", "proofing_process": "常规染色"}
    )
    client.put(
        f"/cards/{card_id}/inspection",
        headers=headers,
        json={
            "color_comparison_result": "ΔE=0.3",
            "color_difference_value": 0.3,
            "inspector": "质检员",
            "conclusion": "合格"
        }
    )
    client.put(
        f"/cards/{card_id}/confirm",
        headers=headers,
        json={"result": "通过", "confirmer": "客户"}
    )
    
    response = client.post(
        "/resample",
        headers=headers,
        json={
            "original_card_id": card_id,
            "reason": "测试驳回",
            "applicant": "测试员",
            "expected_completion_date": "2025-02-01",
            "customer_feedback": "测试",
            "priority": "低"
        }
    )
    app_id = response.json()["id"]
    
    response = client.put(
        f"/resample/{app_id}/reject",
        headers=headers,
        json={
            "operator": "主管",
            "reason": "申请理由不充分，暂不批准"
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "已驳回"
    assert response.json()["rejection_reason"] == "申请理由不充分，暂不批准"
    print("[OK] 驳回复样申请测试通过")


def test_complete_resample_application(token, app_id):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.put(
        f"/resample/{app_id}/complete",
        headers=headers,
        json={
            "operator": "技术员钱七",
            "remark": "复样完成，颜色已调整到位，符合客户要求"
        }
    )
    assert response.status_code == 400
    assert "当前复样状态" in response.json()["detail"]
    print("[OK] 未确认前不能完成复样测试通过")


def test_follow_up_before_accept_rejected(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/cards",
        headers=headers,
        json={
            "customer_code": "C203",
            "fabric_type": "羊毛",
            "color_card_version": "V1",
            "responsible_team": "A组"
        }
    )
    card_id = response.json()["id"]
    client.put(f"/cards/{card_id}/proofing/start", headers=headers)
    client.put(
        f"/cards/{card_id}/proofing/complete",
        headers=headers,
        json={"dye_vat_batch": "B203", "proofing_process": "低温染色"}
    )
    client.put(
        f"/cards/{card_id}/inspection",
        headers=headers,
        json={
            "color_comparison_result": "ΔE=0.2",
            "color_difference_value": 0.2,
            "inspector": "质检员",
            "conclusion": "合格"
        }
    )
    client.put(
        f"/cards/{card_id}/confirm",
        headers=headers,
        json={"result": "通过", "confirmer": "客户"}
    )
    response = client.post(
        "/resample",
        headers=headers,
        json={
            "original_card_id": card_id,
            "reason": "测试跟进限制",
            "applicant": "测试员",
            "expected_completion_date": "2025-02-01",
            "customer_feedback": "测试",
            "priority": "低"
        }
    )
    pending_app_id = response.json()["id"]
    
    response = client.put(
        f"/resample/{pending_app_id}/follow-up",
        headers=headers,
        json={
            "operator": "跟单员",
            "remark": "未受理就添加跟进"
        }
    )
    assert response.status_code == 400
    assert "只能在受理后添加" in response.json()["detail"]
    print("[OK] 未受理不能添加跟进记录测试通过")


def test_resample_full_workflow(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/cards",
        headers=headers,
        json={
            "customer_code": "C300",
            "fabric_type": "真丝",
            "color_card_version": "V2",
            "responsible_team": "B组"
        }
    )
    card_id = response.json()["id"]
    client.put(f"/cards/{card_id}/proofing/start", headers=headers)
    client.put(
        f"/cards/{card_id}/proofing/complete",
        headers=headers,
        json={"dye_vat_batch": "B300", "proofing_process": "活性染料染色"}
    )
    client.put(
        f"/cards/{card_id}/inspection",
        headers=headers,
        json={
            "color_comparison_result": "ΔE=0.3",
            "color_difference_value": 0.3,
            "inspector": "质检员A",
            "conclusion": "合格"
        }
    )
    client.put(
        f"/cards/{card_id}/confirm",
        headers=headers,
        json={"result": "通过", "confirmer": "客户A"}
    )
    
    response = client.post(
        "/resample",
        headers=headers,
        json={
            "original_card_id": card_id,
            "reason": "客户反馈颜色偏深需调整",
            "applicant": "业务员小王",
            "expected_completion_date": "2025-03-01",
            "customer_feedback": "客户希望颜色更浅一些，调整染色时间",
            "priority": "紧急"
        }
    )
    app_id = response.json()["id"]
    assert response.json()["resample_status"] == "待打样"
    
    response = client.put(
        f"/resample/{app_id}/accept",
        headers=headers,
        json={
            "operator": "主管李经理",
            "remark": "情况属实，同意复样"
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "处理中"
    
    response = client.put(
        f"/resample/{app_id}/proofing/start",
        headers=headers,
        json={"operator": "打样员小张"}
    )
    assert response.status_code == 200
    assert response.json()["resample_status"] == "打样中"
    
    response = client.put(
        f"/resample/{app_id}/proofing/complete",
        headers=headers,
        json={
            "dye_vat_batch": "B300-R1",
            "proofing_process": "缩短染色时间30%",
            "operator": "打样员小张"
        }
    )
    assert response.status_code == 200
    assert response.json()["resample_status"] == "待质检"
    assert len(response.json()["resample_proofing_records"]) == 1
    
    response = client.put(
        f"/resample/{app_id}/inspection",
        headers=headers,
        json={
            "color_comparison_result": "ΔE=1.2",
            "color_difference_value": 1.2,
            "inspector": "质检员B",
            "conclusion": "不合格"
        }
    )
    assert response.status_code == 200
    assert len(response.json()["resample_inspection_records"]) == 1
    
    response = client.put(
        f"/resample/{app_id}/rework",
        headers=headers,
        json={
            "rework_action": "继续减少染色时间",
            "reason": "颜色仍偏深，需进一步调整",
            "operator": "技术员小陈"
        }
    )
    assert response.status_code == 200
    assert response.json()["resample_status"] == "返调中"
    assert len(response.json()["resample_rework_records"]) == 1
    
    response = client.put(
        f"/resample/{app_id}/proofing/start",
        headers=headers,
        json={"operator": "打样员小张"}
    )
    assert response.status_code == 200
    assert response.json()["resample_status"] == "打样中"
    
    response = client.put(
        f"/resample/{app_id}/proofing/complete",
        headers=headers,
        json={
            "dye_vat_batch": "B300-R2",
            "proofing_process": "减少染色时间50%",
            "operator": "打样员小张"
        }
    )
    assert response.status_code == 200
    
    response = client.put(
        f"/resample/{app_id}/inspection",
        headers=headers,
        json={
            "color_comparison_result": "ΔE=0.4",
            "color_difference_value": 0.4,
            "inspector": "质检员B",
            "conclusion": "合格"
        }
    )
    assert response.status_code == 200
    
    response = client.put(
        f"/resample/{app_id}/follow-up",
        headers=headers,
        json={
            "operator": "跟单员小刘",
            "remark": "样品已寄送客户确认"
        }
    )
    assert response.status_code == 200
    
    response = client.put(
        f"/resample/{app_id}/confirm",
        headers=headers,
        json={
            "result": "通过",
            "confirmer": "客户A"
        }
    )
    assert response.status_code == 200
    assert response.json()["resample_status"] == "已确认"
    assert response.json()["resample_confirmation_record"] is not None

    response = client.put(
        f"/resample/{app_id}/complete",
        headers=headers,
        json={
            "operator": "技术员钱七",
            "remark": "复样完成，颜色已调整到位，符合客户要求"
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "已完成"

    action_types = [r["action_type"] for r in response.json()["action_records"]]
    assert "提交申请" in action_types
    assert "受理" in action_types
    assert "复样打样开始" in action_types
    assert "复样打样完成" in action_types
    assert "复样质检" in action_types
    assert "复样返调" in action_types
    assert "跟进记录" in action_types
    assert "复样确认" in action_types
    
    original_card = client.get(f"/cards/{card_id}", headers=headers).json()
    assert original_card["status"] == "已确认"
    assert len(original_card["proofing_records"]) == 1
    
    print("[OK] 完整复样执行流程测试通过")


def test_resample_list_unauthorized():
    response = client.get("/resample")
    assert response.status_code == 401
    print("[OK] 复样申请列表未授权访问校验测试通过")


def test_resample_detail_unauthorized():
    response = client.get("/resample/test-id")
    assert response.status_code == 401
    print("[OK] 复样申请详情未授权访问校验测试通过")


def test_export_unauthorized():
    response = client.get("/export/json")
    assert response.status_code == 401
    response = client.get("/export/download")
    assert response.status_code == 401
    print("[OK] 导出数据未授权访问校验测试通过")


def test_resample_export_contains_data(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/export/json", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "color_cards" in data
    assert "resample_applications" in data
    assert isinstance(data["resample_applications"], list)
    print("[OK] 导出数据包含复样申请测试通过")


def test_archive_unauthorized():
    response = client.post(
        "/archives",
        json={
            "source_type": "原色卡",
            "source_id": "test-id",
            "delivery_batch_no": "BATCH-001",
            "delivery_target": "客户A",
            "archivist": "归档人"
        }
    )
    assert response.status_code == 401

    response = client.get("/archives")
    assert response.status_code == 401

    response = client.get("/archives/stats")
    assert response.status_code == 401

    response = client.get("/archives/test-id")
    assert response.status_code == 401

    response = client.get("/archives/test-id/export")
    assert response.status_code == 401
    print("[OK] 归档模块未授权访问校验测试通过")


import uuid as _uuid

_archive_card_counter = 0
_archive_resample_counter = 0


def _create_confirmed_card_for_archive(token):
    global _archive_card_counter
    _archive_card_counter += 1
    suffix = f"{_archive_card_counter:03d}-{_uuid.uuid4().hex[:6]}"
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/cards",
        headers=headers,
        json={
            "customer_code": f"C-ARCH-{suffix}",
            "fabric_type": f"面料-{suffix}",
            "color_card_version": "V1",
            "responsible_team": "A组"
        }
    )
    assert response.status_code == 200, f"创建色卡失败: {response.status_code} {response.text}"
    card_id = response.json()["id"]

    client.put(f"/cards/{card_id}/proofing/start", headers=headers)
    client.put(
        f"/cards/{card_id}/proofing/complete",
        headers=headers,
        json={"dye_vat_batch": f"BATCH-ARCH-{suffix}", "proofing_process": "活性染料染色"}
    )
    client.put(
        f"/cards/{card_id}/inspection",
        headers=headers,
        json={
            "color_comparison_result": "ΔE=0.4",
            "color_difference_value": 0.4,
            "inspector": "质检员A",
            "conclusion": "合格"
        }
    )
    response = client.put(
        f"/cards/{card_id}/confirm",
        headers=headers,
        json={"result": "通过", "confirmer": "客户张总"}
    )
    assert response.status_code == 200, f"确认色卡失败: {response.status_code} {response.text}"
    assert response.json()["status"] == "已确认"
    return card_id


def _create_completed_resample_for_archive(token):
    global _archive_resample_counter
    _archive_resample_counter += 1
    suffix = f"{_archive_resample_counter:03d}-{_uuid.uuid4().hex[:6]}"
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/cards",
        headers=headers,
        json={
            "customer_code": f"C-RES-{suffix}",
            "fabric_type": f"面料-RES-{suffix}",
            "color_card_version": "V2",
            "responsible_team": "B组"
        }
    )
    assert response.status_code == 200, f"创建色卡失败: {response.status_code} {response.text}"
    card_id = response.json()["id"]

    client.put(f"/cards/{card_id}/proofing/start", headers=headers)
    client.put(
        f"/cards/{card_id}/proofing/complete",
        headers=headers,
        json={"dye_vat_batch": f"BATCH-RES-{suffix}", "proofing_process": "高温染色"}
    )
    client.put(
        f"/cards/{card_id}/inspection",
        headers=headers,
        json={
            "color_comparison_result": "ΔE=0.3",
            "color_difference_value": 0.3,
            "inspector": "质检员B",
            "conclusion": "合格"
        }
    )
    client.put(
        f"/cards/{card_id}/confirm",
        headers=headers,
        json={"result": "通过", "confirmer": "客户李总"}
    )

    response = client.post(
        "/resample",
        headers=headers,
        json={
            "original_card_id": card_id,
            "reason": "客户反馈颜色偏深需调整",
            "applicant": "业务员小陈",
            "expected_completion_date": "2025-04-01",
            "customer_feedback": "客户希望颜色更浅一些",
            "priority": "高"
        }
    )
    assert response.status_code == 200, f"创建复样失败: {response.status_code} {response.text}"
    app_id = response.json()["id"]

    client.put(
        f"/resample/{app_id}/accept",
        headers=headers,
        json={"operator": "主管王经理", "remark": "同意复样"}
    )
    client.put(
        f"/resample/{app_id}/proofing/start",
        headers=headers,
        json={"operator": "打样员小李"}
    )
    client.put(
        f"/resample/{app_id}/proofing/complete",
        headers=headers,
        json={
            "dye_vat_batch": f"BATCH-RES-{suffix}-R1",
            "proofing_process": "缩短染色时间",
            "operator": "打样员小李"
        }
    )
    client.put(
        f"/resample/{app_id}/inspection",
        headers=headers,
        json={
            "color_comparison_result": "ΔE=0.5",
            "color_difference_value": 0.5,
            "inspector": "质检员B",
            "conclusion": "合格"
        }
    )
    client.put(
        f"/resample/{app_id}/confirm",
        headers=headers,
        json={"result": "通过", "confirmer": "客户李总"}
    )
    response = client.put(
        f"/resample/{app_id}/complete",
        headers=headers,
        json={"operator": "技术员小赵", "remark": "复样完成"}
    )
    assert response.status_code == 200, f"完成复样失败: {response.status_code} {response.text}"
    assert response.json()["status"] == "已完成"
    return app_id


def test_archive_confirmed_card(token):
    headers = {"Authorization": f"Bearer {token}"}
    card_id = _create_confirmed_card_for_archive(token)
    card_detail = client.get(f"/cards/{card_id}", headers=headers).json()

    response = client.post(
        "/archives",
        headers=headers,
        json={
            "source_type": "原色卡",
            "source_id": card_id,
            "delivery_batch_no": "DELIVER-2025-0001",
            "delivery_target": "上海XX服装有限公司",
            "delivery_remark": "春季订单首批交付，共500米色卡",
            "archivist": "业务主管王经理"
        }
    )
    assert response.status_code == 200
    archive_id = response.json()["id"]
    assert response.json()["source_type"] == "原色卡"
    assert response.json()["source_id"] == card_id
    assert response.json()["source_status"] == "已确认"
    assert response.json()["delivery_batch_no"] == "DELIVER-2025-0001"
    assert response.json()["delivery_target"] == "上海XX服装有限公司"
    assert response.json()["archivist"] == "业务主管王经理"
    assert response.json()["customer_code"] == card_detail["customer_code"]
    assert response.json()["fabric_type"] == card_detail["fabric_type"]
    assert response.json()["color_card_snapshot"] is not None
    assert response.json()["color_card_snapshot"]["id"] == card_id
    assert response.json()["color_card_snapshot"]["status"] == "已确认"
    assert len(response.json()["color_card_snapshot"]["proofing_records"]) == 1
    assert len(response.json()["color_card_snapshot"]["inspection_records"]) == 1
    assert response.json()["color_card_snapshot"]["confirmation_record"] is not None
    print("[OK] 已确认原色卡归档测试通过")
    return archive_id


def test_archive_unconfirmed_card(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/cards",
        headers=headers,
        json={
            "customer_code": "C-ARCHIVE-003",
            "fabric_type": "纯棉",
            "color_card_version": "V1",
            "responsible_team": "C组"
        }
    )
    unconfirmed_card_id = response.json()["id"]

    response = client.post(
        "/archives",
        headers=headers,
        json={
            "source_type": "原色卡",
            "source_id": unconfirmed_card_id,
            "delivery_batch_no": "DELIVER-TEST",
            "delivery_target": "测试客户",
            "archivist": "测试归档人"
        }
    )
    assert response.status_code == 400
    assert "已确认" in response.json()["detail"]
    print("[OK] 未确认色卡不能归档测试通过")


def test_archive_completed_resample(token):
    headers = {"Authorization": f"Bearer {token}"}
    app_id = _create_completed_resample_for_archive(token)
    app_detail = client.get(f"/resample/{app_id}", headers=headers).json()

    response = client.post(
        "/archives",
        headers=headers,
        json={
            "source_type": "复样申请",
            "source_id": app_id,
            "delivery_batch_no": "DELIVER-2025-0002",
            "delivery_target": "杭州XX纺织品公司",
            "delivery_remark": "复样调整后交付，客户已确认颜色",
            "archivist": "业务主管李经理"
        }
    )
    assert response.status_code == 200
    archive_id = response.json()["id"]
    assert response.json()["source_type"] == "复样申请"
    assert response.json()["source_id"] == app_id
    assert response.json()["source_status"] == "已完成"
    assert response.json()["delivery_batch_no"] == "DELIVER-2025-0002"
    assert response.json()["delivery_target"] == "杭州XX纺织品公司"
    assert response.json()["archivist"] == "业务主管李经理"
    assert response.json()["customer_code"] == app_detail["customer_code"]
    assert response.json()["fabric_type"] == app_detail["fabric_type"]
    assert response.json()["resample_snapshot"] is not None
    assert response.json()["resample_snapshot"]["id"] == app_id
    assert response.json()["resample_snapshot"]["status"] == "已完成"
    assert response.json()["resample_snapshot"]["resample_status"] == "已确认"
    assert len(response.json()["resample_snapshot"]["resample_proofing_records"]) == 1
    assert len(response.json()["resample_snapshot"]["resample_inspection_records"]) == 1
    assert response.json()["resample_snapshot"]["resample_confirmation_record"] is not None
    assert len(response.json()["resample_snapshot"]["action_records"]) > 0
    print("[OK] 已完成复样申请归档测试通过")
    return archive_id


def test_archive_uncompleted_resample(token):
    headers = {"Authorization": f"Bearer {token}"}
    card_id = _create_confirmed_card_for_archive(token)

    response = client.post(
        "/resample",
        headers=headers,
        json={
            "original_card_id": card_id,
            "reason": "测试未完成复样归档",
            "applicant": "测试员",
            "expected_completion_date": "2025-05-01",
            "customer_feedback": "测试反馈",
            "priority": "中"
        }
    )
    pending_app_id = response.json()["id"]

    response = client.post(
        "/archives",
        headers=headers,
        json={
            "source_type": "复样申请",
            "source_id": pending_app_id,
            "delivery_batch_no": "DELIVER-TEST-2",
            "delivery_target": "测试客户2",
            "archivist": "测试归档人2"
        }
    )
    assert response.status_code == 400
    assert "已完成" in response.json()["detail"]
    print("[OK] 未完成复样不能归档测试通过")


def test_archive_duplicate(token):
    headers = {"Authorization": f"Bearer {token}"}
    card_id = _create_confirmed_card_for_archive(token)

    response = client.post(
        "/archives",
        headers=headers,
        json={
            "source_type": "原色卡",
            "source_id": card_id,
            "delivery_batch_no": "DELIVER-DUP-001",
            "delivery_target": "重复测试客户",
            "archivist": "归档人A"
        }
    )
    assert response.status_code == 200

    response = client.post(
        "/archives",
        headers=headers,
        json={
            "source_type": "原色卡",
            "source_id": card_id,
            "delivery_batch_no": "DELIVER-DUP-002",
            "delivery_target": "重复测试客户",
            "archivist": "归档人B"
        }
    )
    assert response.status_code == 400
    assert "已归档" in response.json()["detail"]
    assert "不允许重复归档" in response.json()["detail"]
    print("[OK] 重复归档校验测试通过")


def test_get_archive_detail(token):
    headers = {"Authorization": f"Bearer {token}"}
    card_id = _create_confirmed_card_for_archive(token)
    card_detail = client.get(f"/cards/{card_id}", headers=headers).json()

    response = client.post(
        "/archives",
        headers=headers,
        json={
            "source_type": "原色卡",
            "source_id": card_id,
            "delivery_batch_no": "DELIVER-DETAIL-001",
            "delivery_target": "详情测试客户",
            "delivery_remark": "测试详情页数据",
            "archivist": "测试归档员"
        }
    )
    archive_id = response.json()["id"]

    response = client.get(f"/archives/{archive_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == archive_id
    assert data["source_type"] == "原色卡"
    assert data["delivery_batch_no"] == "DELIVER-DETAIL-001"
    assert "color_card_snapshot" in data
    assert "archived_at" in data
    assert "created_at" in data

    snapshot = data["color_card_snapshot"]
    assert snapshot["customer_code"] == card_detail["customer_code"]
    assert snapshot["fabric_type"] == card_detail["fabric_type"]
    assert snapshot["status"] == "已确认"
    assert len(snapshot["proofing_records"]) >= 0
    assert len(snapshot["inspection_records"]) >= 0
    assert len(snapshot["rework_records"]) >= 0
    assert snapshot["confirmation_record"] is not None
    print("[OK] 归档详情页测试通过")


def test_list_archives(token):
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/archives", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert data["total"] >= 0
    print("[OK] 归档列表接口测试通过")


def test_filter_archives(token):
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        "/archives?source_type=原色卡",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["source_type"] == "原色卡"

    response = client.get(
        "/archives?responsible_team=A组",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["responsible_team"] == "A组"

    response = client.get(
        "/archives?responsible_team=B组",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["responsible_team"] == "B组"

    response = client.get(
        f"/archives?delivery_batch_no=DELIVER-2025-0001",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["delivery_batch_no"] == "DELIVER-2025-0001"
    print("[OK] 归档筛选功能测试通过")


def test_archive_stats(token):
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/archives/stats", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "filter_params" in data
    assert "summary" in data
    assert "customer_stats" in data
    assert "fabric_stats" in data
    assert "team_stats" in data
    assert "batch_stats" in data
    assert "source_type_stats" in data
    assert "archivist_stats" in data

    summary = data["summary"]
    assert "total_count" in summary
    assert "original_card_count" in summary
    assert "resample_count" in summary
    assert "customer_count" in summary
    assert "fabric_count" in summary
    assert "team_count" in summary
    assert "batch_count" in summary

    assert isinstance(data["customer_stats"], list)
    assert isinstance(data["fabric_stats"], list)
    assert isinstance(data["team_stats"], list)
    assert isinstance(data["batch_stats"], list)
    assert isinstance(data["source_type_stats"], list)
    assert isinstance(data["archivist_stats"], list)
    print("[OK] 归档统计接口测试通过")


def test_archive_stats_with_filter(token):
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        "/archives/stats?source_type=原色卡&responsible_team=A组",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filter_params"]["source_type"] == "原色卡"
    assert data["filter_params"]["responsible_team"] == "A组"
    print("[OK] 归档统计筛选功能测试通过")


def test_archive_date_validation(token):
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        "/archives?start_date=2025-01-01&end_date=2024-01-01",
        headers=headers
    )
    assert response.status_code == 400
    assert "开始日期不能大于结束日期" in response.json()["detail"]

    response = client.get(
        "/archives/stats?start_date=2025-01-01&end_date=2024-01-01",
        headers=headers
    )
    assert response.status_code == 400
    assert "开始日期不能大于结束日期" in response.json()["detail"]
    print("[OK] 归档日期范围验证测试通过")


def test_single_archive_export(token):
    headers = {"Authorization": f"Bearer {token}"}
    card_id = _create_confirmed_card_for_archive(token)

    response = client.post(
        "/archives",
        headers=headers,
        json={
            "source_type": "原色卡",
            "source_id": card_id,
            "delivery_batch_no": "DELIVER-EXPORT-001",
            "delivery_target": "导出测试客户",
            "delivery_remark": "测试单条导出功能",
            "archivist": "导出测试员"
        }
    )
    archive_id = response.json()["id"]

    response = client.get(f"/archives/{archive_id}/export", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert data["id"] == archive_id
    assert data["delivery_batch_no"] == "DELIVER-EXPORT-001"
    assert "color_card_snapshot" in data
    print("[OK] 单条归档数据导出测试通过")


def test_archive_not_found(token):
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/archives/non-existent-id", headers=headers)
    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]

    response = client.get("/archives/non-existent-id/export", headers=headers)
    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]
    print("[OK] 归档记录不存在校验测试通过")


def test_archive_pagination(token):
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        "/archives?skip=0&limit=5",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 5
    assert data["skip"] == 0
    assert data["limit"] == 5
    print("[OK] 归档列表分页功能测试通过")


def test_archive_snapshot_contains_risk_info(token):
    headers = {"Authorization": f"Bearer {token}"}
    card_id = _create_confirmed_card_for_archive(token)

    response = client.post(
        "/archives",
        headers=headers,
        json={
            "source_type": "原色卡",
            "source_id": card_id,
            "delivery_batch_no": "DELIVER-RISK-001",
            "delivery_target": "风险快照测试客户",
            "archivist": "测试员"
        }
    )
    archive_id = response.json()["id"]

    response = client.get(f"/archives/{archive_id}", headers=headers)
    data = response.json()
    assert "color_card_snapshot" in data
    snapshot = data["color_card_snapshot"]
    assert "risk_alerts" in snapshot
    assert isinstance(snapshot["risk_alerts"], list)
    print("[OK] 归档快照包含风险处理信息测试通过")


def test_full_export_contains_archives(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/archives/export/all", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "delivery_archives" in data
    assert isinstance(data["delivery_archives"], list)
    print("[OK] 全量归档导出测试通过")


def test_resample_dashboard_overview(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/dashboard/resample/overview", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "status_summary" in data
    assert "customer_stats" in data
    assert "team_stats" in data
    assert "priority_stats" in data
    assert "total_count" in data["status_summary"]
    assert "pending_count" in data["status_summary"]
    assert "processing_count" in data["status_summary"]
    assert "completed_count" in data["status_summary"]
    assert "rejected_count" in data["status_summary"]
    print("[OK] 复样看板总览测试通过")


def test_resample_dashboard_filter(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(
        "/dashboard/resample/overview?customer_code=C100&priority=高",
        headers=headers
    )
    assert response.status_code == 200
    print("[OK] 复样看板筛选测试通过")


def test_resample_unauthorized():
    response = client.post(
        "/resample",
        json={
            "original_card_id": "test-id",
            "reason": "测试",
            "applicant": "测试",
            "expected_completion_date": "2025-01-01",
            "customer_feedback": "测试",
            "priority": "中"
        }
    )
    assert response.status_code == 401
    print("[OK] 复样申请未授权访问校验测试通过")

def run_all_tests():
    print("=" * 60)
    print("开始API接口测试")
    print("=" * 60)
    
    try:
        test_root()
        token = test_login()
        test_unauthorized()
        card_id = test_create_card(token)
        test_duplicate_card(token)
        test_get_card(card_id)
        test_list_cards()
        test_filter_cards()
        test_proofing(token, card_id)
        test_inspection(token, card_id)
        test_confirm_without_inspection(token)
        test_confirm(token, card_id)
        test_stats_high_rework()
        test_stats_pending()
        test_stats_cycle()
        test_risks_detect()
        test_export_json(token)
        test_dashboard_unauthorized()
        test_dashboard_overview(token)
        test_dashboard_detail(token)
        test_dashboard_filter(token)
        test_dashboard_date_validation(token)
        test_dashboard_pagination(token)
        test_dashboard_fabric_dimension(token)
        test_dashboard_inspection_record_detail(token, card_id)
        test_dashboard_date_field_filter(token)
        test_dashboard_confirmed_risk_resolved(token)
        
        print("-" * 60)
        print("开始复样申请模块测试")
        print("-" * 60)
        
        test_resample_unauthorized()
        test_resample_list_unauthorized()
        test_resample_detail_unauthorized()
        test_export_unauthorized()
        test_create_resample_without_confirmed_card(token)
        app_id = test_create_resample_application(token, card_id)
        test_get_resample_application(token, app_id)
        test_list_resample_applications(token)
        test_filter_resample_applications(token)
        test_follow_up_before_accept_rejected(token)
        test_accept_resample_application(token, app_id)
        test_reject_resample_application(token)
        test_complete_resample_application(token, app_id)
        test_resample_full_workflow(token)
        test_resample_dashboard_overview(token)
        test_resample_dashboard_filter(token)
        test_resample_export_contains_data(token)
        
        print("-" * 60)
        print("开始色卡交付归档模块测试")
        print("-" * 60)

        import uuid as _uid
        _fixture_suffix = _uid.uuid4().hex[:8]
        _headers = {"Authorization": f"Bearer {token}"}
        _resp = client.post("/cards", headers=_headers, json={
            "customer_code": f"RUNALL-CUST-{_fixture_suffix}",
            "fabric_type": f"RUNALL-FAB-{_fixture_suffix}",
            "color_card_version": "V1",
            "responsible_team": "A组"
        })
        _sample_card_id = _resp.json()["id"]
        client.put(f"/cards/{_sample_card_id}/proofing/start", headers=_headers)
        client.put(f"/cards/{_sample_card_id}/proofing/complete", headers=_headers,
                   json={"dye_vat_batch": f"BATCH-RUN-{_fixture_suffix}", "proofing_process": "测试染色"})
        client.put(f"/cards/{_sample_card_id}/inspection", headers=_headers,
                   json={"color_comparison_result": "ΔE=0.4", "color_difference_value": 0.4,
                         "inspector": "质检员A", "conclusion": "合格"})
        client.put(f"/cards/{_sample_card_id}/confirm", headers=_headers,
                   json={"result": "通过", "confirmer": "客户测试员"})

        _resp = client.post("/resample", headers=_headers, json={
            "original_card_id": _sample_card_id,
            "reason": f"RUNALL 复样测试-{_fixture_suffix}",
            "applicant": "测试业务员",
            "expected_completion_date": "2025-06-30",
            "customer_feedback": "客户反馈",
            "priority": "中"
        })
        _sample_resample_id = _resp.json()["id"]
        client.put(f"/resample/{_sample_resample_id}/accept", headers=_headers,
                   json={"operator": "测试主管", "remark": "同意"})
        client.put(f"/resample/{_sample_resample_id}/proofing/start", headers=_headers,
                   json={"operator": "测试打样员"})
        client.put(f"/resample/{_sample_resample_id}/proofing/complete", headers=_headers,
                   json={"dye_vat_batch": f"BATCH-RUN-R-{_fixture_suffix}",
                         "proofing_process": "复样染色", "operator": "测试打样员"})
        client.put(f"/resample/{_sample_resample_id}/inspection", headers=_headers,
                   json={"color_comparison_result": "ΔE=0.4", "color_difference_value": 0.4,
                         "inspector": "测试质检员", "conclusion": "合格"})
        client.put(f"/resample/{_sample_resample_id}/confirm", headers=_headers,
                   json={"result": "通过", "confirmer": "测试客户"})
        client.put(f"/resample/{_sample_resample_id}/complete", headers=_headers,
                   json={"operator": "测试技术员", "remark": "完成"})
        
        test_archive_unauthorized()
        test_archive_empty_delivery_batch_no(token, _sample_card_id)
        test_archive_whitespace_delivery_batch_no(token, _sample_card_id)
        test_archive_empty_delivery_target(token, _sample_card_id)
        test_archive_empty_archivist(token, _sample_card_id)
        test_archive_unconfirmed_card(token)
        test_archive_uncompleted_resample(token)
        archive_id_1 = test_archive_confirmed_card(token)
        archive_id_2 = test_archive_completed_resample(token)
        test_resample_archive_contains_original_card_snapshot(token, _sample_resample_id)
        test_archive_duplicate(token)
        test_get_archive_detail(token)
        test_list_archives(token)
        test_filter_archives(token)
        test_archive_stats(token)
        test_archive_stats_with_filter(token)
        test_archive_date_validation(token)
        test_single_archive_export(token)
        test_archive_not_found(token)
        test_archive_pagination(token)
        test_archive_snapshot_contains_risk_info(token)
        test_full_export_contains_archives(token)
        
        print("=" * 60)
        print("[PASS] 所有API测试通过！")
        print("=" * 60)
        return True
    except AssertionError as e:
        print(f"\n[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n[FAIL] 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
