import os
import sys
import logging
import argparse
import requests
import json
import re
import asyncio
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import FinanceDataReader as fdr
import pandas as pd

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.database import SessionLocal, engine, Base
import json
import asyncio
from google.antigravity import Agent, LocalAgentConfig
from app.config import settings
from app.models import (
    Kospi200Stock,
    Kospi200DailyData,
    NightFuturesDailyData,
    KospiPrediction,
    MacroIndicatorDailyData,
    Summary,
    get_kst_now
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Kospi200Daemon] %(message)s"
)
logger = logging.getLogger("stockbs_kospi200_collector")


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch_top_200_kospi_stocks() -> list[tuple[str, str, int]]:
    """Fetch top 200 KOSPI stocks by market capitalization using FinanceDataReader."""
    logger.info("Fetching KOSPI stock listing via FinanceDataReader...")
    try:
        df = fdr.StockListing("KOSPI")
        if df.empty:
            logger.error("FinanceDataReader returned empty KOSPI listing.")
            return []
        
        # Sort by Marcap descending
        df_sorted = df.sort_values(by="Marcap", ascending=False).head(200)
        result = []
        for _, row in df_sorted.iterrows():
            ticker = str(row["Code"]).zfill(6)
            name = str(row["Name"])
            marcap = int(row["Marcap"]) if "Marcap" in row and pd.notna(row["Marcap"]) else 0
            result.append((ticker, name, marcap))
        
        logger.info(f"Successfully retrieved top {len(result)} KOSPI stocks.")
        return result
    except Exception as e:
        logger.error(f"Error fetching KOSPI stock listing: {e}", exc_info=True)
        return []


def update_kospi200_master(db, stock_list: list[tuple[str, str, int]]) -> set[str]:
    """Update kospi200_stocks table with active status (use_yn='Y' for top 200, 'N' for removed)."""
    current_tickers = {ticker for ticker, _, _ in stock_list}
    
    # 1. Query existing stock records
    existing_stocks = db.query(Kospi200Stock).all()
    existing_map = {s.ticker: s for s in existing_stocks}

    # 2. Upsert current KOSPI 200 tickers
    for ticker, name, marcap in stock_list:
        if ticker in existing_map:
            stock_obj = existing_map[ticker]
            stock_obj.name = name
            stock_obj.use_yn = "Y"
        else:
            stock_obj = Kospi200Stock(
                ticker=ticker,
                name=name,
                use_yn="Y"
            )
            db.add(stock_obj)

    # 3. Mark removed tickers as use_yn = 'N'
    for ticker, stock_obj in existing_map.items():
        if ticker not in current_tickers:
            stock_obj.use_yn = "N"

    db.commit()
    logger.info(f"Updated kospi200_stocks master. Active count: {len(current_tickers)}, Total in DB: {len(db.query(Kospi200Stock).all())}.")
    return current_tickers


def fetch_stock_trend_naver(ticker: str) -> dict | None:
    """Fetch daily trend info (foreign ratio, foreigner net buy quant, inst net buy quant, close price) via Naver API."""
    url = f"https://m.stock.naver.com/api/stock/{ticker}/trend?page=1&pageSize=5"
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0] # Latest day trend
    except Exception as e:
        logger.debug(f"Naver trend API fetch error for {ticker}: {e}")
    return None


def parse_clean_int(val) -> int:
    if not val:
        return 0
    clean_str = str(val).replace(",", "").replace("+", "").strip()
    try:
        return int(clean_str)
    except ValueError:
        return 0


def parse_clean_float(val) -> float:
    if not val:
        return 0.0
    clean_str = str(val).replace("%", "").replace(",", "").replace("+", "").strip()
    try:
        return float(clean_str)
    except ValueError:
        return 0.0


def fetch_and_save_kospi200_daily(db, stock_list: list[tuple[str, str, int]]):
    """Fetch & save daily KOSPI 200 prices, foreign holding ratio, and investor net buying."""
    logger.info(f"Collecting daily trend data for {len(stock_list)} KOSPI 200 stocks...")
    saved_count = 0

    for ticker, name, marcap in stock_list:
        trend = fetch_stock_trend_naver(ticker)
        if not trend:
            continue

        bizdate_str = trend.get("bizdate") # e.g. "20260810"
        if not bizdate_str:
            continue

        try:
            trade_date = datetime.strptime(bizdate_str, "%Y%m%d").date()
            close_price = parse_clean_int(trend.get("closePrice"))
            foreign_ratio = parse_clean_float(trend.get("foreignerHoldRatio"))
            foreign_buy_vol = parse_clean_int(trend.get("foreignerPureBuyQuant"))
            inst_buy_vol = parse_clean_int(trend.get("organPureBuyQuant"))
            foreign_buy_amount = foreign_buy_vol * close_price
            inst_buy_amount = inst_buy_vol * close_price

            # Upsert into kospi200_daily_data
            existing = db.query(Kospi200DailyData).filter(
                Kospi200DailyData.trade_date == trade_date,
                Kospi200DailyData.ticker == ticker
            ).first()

            if existing:
                existing.close_price = close_price
                existing.market_cap = marcap
                existing.foreign_buy_net_amount = foreign_buy_amount
                existing.foreign_buy_net_volume = foreign_buy_vol
                existing.foreign_holding_ratio = foreign_ratio
                existing.institution_buy_net_amount = inst_buy_amount
            else:
                rec = Kospi200DailyData(
                    trade_date=trade_date,
                    ticker=ticker,
                    close_price=close_price,
                    market_cap=marcap,
                    foreign_buy_net_amount=foreign_buy_amount,
                    foreign_buy_net_volume=foreign_buy_vol,
                    foreign_holding_ratio=foreign_ratio,
                    institution_buy_net_amount=inst_buy_amount
                )
                db.add(rec)
            saved_count += 1
        except Exception as err:
            logger.warning(f"Failed to parse daily record for ticker {ticker}: {err}")

    db.commit()
    logger.info(f"Successfully saved {saved_count} daily KOSPI 200 stock records.")


def fetch_and_save_night_futures(db):
    """Fetch & save Eurex KOSPI 200 Futures daily summary using FinanceDataReader."""
    logger.info("Collecting Night Futures (KOSPI 200 Futures) daily data...")
    try:
        # KS200 index daily data via FinanceDataReader
        df_ks200 = fdr.DataReader("KS200")
        if not df_ks200.empty:
            latest_dt = df_ks200.index[-1]
            trade_date = latest_dt.date()
            latest_row = df_ks200.iloc[-1]

            close_p = float(latest_row["Close"]) if "Close" in latest_row else 0.0
            change_p = float(latest_row["Change"]) if "Change" in latest_row else 0.0
            vol = int(latest_row["Volume"]) if "Volume" in latest_row else 0
            change_r = round(change_p * 100.0, 2)

            existing = db.query(NightFuturesDailyData).filter(
                NightFuturesDailyData.trade_date == trade_date
            ).first()

            if existing:
                existing.close_price = close_p
                existing.change_price = change_p
                existing.change_rate = change_r
                existing.volume = vol
            else:
                rec = NightFuturesDailyData(
                    trade_date=trade_date,
                    close_price=close_p,
                    change_price=change_p,
                    change_rate=change_r,
                    volume=vol,
                    foreign_buy_net_contracts=0
                )
                db.add(rec)

            db.commit()
            logger.info(f"Saved Night Futures (KS200) data for {trade_date}: Close={close_p}, Change={change_p}.")
    except Exception as e:
        logger.warning(f"Error fetching Night Futures data: {e}", exc_info=True)


def fetch_and_save_macro_indicators(db):
    """Fetch NASDAQ, USD/KRW, SOXX, US 10Y Yield, WTI Crude Oil, and Breaking News."""
    logger.info("Collecting Global Macro Indicators (NASDAQ, Exchange Rate, SOX, US10Y, WTI, News)...")
    try:
        now_kst = get_kst_now()
        trade_date = now_kst.date()

        # 1. NASDAQ
        nasdaq_close, nasdaq_change = 0.0, 0.0
        try:
            df_ixic = fdr.DataReader("IXIC")
            if not df_ixic.empty:
                r = df_ixic.iloc[-1]
                nasdaq_close = float(r["Close"]) if "Close" in r else 0.0
                nasdaq_change = round(float(r["Change"]) * 100.0, 2) if "Change" in r else 0.0
        except Exception as e:
            logger.warning(f"Failed to fetch NASDAQ: {e}")

        # 2. USD/KRW
        usd_krw_val = 0.0
        try:
            df_fx = fdr.DataReader("USD/KRW")
            if not df_fx.empty:
                r = df_fx.iloc[-1]
                usd_krw_val = round(float(r["Close"]), 2) if "Close" in r else 0.0
        except Exception as e:
            logger.warning(f"Failed to fetch USD/KRW: {e}")

        # 3. SOX (via SOXX ETF)
        sox_change = 0.0
        try:
            df_sox = fdr.DataReader("SOXX")
            if not df_sox.empty:
                r = df_sox.iloc[-1]
                sox_change = round(float(r["Change"]) * 100.0, 2) if "Change" in r else 0.0
        except Exception as e:
            logger.warning(f"Failed to fetch SOXX: {e}")

        # 4. US 10Y Yield
        us10y_val = 0.0
        try:
            df_10y = fdr.DataReader("FRED:DGS10")
            if not df_10y.empty:
                r = df_10y.iloc[-1]
                us10y_val = round(float(r["DGS10"]), 2) if "DGS10" in r else 0.0
        except Exception as e:
            logger.warning(f"Failed to fetch US 10Y Yield: {e}")

        # 5. WTI Oil
        wti_val = 0.0
        try:
            df_wti = fdr.DataReader("CL=F")
            if not df_wti.empty:
                r = df_wti.iloc[-1]
                wti_val = round(float(r["Close"]), 2) if "Close" in r else 0.0
        except Exception as e:
            logger.warning(f"Failed to fetch WTI Oil: {e}")

        # 6. Domestic Market Indices (KOSPI, KOSDAQ, KOSPI200, KOSPI200 Futures, KOSDAQ150, Korea Value-Up)
        domestic_idx = {
            'kospi': (0.0, 0.0), 'kosdaq': (0.0, 0.0), 'kospi200': (0.0, 0.0),
            'kospi200_futures': (0.0, 0.0), 'kosdaq150': (0.0, 0.0), 'valueup': (0.0, 0.0)
        }
        try:
            naver_map = {
                'kospi': ('KOSPI', 'KS11'),
                'kosdaq': ('KOSDAQ', 'KQ11'),
                'kospi200': ('KPI200', 'KS200'),
                'kospi200_futures': ('FUT', None),
                'kosdaq150': ('KQ150', 'KQ11'),
                'valueup': ('KVALUE', None)
            }
            for key, (naver_sym, fdr_sym) in naver_map.items():
                c_val, r_val = 0.0, 0.0
                try:
                    url = f'https://m.stock.naver.com/api/index/{naver_sym}/price?pageSize=2&page=1'
                    res = requests.get(url, headers=HEADERS, timeout=5)
                    if res.ok:
                        items = res.json()
                        if isinstance(items, list) and len(items) >= 2:
                            today_close = float(items[0]['closePrice'].replace(',', ''))
                            prev_close = float(items[1]['closePrice'].replace(',', ''))
                            c_val = today_close
                            r_val = round(((today_close - prev_close) / prev_close) * 100, 2)
                except Exception:
                    pass

                if c_val == 0.0 and fdr_sym:
                    try:
                        df = fdr.DataReader(fdr_sym)
                        if not df.empty:
                            c_val = float(df.iloc[-1]['Close'])
                            r_val = round(float(df.iloc[-1].get('Change', 0)) * 100, 2)
                    except Exception:
                        pass
                domestic_idx[key] = (c_val, r_val)
        except Exception as e:
            logger.warning(f"Failed to fetch domestic indices: {e}")

        # 7. Breaking Market News Headlines
        news_titles = []
        try:
            res = requests.get("https://finance.naver.com/news/mainnews.naver", headers=HEADERS, timeout=5)
            if res.ok:
                res.encoding = "euc-kr"
                soup = BeautifulSoup(res.text, "html.parser")
                titles = [a.text.strip() for a in soup.select(".mainNewsList .articleSubject a") if a.text.strip()]
                news_titles = titles[:5]
        except Exception as e:
            logger.warning(f"Failed to scrape market news headlines: {e}")

        news_text = json.dumps(news_titles, ensure_ascii=False) if news_titles else "[]"

        existing = db.query(MacroIndicatorDailyData).filter(
            MacroIndicatorDailyData.trade_date == trade_date
        ).first()

        if existing:
            existing.nasdaq_close = nasdaq_close
            existing.nasdaq_change_rate = nasdaq_change
            existing.usd_krw = usd_krw_val
            existing.sox_change_rate = sox_change
            existing.us10y_yield = us10y_val
            existing.wti_oil = wti_val

            existing.kospi_close = domestic_idx['kospi'][0]
            existing.kospi_change_rate = domestic_idx['kospi'][1]
            existing.kosdaq_close = domestic_idx['kosdaq'][0]
            existing.kosdaq_change_rate = domestic_idx['kosdaq'][1]
            existing.kospi200_close = domestic_idx['kospi200'][0]
            existing.kospi200_change_rate = domestic_idx['kospi200'][1]
            existing.kospi200_futures_close = domestic_idx['kospi200_futures'][0]
            existing.kospi200_futures_change_rate = domestic_idx['kospi200_futures'][1]
            existing.kosdaq150_close = domestic_idx['kosdaq150'][0]
            existing.kosdaq150_change_rate = domestic_idx['kosdaq150'][1]
            existing.valueup_close = domestic_idx['valueup'][0]
            existing.valueup_change_rate = domestic_idx['valueup'][1]

            existing.news_headlines = news_text
        else:
            rec = MacroIndicatorDailyData(
                trade_date=trade_date,
                nasdaq_close=nasdaq_close,
                nasdaq_change_rate=nasdaq_change,
                usd_krw=usd_krw_val,
                sox_change_rate=sox_change,
                us10y_yield=us10y_val,
                wti_oil=wti_val,
                kospi_close=domestic_idx['kospi'][0],
                kospi_change_rate=domestic_idx['kospi'][1],
                kosdaq_close=domestic_idx['kosdaq'][0],
                kosdaq_change_rate=domestic_idx['kosdaq'][1],
                kospi200_close=domestic_idx['kospi200'][0],
                kospi200_change_rate=domestic_idx['kospi200'][1],
                kospi200_futures_close=domestic_idx['kospi200_futures'][0],
                kospi200_futures_change_rate=domestic_idx['kospi200_futures'][1],
                kosdaq150_close=domestic_idx['kosdaq150'][0],
                kosdaq150_change_rate=domestic_idx['kosdaq150'][1],
                valueup_close=domestic_idx['valueup'][0],
                valueup_change_rate=domestic_idx['valueup'][1],
                news_headlines=news_text
            )
            db.add(rec)

        db.commit()
        logger.info(f"Saved Macro Indicators for {trade_date}: NASDAQ={nasdaq_close}({nasdaq_change}%), USD/KRW={usd_krw_val}, KOSPI={domestic_idx['kospi'][0]}({domestic_idx['kospi'][1]}%), KOSDAQ={domestic_idx['kosdaq'][0]}({domestic_idx['kosdaq'][1]}%).")

    except Exception as e:
        logger.error(f"Error fetching macro indicators: {e}", exc_info=True)


def generate_and_save_kospi_prediction(db) -> str:
    """Generate daily KOSPI opening prediction briefing using Gemini AI (google-antigravity) and save to DB."""
    now_kst = get_kst_now()
    predict_date = now_kst.date()
    logger.info(f"Generating Gemini AI KOSPI opening prediction for {predict_date}...")

    # 1. Fetch latest Night Futures
    latest_nf = db.query(NightFuturesDailyData).order_by(NightFuturesDailyData.trade_date.desc()).first()
    nf_text = "데이터 없음"
    if latest_nf:
        nf_text = f"{latest_nf.close_price} pt (등락률: {latest_nf.change_rate:+}%, 대비: {latest_nf.change_price:+} pt, 거래량: {latest_nf.volume:,} 계약)"

    # 2. Fetch latest Global Macro Indicators & News Headlines
    latest_macro = db.query(MacroIndicatorDailyData).order_by(MacroIndicatorDailyData.trade_date.desc()).first()
    macro_text = "매크로 데이터 없음"
    news_text_formatted = "속보 뉴스 없음"

    if latest_macro:
        macro_text = (
            f"- 나스닥(NASDAQ): {latest_macro.nasdaq_close:,.2f} ({latest_macro.nasdaq_change_rate:+}%)\n"
            f"- 원/달러 환율(USD/KRW): {latest_macro.usd_krw:,.2f}원\n"
            f"- 필라델피아 반도체(SOX): {latest_macro.sox_change_rate:+}%\n"
            f"- 미 국채 10년물 금리: {latest_macro.us10y_yield}%\n"
            f"- WTI 국제 유가: ${latest_macro.wti_oil}/bbl\n"
            f"- 코스피(KOSPI) 전일 종가: {latest_macro.kospi_close:,.2f} ({latest_macro.kospi_change_rate:+}%)\n"
            f"- 코스닥(KOSDAQ) 전일 종가: {latest_macro.kosdaq_close:,.2f} ({latest_macro.kosdaq_change_rate:+}%)\n"
            f"- 코스피 200 전일 종가: {latest_macro.kospi200_close:,.2f} ({latest_macro.kospi200_change_rate:+}%)\n"
            f"- 코스피 200 선물 전일 종가: {latest_macro.kospi200_futures_close:,.2f} ({latest_macro.kospi200_futures_change_rate:+}%)\n"
            f"- 코스닥 150 전일 종가: {latest_macro.kosdaq150_close:,.2f} ({latest_macro.kosdaq150_change_rate:+}%)\n"
            f"- 코리아 밸류업 지수 전일 종가: {latest_macro.valueup_close:,.2f} ({latest_macro.valueup_change_rate:+}%)"
        )

        if latest_macro.news_headlines:
            try:
                titles = json.loads(latest_macro.news_headlines)
                if isinstance(titles, list) and titles:
                    news_text_formatted = "\n".join([f"- {t}" for t in titles])
            except Exception:
                news_text_formatted = latest_macro.news_headlines

    # 3. Fetch latest KOSPI 200 daily stock data (top 5 foreign buy & top 5 sell)
    top_buys = db.query(Kospi200DailyData, Kospi200Stock.name).join(
        Kospi200Stock, Kospi200DailyData.ticker == Kospi200Stock.ticker
    ).order_by(Kospi200DailyData.trade_date.desc(), Kospi200DailyData.foreign_buy_net_amount.desc()).limit(5).all()

    top_sells = db.query(Kospi200DailyData, Kospi200Stock.name).join(
        Kospi200Stock, Kospi200DailyData.ticker == Kospi200Stock.ticker
    ).order_by(Kospi200DailyData.trade_date.desc(), Kospi200DailyData.foreign_buy_net_amount.asc()).limit(5).all()

    buy_items = [f"{r.name}({r.Kospi200DailyData.foreign_buy_net_amount / 100000000:.1f}억원)" for r in top_buys if r.Kospi200DailyData.foreign_buy_net_amount > 0]
    sell_items = [f"{r.name}({r.Kospi200DailyData.foreign_buy_net_amount / 100000000:.1f}억원)" for r in top_sells if r.Kospi200DailyData.foreign_buy_net_amount < 0]

    top_buy_text = ", ".join(buy_items) if buy_items else "특이 수급 없음"
    top_sell_text = ", ".join(sell_items) if sell_items else "특이 수급 없음"

    # 4. Fetch latest TV Broadcast Summaries
    recent_summaries = db.query(Summary).order_by(Summary.id.desc()).limit(3).all()
    summaries_text = "\n".join([f"- [{s.channel_identifier}] {s.summary_text[:300]}" for s in recent_summaries]) if recent_summaries else "방송 요약 데이터 없음"

    prompt = f"""아래 제공된 [새벽 수집 시장 데이터]를 바탕으로, 지시된 [작성 규칙]과 [출력 양식]을 '엄격히 준수'하여 당일 아침 09:00 한국 증시(KOSPI) 개장 향방을 예측하는 [당일 KOSPI 개장 예측 프리장 브리핑]을 작성해 줘.

[작성 규칙]
1. (개장 갭 방향 지정) 첫 머리에 당일 예상되는 개장 형태("갭상승", "보합", "갭하락")와 예상 등락폭 범위(예: "+0.3% ~ +0.5%")를 명확히 판정할 것.
2. (매크로 & 야간선물 원인 분석) 야간 선물(Eurex), 나스닥 등락률, 원/달러 환율, 반도체지수(SOX) 및 미 금리가 국내 증시 개장에 주는 영향을 선행 종합 분석할 것.
3. (수급 & 주도 섹터) 전일 외국인 순매수/순매도 상위 종목, 주요 증시 속보 뉴스 및 TV 방송 패널들의 요약 분석을 연계하여, 당일 장 초반 수급 쏠림이 유력한 주도 섹터 및 관전 포인트를 2~3개 추출할 것.
4. (초간결 개조식 단문) 군더더기 서술 문장을 배제하고 핵심 팩트만 명확한 1줄 개조식 단문(~함, ~임, ~상승, ~유력)으로 작성할 것.

[새벽 수집 시장 데이터]
- 글로벌 매크로 지표:
{macro_text}

- 야간 선물 마감: {nf_text}
- KOSPI 200 전일 외인 순매수 상위: {top_buy_text}
- KOSPI 200 전일 외인 순매도 상위: {top_sell_text}
- 주요 증시 헤드라인 속보 뉴스:
{news_text_formatted}
- TV 방송 주요 요약:
{summaries_text[:1200]}

---

[출력 양식]

## 1. ☀️ 당일 지수 개장 예측
* **[예상 개장 방향]:**
  * 글로벌 매크로(나스닥/환율/반도체지수) 및 야간 선물 연계 분석 1
  * 시초가 예상 등락폭 및 시장 분위기 2

## 2. 🎯 당일 수급 및 주도 섹터 관전 포인트
* **[주도 섹터/종목 1]:**
  * 외국인 수급 연속성 및 뉴스 호재 분석 1
* **[주도 섹터/종목 2]:**
  * 방송 요약 및 이슈 연계 분석 2
"""

    api_key = settings.GEMINI_API_KEY
    prediction_text = ""

    if api_key and api_key != "YOUR_GEMINI_API_KEY":
        try:
            async def _call_gemini():
                config = LocalAgentConfig(
                    model="gemini-3.5-flash",
                    api_key=api_key
                )
                async with Agent(config=config) as agent:
                    response = await agent.chat(prompt)
                    return await response.text()

            prediction_text = asyncio.run(_call_gemini())
        except Exception as e:
            logger.error(f"Gemini API invocation error during KOSPI prediction: {e}")
            prediction_text = f"## 1. ☀️ 당일 지수 개장 예측\n* **[예상 개장 방향]:**\n  * 야간 선물 {nf_text} 반영으로 보합권 출발 예상됨.\n\n## 2. 🎯 당일 수급 관전 포인트\n* **외국인 수급 상위:** {top_buy_text}\n* **외국인 순매도 상위:** {top_sell_text}"
    else:
        prediction_text = f"## 1. ☀️ 당일 지수 개장 예측\n* **[예상 개장 방향]:**\n  * 야간 선물 {nf_text} 반영으로 보합권 출발 예상됨.\n\n## 2. 🎯 당일 수급 관전 포인트\n* **외국인 수급 상위:** {top_buy_text}\n* **외국인 순매도 상위:** {top_sell_text}"

    # Parse gap direction ("갭상승", "보합", "갭하락") and rate
    gap_direction = "보합"
    predicted_rate = "0.0%"

    if "갭상승" in prediction_text:
        gap_direction = "갭상승"
    elif "갭하락" in prediction_text:
        gap_direction = "갭하락"

    # Extract percentage range like (+0.1% ~ +0.3%)
    rate_match = re.search(r"(\+|-)?\d+(\.\d+)?%\s*~\s*(\+|-)?\d+(\.\d+)?%", prediction_text)
    if rate_match:
        predicted_rate = rate_match.group(0)
    else:
        single_match = re.search(r"(\+|-)?\d+(\.\d+)?%", prediction_text)
        if single_match:
            predicted_rate = single_match.group(0)

    # Save into KospiPrediction DB table
    existing_pred = db.query(KospiPrediction).filter(
        KospiPrediction.predict_date == predict_date
    ).first()

    if existing_pred:
        existing_pred.gap_direction = gap_direction
        existing_pred.predicted_change_rate = predicted_rate
        existing_pred.prediction_text = prediction_text
        existing_pred.created_at = get_kst_now()
    else:
        pred_obj = KospiPrediction(
            predict_date=predict_date,
            gap_direction=gap_direction,
            predicted_change_rate=predicted_rate,
            prediction_text=prediction_text
        )
        db.add(pred_obj)


    db.commit()
    logger.info(f"Successfully generated and saved KOSPI prediction for {predict_date} (Direction: {gap_direction}).")

    # Evaluate accuracy immediately if actual open data is available
    evaluate_prediction_accuracy(db, predict_date)

    return prediction_text


def evaluate_prediction_accuracy(db: Session, target_date: date = None):
    """
    Evaluates AI Opening Gap prediction accuracy against actual market open data.
    Calculates actual open gap rate (%), compares gap direction, and updates DB.
    """
    if not target_date:
        target_date = get_kst_now().date()

    prediction = db.query(KospiPrediction).filter(KospiPrediction.predict_date == target_date).first()
    if not prediction:
        logger.info(f"No prediction record found for date {target_date} to evaluate.")
        return None

    try:
        import FinanceDataReader as fdr
        start_search = target_date - timedelta(days=7)
        # Fetch actual market data for KOSPI index (KS11)
        df = fdr.DataReader("KS11", start_search, target_date)
        if df.empty or len(df) < 2:
            df = fdr.DataReader("005930", start_search, target_date)

        if not df.empty and len(df) >= 2:
            prev_close = float(df.iloc[-2]["Close"])
            today_open = float(df.iloc[-1]["Open"])

            if prev_close > 0:
                actual_gap_pct = round(((today_open - prev_close) / prev_close) * 100, 2)

                if actual_gap_pct > 0.3:
                    actual_direction = "갭상승"
                elif actual_gap_pct < -0.3:
                    actual_direction = "갭하락"
                else:
                    actual_direction = "보합"

                pred_dir = prediction.gap_direction
                is_match = (pred_dir == actual_direction)

                error_margin = None
                if prediction.predicted_change_rate:
                    match = re.search(r"([+-]?\d+\.?\d*)", prediction.predicted_change_rate)
                    if match:
                        pred_val = float(match.group(1))
                        error_margin = round(abs(pred_val - actual_gap_pct), 2)

                prediction.actual_gap_direction = actual_direction
                prediction.actual_change_rate = actual_gap_pct
                prediction.is_accurate = is_match
                prediction.error_margin = error_margin
                prediction.evaluated_at = get_kst_now()

                db.commit()
                db.refresh(prediction)
                logger.info(f"Evaluated prediction accuracy for {target_date}: Predicted={pred_dir}, Actual={actual_direction}({actual_gap_pct}%), Accurate={is_match}")
                return prediction
    except Exception as e:
        logger.error(f"Failed to evaluate prediction accuracy for {target_date}: {e}")
        db.rollback()

    return prediction



def run_kospi200_collection_cycle():
    """Main collection cycle executed every morning at 05:30 KST."""
    logger.info("====================================================")
    logger.info(" Starting KOSPI 200 & Night Futures Daily Collector")
    logger.info("====================================================")

    # Ensure missing tables are created
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        stock_list = fetch_top_200_kospi_stocks()
        if stock_list:
            update_kospi200_master(db, stock_list)
            fetch_and_save_kospi200_daily(db, stock_list)
        fetch_and_save_night_futures(db)
        fetch_and_save_macro_indicators(db)
        generate_and_save_kospi_prediction(db)
        logger.info("KOSPI 200 & Night Futures collection cycle finished successfully.")
    except Exception as e:
        logger.error(f"Error during KOSPI 200 collection cycle: {e}", exc_info=True)
    finally:
        db.close()




def main():
    parser = argparse.ArgumentParser(description="StockBS KOSPI 200 Collector Daemon")
    parser.add_argument("--now", action="store_true", help="Run collection cycle immediately and exit")
    args = parser.parse_args()

    if args.now:
        logger.info("Running manual KOSPI 200 collection cycle immediately...")
        run_kospi200_collection_cycle()
        return

    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    # Schedule job every morning at 05:30 KST
    scheduler.add_job(
        run_kospi200_collection_cycle,
        CronTrigger(hour=5, minute=30, timezone="Asia/Seoul"),
        id="run_kospi200_collection_cycle"
    )

    logger.info("KOSPI 200 collector daemon scheduler started. Waiting for 05:30 KST trigger...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping KOSPI 200 collector daemon scheduler.")


if __name__ == "__main__":
    main()
