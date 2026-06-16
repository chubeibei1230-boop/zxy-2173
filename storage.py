import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from models import (
    ColorCard, ColorCardCreate, CardStatus, RiskAlert, RiskType,
    ProofingRecord, InspectionRecord, ReworkRecord, ConfirmationRecord,
    FilterParams, HighReworkBatchStats, PendingInspectionStats, ConfirmationCycleStats,
    DashboardFilterParams, StatusSummary, DimensionStats, CardDetailItem,
    DashboardOverviewResponse, DashboardDetailResponse
)
from config import (
    REWORK_THRESHOLD, INSPECTION_OVERDUE_HOURS,
    COLOR_DIFFERENCE_CLUSTER_THRESHOLD, TEAM_HIGH_REWORK_RATE_THRESHOLD
)


class MemoryStorage:
    def __init__(self):
        self.cards: Dict[str, ColorCard] = {}
        self._init_sample_data()

    def _init_sample_data(self):
        sample_cards = [
            {
                "customer_code": "C001",
                "fabric_type": "棉布",
                "color_card_version": "V1",
                "responsible_team": "A组"
            },
            {
                "customer_code": "C002",
                "fabric_type": "涤纶",
                "color_card_version": "V2",
                "responsible_team": "B组"
            }
        ]
        for card_data in sample_cards:
            card = ColorCard(
                id=str(uuid.uuid4()),
                **card_data
            )
            self.cards[card.id] = card

    def create_card(self, card_create: ColorCardCreate) -> ColorCard:
        for card in self.cards.values():
            if (card.customer_code == card_create.customer_code and
                card.fabric_type == card_create.fabric_type and
                card.color_card_version == card_create.color_card_version and
                card.status != CardStatus.DISCARDED):
                raise ValueError(f"客户 {card_create.customer_code} 的 {card_create.fabric_type} 在版本 {card_create.color_card_version} 下已存在有效色卡")

        card_id = str(uuid.uuid4())
        card = ColorCard(
            id=card_id,
            **card_create.model_dump()
        )
        self.cards[card_id] = card
        return card

    def get_card(self, card_id: str) -> Optional[ColorCard]:
        return self.cards.get(card_id)

    def list_cards(self, filters: FilterParams) -> Tuple[List[ColorCard], int]:
        result = list(self.cards.values())

        if filters.customer_code:
            result = [c for c in result if c.customer_code == filters.customer_code]
        if filters.fabric_type:
            result = [c for c in result if c.fabric_type == filters.fabric_type]
        if filters.dye_vat_batch:
            result = [c for c in result if any(
                pr.dye_vat_batch == filters.dye_vat_batch for pr in c.proofing_records
            )]
        if filters.color_card_version:
            result = [c for c in result if c.color_card_version == filters.color_card_version]
        if filters.status:
            result = [c for c in result if c.status == filters.status]
        if filters.start_date:
            start_dt = datetime.combine(filters.start_date, datetime.min.time())
            result = [c for c in result if c.created_at >= start_dt]
        if filters.end_date:
            end_dt = datetime.combine(filters.end_date, datetime.max.time())
            result = [c for c in result if c.created_at <= end_dt]
        if filters.inspection_conclusion:
            result = [c for c in result if any(
                ir.conclusion == filters.inspection_conclusion for ir in c.inspection_records
            )]

        total = len(result)
        result = result[filters.skip:filters.skip + filters.limit]
        return result, total

    def update_card_status(self, card_id: str, new_status: CardStatus) -> ColorCard:
        card = self.get_card(card_id)
        if not card:
            raise ValueError(f"色卡 {card_id} 不存在")
        card.status = new_status
        card.updated_at = datetime.now()
        return card

    def start_proofing(self, card_id: str) -> ColorCard:
        card = self.get_card(card_id)
        if not card:
            raise ValueError(f"色卡 {card_id} 不存在")
        if card.status not in [CardStatus.PENDING_PROOFING, CardStatus.REWORKING]:
            raise ValueError(f"当前状态 {card.status} 不允许开始打样")

        card.status = CardStatus.PROOFING
        card.updated_at = datetime.now()
        return card

    def complete_proofing(self, card_id: str, dye_vat_batch: str, proofing_process: str) -> ColorCard:
        card = self.get_card(card_id)
        if not card:
            raise ValueError(f"色卡 {card_id} 不存在")
        if card.status != CardStatus.PROOFING:
            raise ValueError(f"当前状态 {card.status} 不允许完成打样")

        record = ProofingRecord(
            id=str(uuid.uuid4()),
            dye_vat_batch=dye_vat_batch,
            proofing_process=proofing_process
        )
        card.proofing_records.append(record)
        card.status = CardStatus.PENDING_INSPECTION
        card.submitted_for_inspection_at = datetime.now()
        card.updated_at = datetime.now()
        self._check_risks(card)
        return card

    def add_inspection(self, card_id: str, color_comparison_result: str,
                       color_difference_value: Optional[float], inspector: str, conclusion: str) -> ColorCard:
        card = self.get_card(card_id)
        if not card:
            raise ValueError(f"色卡 {card_id} 不存在")
        if card.status != CardStatus.PENDING_INSPECTION:
            raise ValueError(f"当前状态 {card.status} 不允许提交质检")

        record = InspectionRecord(
            id=str(uuid.uuid4()),
            color_comparison_result=color_comparison_result,
            color_difference_value=color_difference_value,
            inspector=inspector,
            conclusion=conclusion
        )
        card.inspection_records.append(record)
        card.updated_at = datetime.now()
        self._check_risks(card)
        return card

    def _has_valid_inspection_after_last_proofing(self, card: ColorCard) -> bool:
        if not card.inspection_records or not card.proofing_records:
            return False
        last_proofing_time = card.proofing_records[-1].created_at
        last_inspection_time = card.inspection_records[-1].created_at
        return last_inspection_time > last_proofing_time

    def add_rework(self, card_id: str, rework_action: str, reason: str, operator: str) -> ColorCard:
        card = self.get_card(card_id)
        if not card:
            raise ValueError(f"色卡 {card_id} 不存在")
        if card.status != CardStatus.PENDING_INSPECTION:
            raise ValueError(f"当前状态 {card.status} 不允许返调")
        if not self._has_valid_inspection_after_last_proofing(card):
            raise ValueError("返调前必须存在本次打样后的质检结论")

        record = ReworkRecord(
            id=str(uuid.uuid4()),
            rework_action=rework_action,
            reason=reason,
            operator=operator
        )
        card.rework_records.append(record)
        card.status = CardStatus.REWORKING
        card.updated_at = datetime.now()
        self._check_risks(card)
        return card

    def confirm_card(self, card_id: str, result: str, confirmer: str) -> ColorCard:
        card = self.get_card(card_id)
        if not card:
            raise ValueError(f"色卡 {card_id} 不存在")
        if card.status != CardStatus.PENDING_INSPECTION:
            raise ValueError(f"当前状态 {card.status} 不允许确认")
        if not self._has_valid_inspection_after_last_proofing(card):
            raise ValueError("确认前必须存在本次打样后的质检结论")

        record = ConfirmationRecord(
            id=str(uuid.uuid4()),
            result=result,
            confirmer=confirmer
        )
        card.confirmation_record = record
        card.status = CardStatus.CONFIRMED
        card.updated_at = datetime.now()
        return card

    def discard_card(self, card_id: str, reason: str) -> ColorCard:
        card = self.get_card(card_id)
        if not card:
            raise ValueError(f"色卡 {card_id} 不存在")
        card.discard_reason = reason
        card.status = CardStatus.DISCARDED
        card.updated_at = datetime.now()
        return card

    def _add_risk_alert(self, card: ColorCard, risk_type: RiskType, message: str):
        existing = any(a.type == risk_type and not a.resolved for a in card.risk_alerts)
        if not existing:
            alert = RiskAlert(
                id=str(uuid.uuid4()),
                type=risk_type,
                message=message
            )
            card.risk_alerts.append(alert)

    def _check_risks(self, card: ColorCard):
        if len(card.rework_records) >= REWORK_THRESHOLD:
            self._add_risk_alert(
                card, RiskType.REWORK_EXCEED_THRESHOLD,
                f"返调次数已达 {len(card.rework_records)} 次，超过阈值 {REWORK_THRESHOLD} 次"
            )

        if card.status == CardStatus.PENDING_INSPECTION and card.submitted_for_inspection_at:
            overdue_time = card.submitted_for_inspection_at + timedelta(hours=INSPECTION_OVERDUE_HOURS)
            if datetime.now() > overdue_time:
                self._add_risk_alert(
                    card, RiskType.INSPECTION_OVERDUE,
                    f"质检已超期 {INSPECTION_OVERDUE_HOURS} 小时"
                )

    def detect_color_difference_cluster(self) -> List[HighReworkBatchStats]:
        batch_rework_count: Dict[str, int] = defaultdict(int)
        batch_card_count: Dict[str, set] = defaultdict(set)

        for card in self.cards.values():
            for record in card.rework_records:
                for proofing in card.proofing_records:
                    batch_rework_count[proofing.dye_vat_batch] += 1
                    batch_card_count[proofing.dye_vat_batch].add(card.id)

        result = []
        for batch, count in batch_rework_count.items():
            if count >= COLOR_DIFFERENCE_CLUSTER_THRESHOLD:
                for card in self.cards.values():
                    if batch in [p.dye_vat_batch for p in card.proofing_records]:
                        self._add_risk_alert(
                            card, RiskType.COLOR_DIFFERENCE_CLUSTER,
                            f"染缸批次 {batch} 色差问题集中，累计返调 {count} 次"
                        )
                result.append(HighReworkBatchStats(
                    dye_vat_batch=batch,
                    rework_count=count,
                    affected_card_count=len(batch_card_count[batch])
                ))
        return result

    def detect_team_high_rework_rate(self) -> List[Dict]:
        team_stats: Dict[str, Dict] = defaultdict(lambda: {"total": 0, "reworked": 0})

        for card in self.cards.values():
            team_stats[card.responsible_team]["total"] += 1
            if len(card.rework_records) > 0:
                team_stats[card.responsible_team]["reworked"] += 1

        result = []
        for team, stats in team_stats.items():
            if stats["total"] > 0:
                rate = stats["reworked"] / stats["total"]
                if rate >= TEAM_HIGH_REWORK_RATE_THRESHOLD:
                    for card in self.cards.values():
                        if card.responsible_team == team:
                            self._add_risk_alert(
                                card, RiskType.TEAM_HIGH_REWORK_RATE,
                                f"小组 {team} 返调率 {rate:.1%}，超过阈值 {TEAM_HIGH_REWORK_RATE_THRESHOLD:.0%}"
                            )
                    result.append({
                        "team": team,
                        "total_cards": stats["total"],
                        "reworked_cards": stats["reworked"],
                        "rework_rate": rate
                    })
        return result

    def detect_inspection_overdue(self) -> List[Dict]:
        now = datetime.now()
        result = []

        for card in self.cards.values():
            if card.status == CardStatus.PENDING_INSPECTION and card.submitted_for_inspection_at:
                overdue_time = card.submitted_for_inspection_at + timedelta(hours=INSPECTION_OVERDUE_HOURS)
                if now > overdue_time:
                    overdue_hours = round((now - card.submitted_for_inspection_at).total_seconds() / 3600, 1)
                    self._add_risk_alert(
                        card, RiskType.INSPECTION_OVERDUE,
                        f"质检已超期 {overdue_hours} 小时"
                    )
                    result.append({
                        "card_id": card.id,
                        "customer_code": card.customer_code,
                        "fabric_type": card.fabric_type,
                        "overdue_hours": overdue_hours,
                        "submitted_at": card.submitted_for_inspection_at
                    })
        return result

    def get_high_rework_batches(self) -> List[HighReworkBatchStats]:
        self.detect_color_difference_cluster()
        batch_rework_count: Dict[str, int] = defaultdict(int)
        batch_card_count: Dict[str, set] = defaultdict(set)

        for card in self.cards.values():
            for _ in card.rework_records:
                for proofing in card.proofing_records:
                    batch_rework_count[proofing.dye_vat_batch] += 1
                    batch_card_count[proofing.dye_vat_batch].add(card.id)

        result = []
        for batch, count in batch_rework_count.items():
            result.append(HighReworkBatchStats(
                dye_vat_batch=batch,
                rework_count=count,
                affected_card_count=len(batch_card_count[batch])
            ))
        result.sort(key=lambda x: x.rework_count, reverse=True)
        return result

    def get_pending_inspection_stats(self) -> PendingInspectionStats:
        pending_cards = [
            card for card in self.cards.values()
            if card.status == CardStatus.PENDING_INSPECTION
        ]
        overdue_count = 0
        now = datetime.now()
        for card in pending_cards:
            if card.submitted_for_inspection_at:
                overdue_time = card.submitted_for_inspection_at + timedelta(hours=INSPECTION_OVERDUE_HOURS)
                if now > overdue_time:
                    overdue_count += 1
        return PendingInspectionStats(
            pending_count=len(pending_cards),
            overdue_count=overdue_count,
            cards=pending_cards
        )

    def get_confirmation_cycle_stats(self) -> List[ConfirmationCycleStats]:
        customer_stats: Dict[str, Dict] = defaultdict(lambda: {"total_days": 0, "count": 0})

        for card in self.cards.values():
            if card.status == CardStatus.CONFIRMED and card.confirmation_record:
                cycle_days = (card.confirmation_record.created_at - card.created_at).total_seconds() / 86400
                customer_stats[card.customer_code]["total_days"] += cycle_days
                customer_stats[card.customer_code]["count"] += 1

        result = []
        for customer, stats in customer_stats.items():
            if stats["count"] > 0:
                result.append(ConfirmationCycleStats(
                    customer_code=customer,
                    avg_cycle_days=round(stats["total_days"] / stats["count"], 2),
                    total_confirmed=stats["count"]
                ))
        return result

    def get_all_cards_json(self) -> List[Dict]:
        return [card.model_dump(mode='json') for card in self.cards.values()]

    def resolve_risk_alert(self, card_id: str, alert_id: str) -> ColorCard:
        card = self.get_card(card_id)
        if not card:
            raise ValueError(f"色卡 {card_id} 不存在")
        for alert in card.risk_alerts:
            if alert.id == alert_id:
                alert.resolved = True
                card.updated_at = datetime.now()
                return card
        raise ValueError(f"风险预警 {alert_id} 不存在")

    def _filter_cards_by_dashboard_params(self, filters: DashboardFilterParams) -> List[ColorCard]:
        result = list(self.cards.values())

        if filters.customer_code:
            result = [c for c in result if c.customer_code == filters.customer_code]
        if filters.fabric_type:
            result = [c for c in result if c.fabric_type == filters.fabric_type]
        if filters.responsible_team:
            result = [c for c in result if c.responsible_team == filters.responsible_team]
        if filters.status:
            result = [c for c in result if c.status == filters.status]
        if filters.start_date:
            start_dt = datetime.combine(filters.start_date, datetime.min.time())
            result = [c for c in result if c.created_at >= start_dt]
        if filters.end_date:
            end_dt = datetime.combine(filters.end_date, datetime.max.time())
            result = [c for c in result if c.created_at <= end_dt]

        return result

    def _calculate_status_summary(self, cards: List[ColorCard]) -> StatusSummary:
        summary = StatusSummary()
        for card in cards:
            summary.total_count += 1
            if card.status == CardStatus.PENDING_PROOFING:
                summary.pending_proofing_count += 1
            elif card.status == CardStatus.PROOFING:
                summary.proofing_count += 1
            elif card.status == CardStatus.PENDING_INSPECTION:
                summary.pending_inspection_count += 1
            elif card.status == CardStatus.REWORKING:
                summary.reworking_count += 1
            elif card.status == CardStatus.CONFIRMED:
                summary.confirmed_count += 1
            elif card.status == CardStatus.DISCARDED:
                summary.discarded_count += 1
        return summary

    def _calculate_dimension_stats(self, cards: List[ColorCard], dimension_field: str) -> List[DimensionStats]:
        stats_map: Dict[str, Dict] = defaultdict(lambda: {
            "total_cards": 0,
            "total_cycle_days": 0.0,
            "confirmed_count": 0,
            "total_rework_count": 0,
            "overdue_inspection_count": 0,
            "unresolved_risk_count": 0
        })

        now = datetime.now()
        for card in cards:
            key = getattr(card, dimension_field)
            stats = stats_map[key]
            stats["total_cards"] += 1
            stats["total_rework_count"] += len(card.rework_records)

            if card.status == CardStatus.CONFIRMED and card.confirmation_record:
                cycle_days = (card.confirmation_record.created_at - card.created_at).total_seconds() / 86400
                stats["total_cycle_days"] += cycle_days
                stats["confirmed_count"] += 1

            if card.status == CardStatus.PENDING_INSPECTION and card.submitted_for_inspection_at:
                overdue_time = card.submitted_for_inspection_at + timedelta(hours=INSPECTION_OVERDUE_HOURS)
                if now > overdue_time:
                    stats["overdue_inspection_count"] += 1

            unresolved_risks = [a for a in card.risk_alerts if not a.resolved]
            if unresolved_risks:
                stats["unresolved_risk_count"] += 1

        result = []
        for key, stats in stats_map.items():
            avg_cycle = stats["total_cycle_days"] / stats["confirmed_count"] if stats["confirmed_count"] > 0 else 0.0
            result.append(DimensionStats(
                dimension_key=key,
                avg_confirmation_cycle_days=round(avg_cycle, 2),
                total_rework_count=stats["total_rework_count"],
                overdue_inspection_count=stats["overdue_inspection_count"],
                unresolved_risk_count=stats["unresolved_risk_count"],
                total_cards=stats["total_cards"]
            ))
        return result

    def _get_next_suggested_action(self, card: ColorCard) -> str:
        if card.status == CardStatus.PENDING_PROOFING:
            return "请安排打样"
        elif card.status == CardStatus.PROOFING:
            return "请完成打样并提交质检"
        elif card.status == CardStatus.PENDING_INSPECTION:
            return "请进行质检"
        elif card.status == CardStatus.REWORKING:
            return "请安排返调后重新打样"
        elif card.status == CardStatus.CONFIRMED:
            return "色卡已确认，可安排生产"
        elif card.status == CardStatus.DISCARDED:
            return "色卡已废弃"
        return "请跟进处理"

    def _get_risk_info(self, card: ColorCard) -> Tuple[str, str]:
        unresolved_risks = [a for a in card.risk_alerts if not a.resolved]
        if not unresolved_risks:
            return "正常", "none"

        highest_level = "warning"
        risk_types = []
        for risk in unresolved_risks:
            risk_types.append(risk.type.value)
            if risk.level == "danger":
                highest_level = "danger"

        return "、".join(risk_types), highest_level

    def _build_card_detail_item(self, card: ColorCard) -> CardDetailItem:
        last_proofing = card.proofing_records[-1] if card.proofing_records else None
        last_inspection = card.inspection_records[-1] if card.inspection_records else None
        risk_status, risk_level = self._get_risk_info(card)

        return CardDetailItem(
            card_id=card.id,
            customer_code=card.customer_code,
            fabric_type=card.fabric_type,
            color_card_version=card.color_card_version,
            responsible_team=card.responsible_team,
            current_status=card.status,
            last_proofing_record=last_proofing,
            last_inspection_conclusion=last_inspection.conclusion if last_inspection else None,
            current_risk_status=risk_status,
            risk_level=risk_level,
            next_suggested_action=self._get_next_suggested_action(card),
            created_at=card.created_at,
            updated_at=card.updated_at
        )

    def get_dashboard_overview(self, filters: DashboardFilterParams) -> DashboardOverviewResponse:
        cards = self._filter_cards_by_dashboard_params(filters)
        status_summary = self._calculate_status_summary(cards)
        customer_stats = self._calculate_dimension_stats(cards, "customer_code")
        team_stats = self._calculate_dimension_stats(cards, "responsible_team")

        return DashboardOverviewResponse(
            filter_params=filters,
            status_summary=status_summary,
            customer_dimension_stats=customer_stats,
            team_dimension_stats=team_stats
        )

    def get_dashboard_detail(self, filters: DashboardFilterParams, skip: int = 0, limit: int = 100) -> DashboardDetailResponse:
        cards = self._filter_cards_by_dashboard_params(filters)
        total = len(cards)
        cards = cards[skip:skip + limit]
        items = [self._build_card_detail_item(card) for card in cards]

        return DashboardDetailResponse(
            filter_params=filters,
            total=total,
            items=items
        )


storage = MemoryStorage()
