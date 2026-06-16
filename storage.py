import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

from models import (
    ColorCard, ColorCardCreate, CardStatus, RiskAlert, RiskType, DateFieldType,
    ProofingRecord, InspectionRecord, ReworkRecord, ConfirmationRecord,
    FilterParams, HighReworkBatchStats, PendingInspectionStats, ConfirmationCycleStats,
    DashboardFilterParams, StatusSummary, DimensionStats, CardDetailItem,
    DashboardOverviewResponse, DashboardDetailResponse,
    ResampleApplication, ResampleApplicationCreate, ResampleStatus, ResamplePriority,
    ResampleActionRecord, ResampleActionType, ResampleFilterParams,
    ResampleStatusSummary, ResampleDimensionStats, ResampleDashboardOverview,
    ResampleProofingRecord, ResampleInspectionRecord, ResampleReworkRecord,
    ResampleConfirmationRecord, ResampleProofingSubmit, ResampleInspectionSubmit,
    ResampleReworkSubmit, ResampleConfirmationSubmit,
    ArchiveSourceType, ColorCardSnapshot, ResampleApplicationSnapshot,
    DeliveryArchive, DeliveryArchiveCreate, ArchiveFilterParams,
    ArchiveStatsSummary, ArchiveDimensionStats, ArchiveStatsResponse
)
from config import (
    REWORK_THRESHOLD, INSPECTION_OVERDUE_HOURS,
    COLOR_DIFFERENCE_CLUSTER_THRESHOLD, TEAM_HIGH_REWORK_RATE_THRESHOLD
)


class MemoryStorage:
    def __init__(self):
        self.cards: Dict[str, ColorCard] = {}
        self.resample_applications: Dict[str, ResampleApplication] = {}
        self.delivery_archives: Dict[str, DeliveryArchive] = {}
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
        self._resolve_risk_by_type(card, RiskType.INSPECTION_OVERDUE)
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
        for alert in card.risk_alerts:
            if not alert.resolved:
                alert.resolved = True
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

    def _resolve_risk_by_type(self, card: ColorCard, risk_type: RiskType):
        for alert in card.risk_alerts:
            if alert.type == risk_type and not alert.resolved:
                alert.resolved = True

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

    def _get_card_date_by_field(self, card: ColorCard, date_field: DateFieldType) -> Optional[datetime]:
        if date_field == DateFieldType.CREATED_AT:
            return card.created_at
        elif date_field == DateFieldType.UPDATED_AT:
            return card.updated_at
        elif date_field == DateFieldType.PROOFING_AT:
            return card.proofing_records[-1].created_at if card.proofing_records else None
        elif date_field == DateFieldType.INSPECTION_AT:
            return card.inspection_records[-1].created_at if card.inspection_records else None
        elif date_field == DateFieldType.CONFIRMATION_AT:
            return card.confirmation_record.created_at if card.confirmation_record else None
        return None

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

        if filters.start_date or filters.end_date:
            filtered = []
            for card in result:
                card_date = self._get_card_date_by_field(card, filters.date_field)
                if card_date is None:
                    continue
                if filters.start_date:
                    start_dt = datetime.combine(filters.start_date, datetime.min.time())
                    if card_date < start_dt:
                        continue
                if filters.end_date:
                    end_dt = datetime.combine(filters.end_date, datetime.max.time())
                    if card_date > end_dt:
                        continue
                filtered.append(card)
            result = filtered

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
            last_inspection_record=last_inspection,
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
        fabric_stats = self._calculate_dimension_stats(cards, "fabric_type")
        team_stats = self._calculate_dimension_stats(cards, "responsible_team")

        return DashboardOverviewResponse(
            filter_params=filters,
            status_summary=status_summary,
            customer_dimension_stats=customer_stats,
            fabric_dimension_stats=fabric_stats,
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

    def create_resample_application(self, app_create: ResampleApplicationCreate) -> ResampleApplication:
        original_card = self.get_card(app_create.original_card_id)
        if not original_card:
            raise ValueError(f"原色卡 {app_create.original_card_id} 不存在")
        if original_card.status != CardStatus.CONFIRMED:
            raise ValueError(f"只有已确认的色卡才能发起复样申请，当前状态：{original_card.status}")

        app_id = str(uuid.uuid4())
        application = ResampleApplication(
            id=app_id,
            **app_create.model_dump(),
            customer_code=original_card.customer_code,
            fabric_type=original_card.fabric_type,
            color_card_version=original_card.color_card_version,
            responsible_team=original_card.responsible_team,
            original_confirmation_record=original_card.confirmation_record
        )

        submit_record = ResampleActionRecord(
            id=str(uuid.uuid4()),
            action_type=ResampleActionType.SUBMIT,
            operator=app_create.applicant,
            remark="提交复样申请"
        )
        application.action_records.append(submit_record)

        self.resample_applications[app_id] = application
        return application

    def get_resample_application(self, app_id: str) -> Optional[ResampleApplication]:
        return self.resample_applications.get(app_id)

    def list_resample_applications(self, filters: ResampleFilterParams) -> Tuple[List[ResampleApplication], int]:
        result = list(self.resample_applications.values())

        if filters.customer_code:
            result = [a for a in result if a.customer_code == filters.customer_code]
        if filters.fabric_type:
            result = [a for a in result if a.fabric_type == filters.fabric_type]
        if filters.responsible_team:
            result = [a for a in result if a.responsible_team == filters.responsible_team]
        if filters.priority:
            result = [a for a in result if a.priority == filters.priority]
        if filters.status:
            result = [a for a in result if a.status == filters.status]
        if filters.start_date:
            start_dt = datetime.combine(filters.start_date, datetime.min.time())
            result = [a for a in result if a.created_at >= start_dt]
        if filters.end_date:
            end_dt = datetime.combine(filters.end_date, datetime.max.time())
            result = [a for a in result if a.created_at <= end_dt]

        total = len(result)
        result = result[filters.skip:filters.skip + filters.limit]
        return result, total

    def accept_resample_application(self, app_id: str, operator: str, remark: Optional[str] = None) -> ResampleApplication:
        application = self.get_resample_application(app_id)
        if not application:
            raise ValueError(f"复样申请 {app_id} 不存在")
        if application.status != ResampleStatus.PENDING:
            raise ValueError(f"当前状态 {application.status} 不允许受理")

        application.status = ResampleStatus.PROCESSING
        application.updated_at = datetime.now()

        action_record = ResampleActionRecord(
            id=str(uuid.uuid4()),
            action_type=ResampleActionType.ACCEPT,
            operator=operator,
            remark=remark or "受理复样申请"
        )
        application.action_records.append(action_record)

        return application

    def reject_resample_application(self, app_id: str, operator: str, reason: str) -> ResampleApplication:
        application = self.get_resample_application(app_id)
        if not application:
            raise ValueError(f"复样申请 {app_id} 不存在")
        if application.status != ResampleStatus.PENDING:
            raise ValueError(f"当前状态 {application.status} 不允许驳回")

        application.status = ResampleStatus.REJECTED
        application.rejection_reason = reason
        application.updated_at = datetime.now()

        action_record = ResampleActionRecord(
            id=str(uuid.uuid4()),
            action_type=ResampleActionType.REJECT,
            operator=operator,
            remark=reason
        )
        application.action_records.append(action_record)

        return application

    def complete_resample_application(self, app_id: str, operator: str, remark: Optional[str] = None) -> ResampleApplication:
        application = self.get_resample_application(app_id)
        if not application:
            raise ValueError(f"复样申请 {app_id} 不存在")
        if application.status != ResampleStatus.PROCESSING:
            raise ValueError(f"当前状态 {application.status} 不允许完成")
        if application.resample_status != CardStatus.CONFIRMED:
            raise ValueError(f"当前复样状态 {application.resample_status} 不允许完成")

        application.status = ResampleStatus.COMPLETED
        application.completion_remark = remark
        application.updated_at = datetime.now()

        action_record = ResampleActionRecord(
            id=str(uuid.uuid4()),
            action_type=ResampleActionType.COMPLETE,
            operator=operator,
            remark=remark or "完成复样"
        )
        application.action_records.append(action_record)

        return application

    def add_resample_follow_up(self, app_id: str, operator: str, remark: str) -> ResampleApplication:
        application = self.get_resample_application(app_id)
        if not application:
            raise ValueError(f"复样申请 {app_id} 不存在")
        if application.status != ResampleStatus.PROCESSING:
            raise ValueError(f"当前状态 {application.status} 不允许添加跟进记录，只能在受理后添加")

        action_record = ResampleActionRecord(
            id=str(uuid.uuid4()),
            action_type=ResampleActionType.FOLLOW_UP,
            operator=operator,
            remark=remark
        )
        application.action_records.append(action_record)
        application.updated_at = datetime.now()

        return application

    def start_resample_proofing(self, app_id: str, operator: str) -> ResampleApplication:
        application = self.get_resample_application(app_id)
        if not application:
            raise ValueError(f"复样申请 {app_id} 不存在")
        if application.status != ResampleStatus.PROCESSING:
            raise ValueError(f"当前申请状态 {application.status} 不允许开始打样")
        if application.resample_status not in [CardStatus.PENDING_PROOFING, CardStatus.REWORKING]:
            raise ValueError(f"当前复样状态 {application.resample_status} 不允许开始打样")

        application.resample_status = CardStatus.PROOFING
        application.updated_at = datetime.now()

        action_record = ResampleActionRecord(
            id=str(uuid.uuid4()),
            action_type=ResampleActionType.PROOFING_START,
            operator=operator,
            remark="开始复样打样"
        )
        application.action_records.append(action_record)

        return application

    def complete_resample_proofing(self, app_id: str, submit: ResampleProofingSubmit) -> ResampleApplication:
        application = self.get_resample_application(app_id)
        if not application:
            raise ValueError(f"复样申请 {app_id} 不存在")
        if application.status != ResampleStatus.PROCESSING:
            raise ValueError(f"当前申请状态 {application.status} 不允许完成打样")
        if application.resample_status != CardStatus.PROOFING:
            raise ValueError(f"当前复样状态 {application.resample_status} 不允许完成打样")

        record = ResampleProofingRecord(
            id=str(uuid.uuid4()),
            dye_vat_batch=submit.dye_vat_batch,
            proofing_process=submit.proofing_process
        )
        application.resample_proofing_records.append(record)
        application.resample_status = CardStatus.PENDING_INSPECTION
        application.resample_submitted_for_inspection_at = datetime.now()
        application.updated_at = datetime.now()

        action_record = ResampleActionRecord(
            id=str(uuid.uuid4()),
            action_type=ResampleActionType.PROOFING_COMPLETE,
            operator=submit.operator,
            remark=f"完成复样打样，染缸批次：{submit.dye_vat_batch}，工艺：{submit.proofing_process}"
        )
        application.action_records.append(action_record)

        return application

    def add_resample_inspection(self, app_id: str, submit: ResampleInspectionSubmit) -> ResampleApplication:
        application = self.get_resample_application(app_id)
        if not application:
            raise ValueError(f"复样申请 {app_id} 不存在")
        if application.status != ResampleStatus.PROCESSING:
            raise ValueError(f"当前申请状态 {application.status} 不允许提交质检")
        if application.resample_status != CardStatus.PENDING_INSPECTION:
            raise ValueError(f"当前复样状态 {application.resample_status} 不允许提交质检")

        record = ResampleInspectionRecord(
            id=str(uuid.uuid4()),
            color_comparison_result=submit.color_comparison_result,
            color_difference_value=submit.color_difference_value,
            inspector=submit.inspector,
            conclusion=submit.conclusion
        )
        application.resample_inspection_records.append(record)
        application.updated_at = datetime.now()

        action_record = ResampleActionRecord(
            id=str(uuid.uuid4()),
            action_type=ResampleActionType.INSPECTION,
            operator=submit.inspector,
            remark=f"复样质检，结论：{submit.conclusion}，色差：{submit.color_comparison_result}"
        )
        application.action_records.append(action_record)

        return application

    def add_resample_rework(self, app_id: str, submit: ResampleReworkSubmit) -> ResampleApplication:
        application = self.get_resample_application(app_id)
        if not application:
            raise ValueError(f"复样申请 {app_id} 不存在")
        if application.status != ResampleStatus.PROCESSING:
            raise ValueError(f"当前申请状态 {application.status} 不允许返调")
        if application.resample_status != CardStatus.PENDING_INSPECTION:
            raise ValueError(f"当前复样状态 {application.resample_status} 不允许返调")
        if not self._has_valid_resample_inspection_after_last_proofing(application):
            raise ValueError("返调前必须存在本次打样后的质检结论")

        record = ResampleReworkRecord(
            id=str(uuid.uuid4()),
            rework_action=submit.rework_action,
            reason=submit.reason,
            operator=submit.operator
        )
        application.resample_rework_records.append(record)
        application.resample_status = CardStatus.REWORKING
        application.updated_at = datetime.now()

        action_record = ResampleActionRecord(
            id=str(uuid.uuid4()),
            action_type=ResampleActionType.REWORK,
            operator=submit.operator,
            remark=f"复样返调，措施：{submit.rework_action}，原因：{submit.reason}"
        )
        application.action_records.append(action_record)

        return application

    def confirm_resample(self, app_id: str, submit: ResampleConfirmationSubmit) -> ResampleApplication:
        application = self.get_resample_application(app_id)
        if not application:
            raise ValueError(f"复样申请 {app_id} 不存在")
        if application.status != ResampleStatus.PROCESSING:
            raise ValueError(f"当前申请状态 {application.status} 不允许确认")
        if application.resample_status != CardStatus.PENDING_INSPECTION:
            raise ValueError(f"当前复样状态 {application.resample_status} 不允许确认")
        if not self._has_valid_resample_inspection_after_last_proofing(application):
            raise ValueError("确认前必须存在本次打样后的质检结论")

        record = ResampleConfirmationRecord(
            id=str(uuid.uuid4()),
            result=submit.result,
            confirmer=submit.confirmer
        )
        application.resample_confirmation_record = record
        application.resample_status = CardStatus.CONFIRMED
        application.updated_at = datetime.now()

        action_record = ResampleActionRecord(
            id=str(uuid.uuid4()),
            action_type=ResampleActionType.CONFIRM,
            operator=submit.confirmer,
            remark=f"复样确认，结果：{submit.result}"
        )
        application.action_records.append(action_record)

        return application

    def _has_valid_resample_inspection_after_last_proofing(self, application: ResampleApplication) -> bool:
        if not application.resample_inspection_records or not application.resample_proofing_records:
            return False
        last_proofing_time = application.resample_proofing_records[-1].created_at
        last_inspection_time = application.resample_inspection_records[-1].created_at
        return last_inspection_time > last_proofing_time

    def get_resample_dashboard_overview(self, filters: Optional[ResampleFilterParams] = None) -> ResampleDashboardOverview:
        applications = list(self.resample_applications.values())

        if filters:
            if filters.customer_code:
                applications = [a for a in applications if a.customer_code == filters.customer_code]
            if filters.fabric_type:
                applications = [a for a in applications if a.fabric_type == filters.fabric_type]
            if filters.responsible_team:
                applications = [a for a in applications if a.responsible_team == filters.responsible_team]
            if filters.priority:
                applications = [a for a in applications if a.priority == filters.priority]
            if filters.status:
                applications = [a for a in applications if a.status == filters.status]
            if filters.start_date:
                start_dt = datetime.combine(filters.start_date, datetime.min.time())
                applications = [a for a in applications if a.created_at >= start_dt]
            if filters.end_date:
                end_dt = datetime.combine(filters.end_date, datetime.max.time())
                applications = [a for a in applications if a.created_at <= end_dt]

        status_summary = ResampleStatusSummary()
        for app in applications:
            status_summary.total_count += 1
            if app.status == ResampleStatus.PENDING:
                status_summary.pending_count += 1
            elif app.status == ResampleStatus.PROCESSING:
                status_summary.processing_count += 1
            elif app.status == ResampleStatus.COMPLETED:
                status_summary.completed_count += 1
            elif app.status == ResampleStatus.REJECTED:
                status_summary.rejected_count += 1

        customer_stats_map: Dict[str, ResampleDimensionStats] = defaultdict(
            lambda: ResampleDimensionStats(dimension_key="")
        )
        for app in applications:
            stat = customer_stats_map[app.customer_code]
            stat.dimension_key = app.customer_code
            stat.total_count += 1
            if app.status == ResampleStatus.PENDING:
                stat.pending_count += 1
            elif app.status == ResampleStatus.PROCESSING:
                stat.processing_count += 1
            elif app.status == ResampleStatus.COMPLETED:
                stat.completed_count += 1
            elif app.status == ResampleStatus.REJECTED:
                stat.rejected_count += 1
        customer_stats = list(customer_stats_map.values())

        team_stats_map: Dict[str, ResampleDimensionStats] = defaultdict(
            lambda: ResampleDimensionStats(dimension_key="")
        )
        for app in applications:
            stat = team_stats_map[app.responsible_team]
            stat.dimension_key = app.responsible_team
            stat.total_count += 1
            if app.status == ResampleStatus.PENDING:
                stat.pending_count += 1
            elif app.status == ResampleStatus.PROCESSING:
                stat.processing_count += 1
            elif app.status == ResampleStatus.COMPLETED:
                stat.completed_count += 1
            elif app.status == ResampleStatus.REJECTED:
                stat.rejected_count += 1
        team_stats = list(team_stats_map.values())

        priority_stats_map: Dict[str, ResampleDimensionStats] = defaultdict(
            lambda: ResampleDimensionStats(dimension_key="")
        )
        for app in applications:
            stat = priority_stats_map[app.priority]
            stat.dimension_key = app.priority
            stat.total_count += 1
            if app.status == ResampleStatus.PENDING:
                stat.pending_count += 1
            elif app.status == ResampleStatus.PROCESSING:
                stat.processing_count += 1
            elif app.status == ResampleStatus.COMPLETED:
                stat.completed_count += 1
            elif app.status == ResampleStatus.REJECTED:
                stat.rejected_count += 1
        priority_stats = list(priority_stats_map.values())

        return ResampleDashboardOverview(
            status_summary=status_summary,
            customer_stats=customer_stats,
            team_stats=team_stats,
            priority_stats=priority_stats
        )

    def get_all_resample_applications_json(self) -> List[Dict]:
        return [app.model_dump(mode='json') for app in self.resample_applications.values()]

    def get_full_export_data(self) -> Dict[str, Any]:
        return {
            "color_cards": self.get_all_cards_json(),
            "resample_applications": self.get_all_resample_applications_json()
        }

    def _build_color_card_snapshot(self, card: ColorCard) -> ColorCardSnapshot:
        return ColorCardSnapshot(
            id=card.id,
            customer_code=card.customer_code,
            fabric_type=card.fabric_type,
            color_card_version=card.color_card_version,
            responsible_team=card.responsible_team,
            status=card.status,
            proofing_records=[pr.model_copy() for pr in card.proofing_records],
            inspection_records=[ir.model_copy() for ir in card.inspection_records],
            rework_records=[rr.model_copy() for rr in card.rework_records],
            confirmation_record=card.confirmation_record.model_copy() if card.confirmation_record else None,
            risk_alerts=[ra.model_copy() for ra in card.risk_alerts],
            created_at=card.created_at,
            updated_at=card.updated_at
        )

    def _build_resample_snapshot(self, app: ResampleApplication) -> ResampleApplicationSnapshot:
        return ResampleApplicationSnapshot(
            id=app.id,
            original_card_id=app.original_card_id,
            reason=app.reason,
            applicant=app.applicant,
            expected_completion_date=app.expected_completion_date,
            customer_feedback=app.customer_feedback,
            priority=app.priority,
            status=app.status,
            customer_code=app.customer_code,
            fabric_type=app.fabric_type,
            color_card_version=app.color_card_version,
            responsible_team=app.responsible_team,
            original_confirmation_record=app.original_confirmation_record.model_copy() if app.original_confirmation_record else None,
            resample_status=app.resample_status,
            resample_proofing_records=[pr.model_copy() for pr in app.resample_proofing_records],
            resample_inspection_records=[ir.model_copy() for ir in app.resample_inspection_records],
            resample_rework_records=[rr.model_copy() for rr in app.resample_rework_records],
            resample_confirmation_record=app.resample_confirmation_record.model_copy() if app.resample_confirmation_record else None,
            action_records=[ar.model_copy() for ar in app.action_records],
            rejection_reason=app.rejection_reason,
            completion_remark=app.completion_remark,
            created_at=app.created_at,
            updated_at=app.updated_at
        )

    def _check_source_already_archived(self, source_type: ArchiveSourceType, source_id: str) -> bool:
        for archive in self.delivery_archives.values():
            if archive.source_type == source_type and archive.source_id == source_id:
                return True
        return False

    def create_delivery_archive(self, archive_create: DeliveryArchiveCreate) -> DeliveryArchive:
        if self._check_source_already_archived(archive_create.source_type, archive_create.source_id):
            raise ValueError(f"{archive_create.source_type.value} {archive_create.source_id} 已归档，不允许重复归档")

        color_card_snapshot = None
        resample_snapshot = None
        source_status = ""
        customer_code = ""
        fabric_type = ""
        color_card_version = ""
        responsible_team = ""

        if archive_create.source_type == ArchiveSourceType.ORIGINAL_CARD:
            card = self.get_card(archive_create.source_id)
            if not card:
                raise ValueError(f"原色卡 {archive_create.source_id} 不存在")
            if card.status != CardStatus.CONFIRMED:
                raise ValueError(f"只有已确认的原色卡才能归档，当前状态：{card.status}")
            source_status = card.status.value
            customer_code = card.customer_code
            fabric_type = card.fabric_type
            color_card_version = card.color_card_version
            responsible_team = card.responsible_team
            color_card_snapshot = self._build_color_card_snapshot(card)

        elif archive_create.source_type == ArchiveSourceType.RESAMPLE:
            app = self.get_resample_application(archive_create.source_id)
            if not app:
                raise ValueError(f"复样申请 {archive_create.source_id} 不存在")
            if app.status != ResampleStatus.COMPLETED:
                raise ValueError(f"只有已完成的复样申请才能归档，当前状态：{app.status}")
            source_status = app.status.value
            customer_code = app.customer_code
            fabric_type = app.fabric_type
            color_card_version = app.color_card_version
            responsible_team = app.responsible_team
            resample_snapshot = self._build_resample_snapshot(app)

        archive_id = str(uuid.uuid4())
        now = datetime.now()
        archive = DeliveryArchive(
            id=archive_id,
            source_type=archive_create.source_type,
            source_id=archive_create.source_id,
            source_status=source_status,
            delivery_batch_no=archive_create.delivery_batch_no,
            delivery_target=archive_create.delivery_target,
            delivery_remark=archive_create.delivery_remark,
            archivist=archive_create.archivist,
            customer_code=customer_code,
            fabric_type=fabric_type,
            color_card_version=color_card_version,
            responsible_team=responsible_team,
            color_card_snapshot=color_card_snapshot,
            resample_snapshot=resample_snapshot,
            created_at=now,
            archived_at=now
        )

        self.delivery_archives[archive_id] = archive
        return archive

    def get_delivery_archive(self, archive_id: str) -> Optional[DeliveryArchive]:
        return self.delivery_archives.get(archive_id)

    def list_delivery_archives(self, filters: ArchiveFilterParams) -> Tuple[List[DeliveryArchive], int]:
        result = list(self.delivery_archives.values())

        if filters.customer_code:
            result = [a for a in result if a.customer_code == filters.customer_code]
        if filters.fabric_type:
            result = [a for a in result if a.fabric_type == filters.fabric_type]
        if filters.responsible_team:
            result = [a for a in result if a.responsible_team == filters.responsible_team]
        if filters.delivery_batch_no:
            result = [a for a in result if a.delivery_batch_no == filters.delivery_batch_no]
        if filters.source_type:
            result = [a for a in result if a.source_type == filters.source_type]
        if filters.archivist:
            result = [a for a in result if a.archivist == filters.archivist]
        if filters.start_date:
            start_dt = datetime.combine(filters.start_date, datetime.min.time())
            result = [a for a in result if a.archived_at >= start_dt]
        if filters.end_date:
            end_dt = datetime.combine(filters.end_date, datetime.max.time())
            result = [a for a in result if a.archived_at <= end_dt]

        result.sort(key=lambda x: x.archived_at, reverse=True)

        total = len(result)
        result = result[filters.skip:filters.skip + filters.limit]
        return result, total

    def _calculate_archive_dimension_stats(
        self, archives: List[DeliveryArchive], dimension_field: str
    ) -> List[ArchiveDimensionStats]:
        stats_map: Dict[str, ArchiveDimensionStats] = defaultdict(
            lambda: ArchiveDimensionStats(dimension_key="")
        )

        for archive in archives:
            key = getattr(archive, dimension_field)
            stat = stats_map[key]
            stat.dimension_key = key
            stat.total_count += 1
            if archive.source_type == ArchiveSourceType.ORIGINAL_CARD:
                stat.original_card_count += 1
            elif archive.source_type == ArchiveSourceType.RESAMPLE:
                stat.resample_count += 1

        return list(stats_map.values())

    def get_archive_stats(self, filters: ArchiveFilterParams) -> ArchiveStatsResponse:
        all_archives = list(self.delivery_archives.values())
        filtered = all_archives

        if filters.customer_code:
            filtered = [a for a in filtered if a.customer_code == filters.customer_code]
        if filters.fabric_type:
            filtered = [a for a in filtered if a.fabric_type == filters.fabric_type]
        if filters.responsible_team:
            filtered = [a for a in filtered if a.responsible_team == filters.responsible_team]
        if filters.delivery_batch_no:
            filtered = [a for a in filtered if a.delivery_batch_no == filters.delivery_batch_no]
        if filters.source_type:
            filtered = [a for a in filtered if a.source_type == filters.source_type]
        if filters.archivist:
            filtered = [a for a in filtered if a.archivist == filters.archivist]
        if filters.start_date:
            start_dt = datetime.combine(filters.start_date, datetime.min.time())
            filtered = [a for a in filtered if a.archived_at >= start_dt]
        if filters.end_date:
            end_dt = datetime.combine(filters.end_date, datetime.max.time())
            filtered = [a for a in filtered if a.archived_at <= end_dt]

        summary = ArchiveStatsSummary()
        summary.total_count = len(filtered)
        summary.original_card_count = sum(1 for a in filtered if a.source_type == ArchiveSourceType.ORIGINAL_CARD)
        summary.resample_count = sum(1 for a in filtered if a.source_type == ArchiveSourceType.RESAMPLE)
        summary.customer_count = len(set(a.customer_code for a in filtered))
        summary.fabric_count = len(set(a.fabric_type for a in filtered))
        summary.team_count = len(set(a.responsible_team for a in filtered))
        summary.batch_count = len(set(a.delivery_batch_no for a in filtered))

        customer_stats = self._calculate_archive_dimension_stats(filtered, "customer_code")
        fabric_stats = self._calculate_archive_dimension_stats(filtered, "fabric_type")
        team_stats = self._calculate_archive_dimension_stats(filtered, "responsible_team")
        batch_stats = self._calculate_archive_dimension_stats(filtered, "delivery_batch_no")
        archivist_stats = self._calculate_archive_dimension_stats(filtered, "archivist")

        source_type_map: Dict[str, ArchiveDimensionStats] = defaultdict(
            lambda: ArchiveDimensionStats(dimension_key="")
        )
        for archive in filtered:
            key = archive.source_type.value
            stat = source_type_map[key]
            stat.dimension_key = key
            stat.total_count += 1
            if archive.source_type == ArchiveSourceType.ORIGINAL_CARD:
                stat.original_card_count += 1
            elif archive.source_type == ArchiveSourceType.RESAMPLE:
                stat.resample_count += 1
        source_type_stats = list(source_type_map.values())

        return ArchiveStatsResponse(
            filter_params=filters,
            summary=summary,
            customer_stats=customer_stats,
            fabric_stats=fabric_stats,
            team_stats=team_stats,
            batch_stats=batch_stats,
            source_type_stats=source_type_stats,
            archivist_stats=archivist_stats
        )

    def get_single_archive_export(self, archive_id: str) -> Dict[str, Any]:
        archive = self.get_delivery_archive(archive_id)
        if not archive:
            raise ValueError(f"归档记录 {archive_id} 不存在")
        return archive.model_dump(mode='json')

    def get_all_archives_json(self) -> List[Dict]:
        return [a.model_dump(mode='json') for a in self.delivery_archives.values()]


storage = MemoryStorage()
