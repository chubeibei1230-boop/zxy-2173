from enum import Enum
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class CardStatus(str, Enum):
    PENDING_PROOFING = "待打样"
    PROOFING = "打样中"
    PENDING_INSPECTION = "待质检"
    REWORKING = "返调中"
    CONFIRMED = "已确认"
    DISCARDED = "已废弃"


class ResampleStatus(str, Enum):
    PENDING = "待受理"
    PROCESSING = "处理中"
    COMPLETED = "已完成"
    REJECTED = "已驳回"


class ResamplePriority(str, Enum):
    LOW = "低"
    MEDIUM = "中"
    HIGH = "高"
    URGENT = "紧急"


class ResampleActionType(str, Enum):
    SUBMIT = "提交申请"
    ACCEPT = "受理"
    REJECT = "驳回"
    COMPLETE = "完成"
    FOLLOW_UP = "跟进记录"
    PROOFING_START = "复样打样开始"
    PROOFING_COMPLETE = "复样打样完成"
    INSPECTION = "复样质检"
    REWORK = "复样返调"
    CONFIRM = "复样确认"


class RiskType(str, Enum):
    REWORK_EXCEED_THRESHOLD = "返调次数超限"
    COLOR_DIFFERENCE_CLUSTER = "染缸批次色差集中"
    INSPECTION_OVERDUE = "质检超期"
    TEAM_HIGH_REWORK_RATE = "小组返调率偏高"


class DateFieldType(str, Enum):
    CREATED_AT = "创建时间"
    PROOFING_AT = "最近打样时间"
    INSPECTION_AT = "最近质检时间"
    CONFIRMATION_AT = "确认时间"
    UPDATED_AT = "更新时间"


class ProofingRecord(BaseModel):
    id: str
    dye_vat_batch: str
    proofing_process: str
    created_at: datetime = Field(default_factory=datetime.now)


class InspectionRecord(BaseModel):
    id: str
    color_comparison_result: str
    color_difference_value: Optional[float] = None
    inspector: str
    conclusion: str
    created_at: datetime = Field(default_factory=datetime.now)


class ReworkRecord(BaseModel):
    id: str
    rework_action: str
    reason: str
    operator: str
    created_at: datetime = Field(default_factory=datetime.now)


class ConfirmationRecord(BaseModel):
    id: str
    result: str
    confirmer: str
    created_at: datetime = Field(default_factory=datetime.now)


class RiskAlert(BaseModel):
    id: str
    type: RiskType
    message: str
    level: str = "warning"
    created_at: datetime = Field(default_factory=datetime.now)
    resolved: bool = False


class ColorCardBase(BaseModel):
    customer_code: str
    fabric_type: str
    color_card_version: str
    responsible_team: str


class ColorCardCreate(ColorCardBase):
    pass


class ColorCard(ColorCardBase):
    id: str
    status: CardStatus = CardStatus.PENDING_PROOFING
    proofing_records: List[ProofingRecord] = Field(default_factory=list)
    inspection_records: List[InspectionRecord] = Field(default_factory=list)
    rework_records: List[ReworkRecord] = Field(default_factory=list)
    confirmation_record: Optional[ConfirmationRecord] = None
    discard_reason: Optional[str] = None
    risk_alerts: List[RiskAlert] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    submitted_for_inspection_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ProofingSubmit(BaseModel):
    dye_vat_batch: str
    proofing_process: str


class InspectionSubmit(BaseModel):
    color_comparison_result: str
    color_difference_value: Optional[float] = None
    inspector: str
    conclusion: str


class ReworkSubmit(BaseModel):
    rework_action: str
    reason: str
    operator: str


class ConfirmationSubmit(BaseModel):
    result: str
    confirmer: str


class DiscardSubmit(BaseModel):
    reason: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    username: str
    password: str


class FilterParams(BaseModel):
    customer_code: Optional[str] = None
    fabric_type: Optional[str] = None
    dye_vat_batch: Optional[str] = None
    color_card_version: Optional[str] = None
    status: Optional[CardStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    inspection_conclusion: Optional[str] = None
    skip: int = 0
    limit: int = 100


class HighReworkBatchStats(BaseModel):
    dye_vat_batch: str
    rework_count: int
    affected_card_count: int


class PendingInspectionStats(BaseModel):
    pending_count: int
    overdue_count: int
    cards: List[ColorCard]


class ConfirmationCycleStats(BaseModel):
    customer_code: str
    avg_cycle_days: float
    total_confirmed: int


class DashboardFilterParams(BaseModel):
    customer_code: Optional[str] = None
    fabric_type: Optional[str] = None
    responsible_team: Optional[str] = None
    status: Optional[CardStatus] = None
    date_field: DateFieldType = DateFieldType.CREATED_AT
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @classmethod
    def validate_date_range(cls, start_date: Optional[date], end_date: Optional[date]):
        if start_date and end_date and start_date > end_date:
            raise ValueError("开始日期不能大于结束日期")


class StatusSummary(BaseModel):
    pending_proofing_count: int = 0
    proofing_count: int = 0
    pending_inspection_count: int = 0
    reworking_count: int = 0
    confirmed_count: int = 0
    discarded_count: int = 0
    total_count: int = 0


class DimensionStats(BaseModel):
    dimension_key: str
    avg_confirmation_cycle_days: float = 0.0
    total_rework_count: int = 0
    overdue_inspection_count: int = 0
    unresolved_risk_count: int = 0
    total_cards: int = 0


class CardDetailItem(BaseModel):
    card_id: str
    customer_code: str
    fabric_type: str
    color_card_version: str
    responsible_team: str
    current_status: CardStatus
    last_proofing_record: Optional[ProofingRecord] = None
    last_inspection_record: Optional[InspectionRecord] = None
    current_risk_status: str = "正常"
    risk_level: str = "none"
    next_suggested_action: str
    created_at: datetime
    updated_at: datetime


class DashboardOverviewResponse(BaseModel):
    filter_params: DashboardFilterParams
    status_summary: StatusSummary
    customer_dimension_stats: List[DimensionStats]
    fabric_dimension_stats: List[DimensionStats]
    team_dimension_stats: List[DimensionStats]


class DashboardDetailResponse(BaseModel):
    filter_params: DashboardFilterParams
    total: int
    items: List[CardDetailItem]


class ResampleActionRecord(BaseModel):
    id: str
    action_type: ResampleActionType
    operator: str
    remark: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class ResampleApplicationBase(BaseModel):
    original_card_id: str
    reason: str
    applicant: str
    expected_completion_date: date
    customer_feedback: str
    priority: ResamplePriority = ResamplePriority.MEDIUM


class ResampleApplicationCreate(ResampleApplicationBase):
    pass


class ResampleProofingRecord(BaseModel):
    id: str
    dye_vat_batch: str
    proofing_process: str
    created_at: datetime = Field(default_factory=datetime.now)


class ResampleInspectionRecord(BaseModel):
    id: str
    color_comparison_result: str
    color_difference_value: Optional[float] = None
    inspector: str
    conclusion: str
    created_at: datetime = Field(default_factory=datetime.now)


class ResampleReworkRecord(BaseModel):
    id: str
    rework_action: str
    reason: str
    operator: str
    created_at: datetime = Field(default_factory=datetime.now)


class ResampleConfirmationRecord(BaseModel):
    id: str
    result: str
    confirmer: str
    created_at: datetime = Field(default_factory=datetime.now)


class ResampleApplication(ResampleApplicationBase):
    id: str
    status: ResampleStatus = ResampleStatus.PENDING
    customer_code: str
    fabric_type: str
    color_card_version: str
    responsible_team: str
    original_confirmation_record: Optional[ConfirmationRecord] = None
    resample_status: CardStatus = CardStatus.PENDING_PROOFING
    resample_proofing_records: List[ResampleProofingRecord] = Field(default_factory=list)
    resample_inspection_records: List[ResampleInspectionRecord] = Field(default_factory=list)
    resample_rework_records: List[ResampleReworkRecord] = Field(default_factory=list)
    resample_confirmation_record: Optional[ResampleConfirmationRecord] = None
    resample_submitted_for_inspection_at: Optional[datetime] = None
    action_records: List[ResampleActionRecord] = Field(default_factory=list)
    rejection_reason: Optional[str] = None
    completion_remark: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(from_attributes=True)


class ResampleAcceptSubmit(BaseModel):
    operator: str
    remark: Optional[str] = None


class ResampleRejectSubmit(BaseModel):
    operator: str
    reason: str


class ResampleCompleteSubmit(BaseModel):
    operator: str
    remark: Optional[str] = None


class ResampleProofingSubmit(BaseModel):
    dye_vat_batch: str
    proofing_process: str
    operator: str


class ResampleInspectionSubmit(BaseModel):
    color_comparison_result: str
    color_difference_value: Optional[float] = None
    inspector: str
    conclusion: str


class ResampleReworkSubmit(BaseModel):
    rework_action: str
    reason: str
    operator: str


class ResampleConfirmationSubmit(BaseModel):
    result: str
    confirmer: str


class ResampleFilterParams(BaseModel):
    customer_code: Optional[str] = None
    fabric_type: Optional[str] = None
    responsible_team: Optional[str] = None
    priority: Optional[ResamplePriority] = None
    status: Optional[ResampleStatus] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    skip: int = 0
    limit: int = 100


class ResampleStatusSummary(BaseModel):
    total_count: int = 0
    pending_count: int = 0
    processing_count: int = 0
    completed_count: int = 0
    rejected_count: int = 0


class ResampleDimensionStats(BaseModel):
    dimension_key: str
    total_count: int = 0
    pending_count: int = 0
    processing_count: int = 0
    completed_count: int = 0
    rejected_count: int = 0


class ResampleDashboardOverview(BaseModel):
    status_summary: ResampleStatusSummary
    customer_stats: List[ResampleDimensionStats]
    team_stats: List[ResampleDimensionStats]
    priority_stats: List[ResampleDimensionStats]
