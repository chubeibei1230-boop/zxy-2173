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
        f"/cards/{card_id}/proofing",
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
        f"/cards/{card_id2}/proofing",
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
