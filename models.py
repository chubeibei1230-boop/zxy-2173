from enum import Enum
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class CardStatus(str, Enum):
    PENDING_PROOFING = "待打样"
    PROOFING = "打样中"
    PENDING_INSPECTION = "待质检"
    REWORKING = "返调中"
    CONFIRMED = "已确认"
    DISCARDED = "已废弃"


class RiskType(str, Enum):
    REWORK_EXCEED_THRESHOLD = "返调次数超限"
    COLOR_DIFFERENCE_CLUSTER = "染缸批次色差集中"
    INSPECTION_OVERDUE = "质检超期"
    TEAM_HIGH_REWORK_RATE = "小组返调率偏高"


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
