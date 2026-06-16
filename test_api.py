import sys
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

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

def test_export_json():
    response = client.get("/export/json")
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


def test_get_resample_application(app_id):
    response = client.get(f"/resample/{app_id}")
    assert response.status_code == 200
    assert response.json()["id"] == app_id
    assert "action_records" in response.json()
    assert "original_confirmation_record" in response.json()
    print("[OK] 获取复样申请详情测试通过")


def test_list_resample_applications():
    response = client.get("/resample")
    assert response.status_code == 200
    assert "items" in response.json()
    assert "total" in response.json()
    print("[OK] 复样申请列表测试通过")


def test_filter_resample_applications():
    response = client.get("/resample?status=待受理&priority=高")
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
    assert response.status_code == 200
    assert response.json()["status"] == "已完成"
    print("[OK] 完成复样申请测试通过")


def test_resample_follow_up(token, app_id):
    headers = {"Authorization": f"Bearer {token}"}
    response = client.put(
        f"/resample/{app_id}/follow-up",
        headers=headers,
        json={
            "operator": "跟单员",
            "remark": "客户已确认复样结果"
        }
    )
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json()}")
    assert response.status_code == 200
    print("[OK] 复样跟进记录测试通过")


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


def test_resample_export_contains_data():
    response = client.get("/export/json")
    assert response.status_code == 200
    data = response.json()
    assert "color_cards" in data
    assert "resample_applications" in data
    assert isinstance(data["resample_applications"], list)
    print("[OK] 导出数据包含复样申请测试通过")


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
        test_export_json()
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
        test_create_resample_without_confirmed_card(token)
        app_id = test_create_resample_application(token, card_id)
        test_get_resample_application(app_id)
        test_list_resample_applications()
        test_filter_resample_applications()
        test_accept_resample_application(token, app_id)
        test_reject_resample_application(token)
        test_complete_resample_application(token, app_id)
        test_resample_dashboard_overview(token)
        test_resample_dashboard_filter(token)
        test_resample_export_contains_data()
        
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
