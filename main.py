import json
from datetime import date
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from models import (
    ColorCard, ColorCardCreate, CardStatus, FilterParams, DateFieldType,
    ProofingSubmit, InspectionSubmit, ReworkSubmit,
    ConfirmationSubmit, DiscardSubmit, Token, User,
    HighReworkBatchStats, PendingInspectionStats, ConfirmationCycleStats,
    DashboardFilterParams, DashboardOverviewResponse, DashboardDetailResponse,
    ResampleApplication, ResampleApplicationCreate, ResampleStatus, ResamplePriority,
    ResampleAcceptSubmit, ResampleRejectSubmit, ResampleCompleteSubmit,
    ResampleFilterParams, ResampleDashboardOverview,
    ResampleProofingSubmit, ResampleInspectionSubmit,
    ResampleReworkSubmit, ResampleConfirmationSubmit
)
from auth import authenticate_user, create_token_for_user, get_current_user
from storage import storage

app = FastAPI(
    title="布料染样管理系统API",
    description="管理布料染样、色卡确认和返调记录的后端接口",
    version="1.0.0"
)


@app.get("/")
async def root():
    return {"message": "布料染样管理系统API", "docs": "/docs"}


@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return create_token_for_user(user.username)


@app.post("/cards", response_model=ColorCard)
async def create_color_card(
    card_create: ColorCardCreate,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.create_card(card_create)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/cards", response_model=dict)
async def list_color_cards(
    customer_code: Optional[str] = None,
    fabric_type: Optional[str] = None,
    dye_vat_batch: Optional[str] = None,
    color_card_version: Optional[str] = None,
    status: Optional[CardStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    inspection_conclusion: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    filters = FilterParams(
        customer_code=customer_code,
        fabric_type=fabric_type,
        dye_vat_batch=dye_vat_batch,
        color_card_version=color_card_version,
        status=status,
        start_date=start_date,
        end_date=end_date,
        inspection_conclusion=inspection_conclusion,
        skip=skip,
        limit=limit
    )
    cards, total = storage.list_cards(filters)
    return {"items": cards, "total": total, "skip": skip, "limit": limit}


@app.get("/cards/{card_id}", response_model=ColorCard)
async def get_color_card(card_id: str):
    card = storage.get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail=f"色卡 {card_id} 不存在")
    return card


@app.put("/cards/{card_id}/proofing/start", response_model=ColorCard)
async def start_proofing(
    card_id: str,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.start_proofing(card_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/cards/{card_id}/proofing/complete", response_model=ColorCard)
async def complete_proofing(
    card_id: str,
    submit: ProofingSubmit,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.complete_proofing(
            card_id, submit.dye_vat_batch, submit.proofing_process
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/cards/{card_id}/inspection", response_model=ColorCard)
async def submit_inspection(
    card_id: str,
    submit: InspectionSubmit,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.add_inspection(
            card_id, submit.color_comparison_result,
            submit.color_difference_value, submit.inspector, submit.conclusion
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/cards/{card_id}/rework", response_model=ColorCard)
async def submit_rework(
    card_id: str,
    submit: ReworkSubmit,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.add_rework(
            card_id, submit.rework_action, submit.reason, submit.operator
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/cards/{card_id}/confirm", response_model=ColorCard)
async def confirm_card(
    card_id: str,
    submit: ConfirmationSubmit,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.confirm_card(
            card_id, submit.result, submit.confirmer
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/cards/{card_id}/discard", response_model=ColorCard)
async def discard_card(
    card_id: str,
    submit: DiscardSubmit,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.discard_card(card_id, submit.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/cards/{card_id}/risks/{alert_id}/resolve", response_model=ColorCard)
async def resolve_risk_alert(
    card_id: str,
    alert_id: str,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.resolve_risk_alert(card_id, alert_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/stats/high-rework-batches", response_model=List[HighReworkBatchStats])
async def get_high_rework_batches():
    return storage.get_high_rework_batches()


@app.get("/stats/pending-inspection", response_model=PendingInspectionStats)
async def get_pending_inspection_stats():
    return storage.get_pending_inspection_stats()


@app.get("/stats/confirmation-cycle", response_model=List[ConfirmationCycleStats])
async def get_confirmation_cycle_stats():
    return storage.get_confirmation_cycle_stats()


@app.get("/dashboard/overview", response_model=DashboardOverviewResponse)
async def get_dashboard_overview(
    customer_code: Optional[str] = Query(None, description="客户编码"),
    fabric_type: Optional[str] = Query(None, description="面料类型"),
    responsible_team: Optional[str] = Query(None, description="负责人小组"),
    status: Optional[CardStatus] = Query(None, description="当前状态"),
    date_field: DateFieldType = Query(DateFieldType.CREATED_AT, description="时间范围统计依据"),
    start_date: Optional[date] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user)
):
    try:
        DashboardFilterParams.validate_date_range(start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    filters = DashboardFilterParams(
        customer_code=customer_code,
        fabric_type=fabric_type,
        responsible_team=responsible_team,
        status=status,
        date_field=date_field,
        start_date=start_date,
        end_date=end_date
    )
    return storage.get_dashboard_overview(filters)


@app.get("/dashboard/detail", response_model=DashboardDetailResponse)
async def get_dashboard_detail(
    customer_code: Optional[str] = Query(None, description="客户编码"),
    fabric_type: Optional[str] = Query(None, description="面料类型"),
    responsible_team: Optional[str] = Query(None, description="负责人小组"),
    status: Optional[CardStatus] = Query(None, description="当前状态"),
    date_field: DateFieldType = Query(DateFieldType.CREATED_AT, description="时间范围统计依据"),
    start_date: Optional[date] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回的最大记录数"),
    current_user: User = Depends(get_current_user)
):
    try:
        DashboardFilterParams.validate_date_range(start_date, end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    filters = DashboardFilterParams(
        customer_code=customer_code,
        fabric_type=fabric_type,
        responsible_team=responsible_team,
        status=status,
        date_field=date_field,
        start_date=start_date,
        end_date=end_date
    )
    return storage.get_dashboard_detail(filters, skip=skip, limit=limit)


@app.get("/risks/color-difference-cluster")
async def detect_color_difference_cluster():
    return {"risks": storage.detect_color_difference_cluster()}


@app.get("/risks/team-high-rework-rate")
async def detect_team_high_rework_rate():
    return {"risks": storage.detect_team_high_rework_rate()}


@app.get("/risks/inspection-overdue")
async def detect_inspection_overdue():
    return {"risks": storage.detect_inspection_overdue()}


@app.get("/risks/detect-all")
async def detect_all_risks():
    color_diff_risks = storage.detect_color_difference_cluster()
    team_risks = storage.detect_team_high_rework_rate()
    overdue_risks = storage.detect_inspection_overdue()
    return {
        "color_difference_cluster_risks": color_diff_risks,
        "team_high_rework_rate_risks": team_risks,
        "inspection_overdue_risks": overdue_risks
    }


@app.post("/resample", response_model=ResampleApplication)
async def create_resample_application(
    app_create: ResampleApplicationCreate,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.create_resample_application(app_create)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/resample", response_model=dict)
async def list_resample_applications(
    customer_code: Optional[str] = None,
    fabric_type: Optional[str] = None,
    responsible_team: Optional[str] = None,
    priority: Optional[ResamplePriority] = None,
    status: Optional[ResampleStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user)
):
    filters = ResampleFilterParams(
        customer_code=customer_code,
        fabric_type=fabric_type,
        responsible_team=responsible_team,
        priority=priority,
        status=status,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit
    )
    apps, total = storage.list_resample_applications(filters)
    return {"items": apps, "total": total, "skip": skip, "limit": limit}


@app.get("/resample/{app_id}", response_model=ResampleApplication)
async def get_resample_application(
    app_id: str,
    current_user: User = Depends(get_current_user)
):
    app = storage.get_resample_application(app_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"复样申请 {app_id} 不存在")
    return app


@app.put("/resample/{app_id}/accept", response_model=ResampleApplication)
async def accept_resample_application(
    app_id: str,
    submit: ResampleAcceptSubmit,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.accept_resample_application(app_id, submit.operator, submit.remark)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/resample/{app_id}/reject", response_model=ResampleApplication)
async def reject_resample_application(
    app_id: str,
    submit: ResampleRejectSubmit,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.reject_resample_application(app_id, submit.operator, submit.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/resample/{app_id}/complete", response_model=ResampleApplication)
async def complete_resample_application(
    app_id: str,
    submit: ResampleCompleteSubmit,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.complete_resample_application(app_id, submit.operator, submit.remark)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/resample/{app_id}/follow-up", response_model=ResampleApplication)
async def add_resample_follow_up(
    app_id: str,
    submit: ResampleAcceptSubmit,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.add_resample_follow_up(app_id, submit.operator, submit.remark or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/resample/{app_id}/proofing/start", response_model=ResampleApplication)
async def start_resample_proofing(
    app_id: str,
    submit: ResampleAcceptSubmit,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.start_resample_proofing(app_id, submit.operator)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/resample/{app_id}/proofing/complete", response_model=ResampleApplication)
async def complete_resample_proofing(
    app_id: str,
    submit: ResampleProofingSubmit,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.complete_resample_proofing(app_id, submit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/resample/{app_id}/inspection", response_model=ResampleApplication)
async def submit_resample_inspection(
    app_id: str,
    submit: ResampleInspectionSubmit,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.add_resample_inspection(app_id, submit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/resample/{app_id}/rework", response_model=ResampleApplication)
async def submit_resample_rework(
    app_id: str,
    submit: ResampleReworkSubmit,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.add_resample_rework(app_id, submit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/resample/{app_id}/confirm", response_model=ResampleApplication)
async def confirm_resample(
    app_id: str,
    submit: ResampleConfirmationSubmit,
    current_user: User = Depends(get_current_user)
):
    try:
        return storage.confirm_resample(app_id, submit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/dashboard/resample/overview", response_model=ResampleDashboardOverview)
async def get_resample_dashboard_overview(
    customer_code: Optional[str] = Query(None, description="客户编码"),
    fabric_type: Optional[str] = Query(None, description="面料类型"),
    responsible_team: Optional[str] = Query(None, description="负责人小组"),
    priority: Optional[ResamplePriority] = Query(None, description="优先级"),
    status: Optional[ResampleStatus] = Query(None, description="申请状态"),
    start_date: Optional[date] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user)
):
    filters = ResampleFilterParams(
        customer_code=customer_code,
        fabric_type=fabric_type,
        responsible_team=responsible_team,
        priority=priority,
        status=status,
        start_date=start_date,
        end_date=end_date
    )
    return storage.get_resample_dashboard_overview(filters)


@app.get("/export/json")
async def export_json(current_user: User = Depends(get_current_user)):
    data = storage.get_full_export_data()
    return JSONResponse(
        content=data,
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=color_cards_and_resamples.json"
        }
    )


@app.get("/export/download")
async def download_json_file(current_user: User = Depends(get_current_user)):
    data = storage.get_full_export_data()
    filename = "color_cards_full_export.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    return FileResponse(
        filename,
        media_type="application/json",
        filename=filename
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8121)
