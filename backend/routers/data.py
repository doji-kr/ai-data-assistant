"""데이터 CRUD + 요약 + 통계/CSV 내보내기."""
from __future__ import annotations

import io
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..models import DataPoint, DataPointIn
from ..summary import compute_summary

router = APIRouter(prefix="/api/data", tags=["data"])


def _store(req: Request):
    return req.app.state.store


@router.get("", response_model=list[DataPoint])
def list_data(req: Request):
    return _store(req).list_data()


@router.post("", response_model=DataPoint, status_code=201)
def add_data(body: DataPointIn, req: Request):
    return _store(req).add_data(body.model_dump())


@router.get("/summary")
def get_summary(req: Request):
    return compute_summary(_store(req).list_data())


@router.get("/export.csv")
def export_csv(req: Request):
    buf = io.StringIO()
    buf.write("date,value,memo\n")
    for r in _store(req).list_data():
        memo = (r.get("memo") or "").replace('"', '""')
        buf.write(f'{r["date"]},{r["value"]},"{memo}"\n')
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=data.csv"})


@router.put("/{item_id}", response_model=DataPoint)
def update_data(item_id: str, body: DataPointIn, req: Request):
    row = _store(req).update_data(item_id, body.model_dump())
    if row is None:
        raise HTTPException(404, "해당 id 의 데이터가 없습니다")
    return row


@router.delete("/{item_id}", status_code=204)
def delete_data(item_id: str, req: Request):
    if not _store(req).delete_data(item_id):
        raise HTTPException(404, "해당 id 의 데이터가 없습니다")
