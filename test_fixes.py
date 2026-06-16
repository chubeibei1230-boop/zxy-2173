import sys
import pytest
from fastapi.testclient import TestClient
from main import app
from storage import storage
from models import CardStatus

client = TestClient(app)


@pytest.fixture(scope="session")
def fixes_token():
    response = client.post(
        "/token",
        data={"username": "admin", "password": "admin123"}
    )
    return response.json()["access_token"]


def get_token():
    response = client.post(
        "/token",
        data={"username": "admin", "password": "admin123"}
    )
    return response.json()["access_token"]

def test_1_confirmed_card_no_duplicate():
    print("\n=== 测试1: 已确认色卡不能重复创建 ===")
    token = get_token()
    
    response = client.post(
        "/cards",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customer_code": "TEST_CONFIRM",
            "fabric_type": "测试布",
            "color_card_version": "V1",
            "responsible_team": "测试组"
        }
    )
    card_id = response.json()["id"]
    print(f"  创建色卡: {card_id}")
    
    client.put(
        f"/cards/{card_id}/proofing/start",
        headers={"Authorization": f"Bearer {token}"}
    )
    print("  开始打样")
    
    client.put(
        f"/cards/{card_id}/proofing/complete",
        headers={"Authorization": f"Bearer {token}"},
        json={"dye_vat_batch": "BATCH_TEST", "proofing_process": "测试染色"}
    )
    print("  完成打样")
    
    client.put(
        f"/cards/{card_id}/inspection",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "color_comparison_result": "ΔE=0.5",
            "color_difference_value": 0.5,
            "inspector": "测试员",
            "conclusion": "合格"
        }
    )
    print("  提交质检")
    
    client.put(
        f"/cards/{card_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={"result": "通过", "confirmer": "测试客户"}
    )
    print("  确认色卡")
    
    response = client.post(
        "/cards",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customer_code": "TEST_CONFIRM",
            "fabric_type": "测试布",
            "color_card_version": "V1",
            "responsible_team": "测试组"
        }
    )
    print(f"  重复创建状态码: {response.status_code}")
    print(f"  错误信息: {response.json().get('detail', '')}")
    
    assert response.status_code == 400, "已确认色卡应该不允许重复创建"
    assert "已存在有效色卡" in response.json()["detail"]
    print("[PASS] 已确认色卡重复创建校验生效")

def test_2_rework_old_inspection_not_reused():
    print("\n=== 测试2: 返调后旧质检结论不能直接确认 ===")
    token = get_token()
    
    response = client.post(
        "/cards",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customer_code": "TEST_REWORK",
            "fabric_type": "返调测试布",
            "color_card_version": "V1",
            "responsible_team": "测试组"
        }
    )
    card_id = response.json()["id"]
    print(f"  创建色卡: {card_id}")
    
    client.put(
        f"/cards/{card_id}/proofing/start",
        headers={"Authorization": f"Bearer {token}"}
    )
    client.put(
        f"/cards/{card_id}/proofing/complete",
        headers={"Authorization": f"Bearer {token}"},
        json={"dye_vat_batch": "BATCH_R1", "proofing_process": "第一次染色"}
    )
    print("  第一次打样完成")
    
    client.put(
        f"/cards/{card_id}/inspection",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "color_comparison_result": "ΔE=2.0",
            "color_difference_value": 2.0,
            "inspector": "测试员",
            "conclusion": "不合格"
        }
    )
    print("  第一次质检（不合格）")
    
    client.put(
        f"/cards/{card_id}/rework",
        headers={"Authorization": f"Bearer {token}"},
        json={"rework_action": "调整配方", "reason": "色差大", "operator": "测试员"}
    )
    print("  返调")
    
    client.put(
        f"/cards/{card_id}/proofing/start",
        headers={"Authorization": f"Bearer {token}"}
    )
    client.put(
        f"/cards/{card_id}/proofing/complete",
        headers={"Authorization": f"Bearer {token}"},
        json={"dye_vat_batch": "BATCH_R2", "proofing_process": "第二次染色"}
    )
    print("  第二次打样完成（返调后）")
    
    card_detail = client.get(f"/cards/{card_id}").json()
    print(f"  当前状态: {card_detail['status']}")
    print(f"  质检记录数: {len(card_detail['inspection_records'])}")
    print(f"  打样记录数: {len(card_detail['proofing_records'])}")
    
    response = client.put(
        f"/cards/{card_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={"result": "通过", "confirmer": "测试客户"}
    )
    print(f"  直接确认状态码: {response.status_code}")
    print(f"  错误信息: {response.json().get('detail', '')}")
    
    assert response.status_code == 400, "返调重打样后没有新质检应该不能确认"
    assert "本次打样后的质检结论" in response.json()["detail"]
    print("[PASS] 返调后旧质检结论不能直接确认")

def test_3_proofing_status_exists():
    print("\n=== 测试3: 打样中状态真实存在 ===")
    token = get_token()
    
    response = client.post(
        "/cards",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customer_code": "TEST_STATUS",
            "fabric_type": "状态测试布",
            "color_card_version": "V1",
            "responsible_team": "测试组"
        }
    )
    card_id = response.json()["id"]
    print(f"  创建色卡，初始状态: {response.json()['status']}")
    
    assert response.json()["status"] == CardStatus.PENDING_PROOFING.value
    
    response = client.put(
        f"/cards/{card_id}/proofing/start",
        headers={"Authorization": f"Bearer {token}"}
    )
    status_after_start = response.json()["status"]
    print(f"  开始打样后状态: {status_after_start}")
    
    assert status_after_start == CardStatus.PROOFING.value, "开始打样后应该是'打样中'状态"
    print("[PASS] 打样中状态真实存在并正确流转")

def test_4_inspection_overdue_detection():
    print("\n=== 测试4: 质检超期风险识别完整 ===")
    from datetime import timedelta
    
    token = get_token()
    
    response = client.post(
        "/cards",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customer_code": "TEST_OVERDUE",
            "fabric_type": "超期测试布",
            "color_card_version": "V1",
            "responsible_team": "测试组"
        }
    )
    card_id = response.json()["id"]
    
    client.put(
        f"/cards/{card_id}/proofing/start",
        headers={"Authorization": f"Bearer {token}"}
    )
    client.put(
        f"/cards/{card_id}/proofing/complete",
        headers={"Authorization": f"Bearer {token}"},
        json={"dye_vat_batch": "BATCH_O1", "proofing_process": "测试染色"}
    )
    print("  创建待质检色卡")
    
    card = storage.get_card(card_id)
    card.submitted_for_inspection_at = card.submitted_for_inspection_at - timedelta(hours=48)
    print("  模拟提交时间为48小时前（超期24小时）")
    
    response = client.get("/risks/inspection-overdue")
    overdue_risks = response.json()["risks"]
    print(f"  质检超期风险数: {len(overdue_risks)}")
    
    assert len(overdue_risks) >= 1, "应该检测到质检超期风险"
    
    response = client.get("/risks/detect-all")
    all_risks = response.json()
    print(f"  综合风险检测包含质检超期: {'inspection_overdue_risks' in all_risks}")
    print(f"  质检超期风险数量: {len(all_risks.get('inspection_overdue_risks', []))}")
    
    assert "inspection_overdue_risks" in all_risks
    assert len(all_risks["inspection_overdue_risks"]) >= 1
    print("[PASS] 质检超期风险识别完整")

def run_all_tests():
    print("=" * 60)
    print("四项问题修复验证测试")
    print("=" * 60)
    
    try:
        test_1_confirmed_card_no_duplicate()
        test_2_rework_old_inspection_not_reused()
        test_3_proofing_status_exists()
        test_4_inspection_overdue_detection()
        
        print("\n" + "=" * 60)
        print("[PASS] 所有四项问题修复验证通过！")
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
