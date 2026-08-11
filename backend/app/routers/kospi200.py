from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import Optional
from app.database import get_db
import json
from app.models import Kospi200Stock, Kospi200DailyData, NightFuturesDailyData, KospiPrediction, MacroIndicatorDailyData

router = APIRouter(prefix="/api/kospi200", tags=["kospi200"])

@router.get("/macro")
def get_macro_indicators(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    query = db.query(MacroIndicatorDailyData)

    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(MacroIndicatorDailyData.trade_date >= sd)
        except ValueError:
            pass

    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(MacroIndicatorDailyData.trade_date <= ed)
        except ValueError:
            pass

    records = query.order_by(MacroIndicatorDailyData.trade_date.desc()).all()

    res_list = []
    for r in records:
        news_titles = []
        if r.news_headlines:
            try:
                news_titles = json.loads(r.news_headlines)
            except Exception:
                news_titles = [r.news_headlines]
        res_list.append({
            "id": r.id,
            "trade_date": r.trade_date.strftime("%Y-%m-%d"),
            "nasdaq_close": r.nasdaq_close,
            "nasdaq_change_rate": r.nasdaq_change_rate,
            "usd_krw": r.usd_krw,
            "sox_change_rate": r.sox_change_rate,
            "us10y_yield": r.us10y_yield,
            "wti_oil": r.wti_oil,
            "kospi_close": getattr(r, 'kospi_close', 0.0),
            "kospi_change_rate": getattr(r, 'kospi_change_rate', 0.0),
            "kosdaq_close": getattr(r, 'kosdaq_close', 0.0),
            "kosdaq_change_rate": getattr(r, 'kosdaq_change_rate', 0.0),
            "kospi200_close": getattr(r, 'kospi200_close', 0.0),
            "kospi200_change_rate": getattr(r, 'kospi200_change_rate', 0.0),
            "kospi200_futures_close": getattr(r, 'kospi200_futures_close', 0.0),
            "kospi200_futures_change_rate": getattr(r, 'kospi200_futures_change_rate', 0.0),
            "kosdaq150_close": getattr(r, 'kosdaq150_close', 0.0),
            "kosdaq150_change_rate": getattr(r, 'kosdaq150_change_rate', 0.0),
            "valueup_close": getattr(r, 'valueup_close', 0.0),
            "valueup_change_rate": getattr(r, 'valueup_change_rate', 0.0),
            "news_headlines": news_titles,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None
        })

    return res_list


@router.get("/predictions")
def get_kospi_predictions(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    from app.services.kospi200_daemon import evaluate_prediction_accuracy
    query = db.query(KospiPrediction)

    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(KospiPrediction.predict_date >= sd)
        except ValueError:
            pass

    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(KospiPrediction.predict_date <= ed)
        except ValueError:
            pass

    records = query.order_by(KospiPrediction.predict_date.desc()).all()

    # Attempt automatic accuracy evaluation for unevaluated prediction records
    for r in records:
        if r.is_accurate is None:
            evaluate_prediction_accuracy(db, r.predict_date)

    records = query.order_by(KospiPrediction.predict_date.desc()).all()

    evaluated_records = [r for r in records if r.is_accurate is not None]
    total_evaluated = len(evaluated_records)
    accurate_count = len([r for r in evaluated_records if r.is_accurate])
    accuracy_rate = round((accurate_count / total_evaluated * 100), 1) if total_evaluated > 0 else 0.0

    return {
        "metrics": {
            "total_predictions": len(records),
            "total_evaluated": total_evaluated,
            "accurate_count": accurate_count,
            "accuracy_rate": accuracy_rate
        },
        "predictions": [
            {
                "id": r.id,
                "predict_date": r.predict_date.strftime("%Y-%m-%d"),
                "gap_direction": r.gap_direction,
                "predicted_change_rate": r.predicted_change_rate,
                "prediction_text": r.prediction_text,
                "actual_gap_direction": r.actual_gap_direction,
                "actual_change_rate": f"{'+' if r.actual_change_rate and r.actual_change_rate > 0 else ''}{r.actual_change_rate:.2f}%" if r.actual_change_rate is not None else None,
                "is_accurate": r.is_accurate,
                "error_margin": f"{r.error_margin:.2f}%p" if r.error_margin is not None else None,
                "evaluated_at": r.evaluated_at.strftime("%Y-%m-%d %H:%M:%S") if r.evaluated_at else None,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None
            }
            for r in records
        ]
    }

@router.post("/predictions/run")
def run_kospi_prediction_now(db: Session = Depends(get_db)):
    from app.services.kospi200_daemon import fetch_and_save_macro_indicators, generate_and_save_kospi_prediction, evaluate_prediction_accuracy
    fetch_and_save_macro_indicators(db)
    text = generate_and_save_kospi_prediction(db)
    evaluate_prediction_accuracy(db)
    return {"status": "success", "prediction_text": text}

@router.post("/predictions/evaluate")
def evaluate_predictions_now(db: Session = Depends(get_db)):
    from app.services.kospi200_daemon import evaluate_prediction_accuracy
    pred = evaluate_prediction_accuracy(db)
    return {"status": "success", "evaluated": True if pred else False}




@router.get("/night-futures")
def get_night_futures(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    query = db.query(NightFuturesDailyData)

    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(NightFuturesDailyData.trade_date >= sd)
        except ValueError:
            pass

    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(NightFuturesDailyData.trade_date <= ed)
        except ValueError:
            pass

    records = query.order_by(NightFuturesDailyData.trade_date.desc()).all()

    return [
        {
            "id": r.id,
            "trade_date": r.trade_date.strftime("%Y-%m-%d"),
            "close_price": r.close_price,
            "change_price": r.change_price,
            "change_rate": r.change_rate,
            "volume": r.volume,
            "foreign_buy_net_contracts": r.foreign_buy_net_contracts,
            "institution_buy_net_contracts": r.institution_buy_net_contracts,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None
        }
        for r in records
    ]

@router.get("/stocks")
def get_kospi200_stocks(
    use_yn: Optional[str] = Query("Y", description="Y or N"),
    db: Session = Depends(get_db)
):
    query = db.query(Kospi200Stock)
    if use_yn:
        query = query.filter(Kospi200Stock.use_yn == use_yn)

    stocks = query.order_by(Kospi200Stock.ticker.asc()).all()
    return [
        {
            "ticker": s.ticker,
            "name": s.name,
            "sector": s.sector,
            "weight": s.weight,
            "use_yn": s.use_yn,
            "updated_at": s.updated_at.strftime("%Y-%m-%d %H:%M:%S") if s.updated_at else None
        }
        for s in stocks
    ]

@router.get("/daily")
def get_kospi200_daily(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    keyword: Optional[str] = Query(None, description="Stock name or ticker"),
    limit: int = Query(300, ge=1, le=2000),
    db: Session = Depends(get_db)
):
    query = db.query(Kospi200DailyData, Kospi200Stock.name).join(
        Kospi200Stock, Kospi200DailyData.ticker == Kospi200Stock.ticker
    )

    if start_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(Kospi200DailyData.trade_date >= sd)
        except ValueError:
            pass

    if end_date:
        try:
            ed = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(Kospi200DailyData.trade_date <= ed)
        except ValueError:
            pass

    if keyword:
        kw = f"%{keyword.strip()}%"
        query = query.filter(
            (Kospi200Stock.name.like(kw)) | (Kospi200DailyData.ticker.like(kw))
        )

    records = query.order_by(Kospi200DailyData.trade_date.desc(), Kospi200DailyData.foreign_buy_net_amount.desc()).limit(limit).all()

    return [
        {
            "id": r.Kospi200DailyData.id,
            "trade_date": r.Kospi200DailyData.trade_date.strftime("%Y-%m-%d"),
            "ticker": r.Kospi200DailyData.ticker,
            "name": r.name,
            "close_price": r.Kospi200DailyData.close_price,
            "market_cap": r.Kospi200DailyData.market_cap,
            "foreign_buy_net_amount": r.Kospi200DailyData.foreign_buy_net_amount,
            "foreign_buy_net_volume": r.Kospi200DailyData.foreign_buy_net_volume,
            "foreign_holding_ratio": r.Kospi200DailyData.foreign_holding_ratio,
            "institution_buy_net_amount": r.Kospi200DailyData.institution_buy_net_amount,
            "created_at": r.Kospi200DailyData.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.Kospi200DailyData.created_at else None
        }
        for r in records
    ]
