from storage import storage
from models import ColorCardCreate, CardStatus

print('=== 测试风险预警和返调 ===')

card = ColorCardCreate(
    customer_code='C004',
    fabric_type='尼龙',
    color_card_version='V1',
    responsible_team='B组'
)
new_card = storage.create_card(card)
print('创建色卡:', new_card.id)

storage.add_proofing(new_card.id, 'BATCH002', '常温染色')
print('打样完成')

for i in range(4):
    storage.add_inspection(
        new_card.id, f'ΔE={1.5+i}', 1.5+i, '质检员B', '不合格'
    )
    storage.add_rework(
        new_card.id, f'调整配方{i+1}', '色差偏大', '操作员A'
    )
    storage.add_proofing(new_card.id, f'BATCH002', f'调整后染色{i+1}')
    print(f'第{i+1}次返调完成')

card_final = storage.get_card(new_card.id)
print('返调次数:', len(card_final.rework_records))
print('风险预警数:', len(card_final.risk_alerts))
for alert in card_final.risk_alerts:
    print(f'  - {alert.type}: {alert.message}')

print('\n=== 测试异常检测 ===')
cluster_risks = storage.detect_color_difference_cluster()
print('染缸批次色差集中风险数:', len(cluster_risks))

team_risks = storage.detect_team_high_rework_rate()
print('小组返调率偏高风险数:', len(team_risks))
for risk in team_risks:
    team_name = risk["team"]
    rate = risk["rework_rate"]
    print(f'  - {team_name}: 返调率 {rate:.1%}')

print('\n=== 测试统计接口 ===')
high_rework = storage.get_high_rework_batches()
print('返调高发批次:', len(high_rework))
for batch in high_rework[:3]:
    print(f'  - {batch.dye_vat_batch}: {batch.rework_count}次返调')

cycle_stats = storage.get_confirmation_cycle_stats()
print('客户确认周期统计:', len(cycle_stats))
for stat in cycle_stats:
    days = stat.avg_cycle_days
    count = stat.total_confirmed
    code = stat.customer_code
    print(f'  - {code}: 平均{days}天, 共{count}个')

print('\n=== 测试JSON导出 ===')
json_data = storage.get_all_cards_json()
print('导出记录数:', len(json_data))

print('\n=== 测试确认前质检校验 ===')
card2 = ColorCardCreate(
    customer_code='C005',
    fabric_type='羊毛',
    color_card_version='V1',
    responsible_team='A组'
)
new_card2 = storage.create_card(card2)
storage.add_proofing(new_card2.id, 'BATCH003', '中温染色')

try:
    storage.confirm_card(new_card2.id, '通过', '客户B')
    print('错误：未质检却确认成功')
except ValueError as e:
    print('确认前质检校验成功:', str(e))

print('\n=== 测试返调前质检校验 ===')
try:
    storage.add_rework(new_card2.id, '调整配方', '色差', '操作员B')
    print('错误：未质检却返调成功')
except ValueError as e:
    print('返调前质检校验成功:', str(e))

print('\n=== 所有测试通过 ===')
