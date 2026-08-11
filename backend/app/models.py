from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, BigInteger, Date, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone, timedelta
from app.database import Base

KST = timezone(timedelta(hours=9))

def get_kst_now():
    return datetime.now(KST).replace(tzinfo=None)

class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False) # e.g. 매일경제TV, 서울경제TV, 한국경제TV
    identifier = Column(String(100), unique=True, index=True, nullable=False) # mkeconomy_tv, seouleconomytv, hkwowtv
    handle = Column(String(100), nullable=False) # MKeconomy_TV, SeoulEconomyTV, hkwowtv
    url = Column(String(255), nullable=False) # https://www.youtube.com/@MKeconomy_TV/live
    status = Column(String(20), default="on") # on/off
    created_at = Column(DateTime, default=get_kst_now)
    updated_at = Column(DateTime, default=get_kst_now, onupdate=get_kst_now)

    subtitles = relationship("SubtitleFile", back_populates="channel", cascade="all, delete-orphan")
    summaries = relationship("Summary", back_populates="channel", cascade="all, delete-orphan")

class SubtitleFile(Base):
    __tablename__ = "subtitle_files"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    channel_identifier = Column(String(100), index=True, nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)
    window_label = Column(String(100), nullable=False) # e.g., 2026-08-04 20:00~21:00
    transcript_text = Column(Text, nullable=False)
    collected_at = Column(DateTime, default=get_kst_now)

    channel = relationship("Channel", back_populates="subtitles")
    summaries = relationship("Summary", back_populates="subtitle_file", cascade="all, delete-orphan")

class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    subtitle_file_id = Column(Integer, ForeignKey("subtitle_files.id", ondelete="CASCADE"), nullable=True)
    channel_identifier = Column(String(100), index=True, nullable=False)
    window_label = Column(String(100), nullable=False)
    summary_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=get_kst_now)

    channel = relationship("Channel", back_populates="summaries")
    subtitle_file = relationship("SubtitleFile", back_populates="summaries")

class SubtitleBuffer(Base):
    __tablename__ = "subtitle_buffers"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    channel_identifier = Column(String(100), index=True, nullable=False)
    window_label = Column(String(100), nullable=False) # e.g. 2026-08-05 01:00~02:00
    chunk_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=get_kst_now)

class Kospi200Stock(Base):
    __tablename__ = "kospi200_stocks"

    ticker = Column(String(10), primary_key=True, index=True) # e.g. "005930"
    name = Column(String(100), nullable=False) # e.g. "삼성전자"
    sector = Column(String(100), nullable=True) # e.g. "전기전자"
    weight = Column(Float, nullable=True) # KOSPI 200 weight %
    use_yn = Column(String(1), nullable=False, default="Y") # "Y" / "N" (Active/Inactive)
    created_at = Column(DateTime, default=get_kst_now)
    updated_at = Column(DateTime, default=get_kst_now, onupdate=get_kst_now)

class Kospi200DailyData(Base):
    __tablename__ = "kospi200_daily_data"

    id = Column(Integer, primary_key=True, index=True)
    trade_date = Column(Date, index=True, nullable=False)
    ticker = Column(String(10), ForeignKey("kospi200_stocks.ticker", ondelete="CASCADE"), index=True, nullable=False)
    close_price = Column(BigInteger, nullable=False, default=0)
    market_cap = Column(BigInteger, nullable=False, default=0)
    foreign_buy_net_amount = Column(BigInteger, nullable=False, default=0) # KRW
    foreign_buy_net_volume = Column(BigInteger, nullable=False, default=0) # Shares
    foreign_holding_ratio = Column(Float, nullable=False, default=0.0) # %
    institution_buy_net_amount = Column(BigInteger, nullable=False, default=0) # KRW
    created_at = Column(DateTime, default=get_kst_now)

    __table_args__ = (
        UniqueConstraint("trade_date", "ticker", name="uix_kospi200_daily_date_ticker"),
    )

class NightFuturesDailyData(Base):
    __tablename__ = "night_futures_daily_data"

    id = Column(Integer, primary_key=True, index=True)
    trade_date = Column(Date, unique=True, index=True, nullable=False)
    close_price = Column(Float, nullable=False, default=0.0) # Index Points
    change_price = Column(Float, nullable=False, default=0.0) # +/- Points
    change_rate = Column(Float, nullable=False, default=0.0) # %
    volume = Column(BigInteger, nullable=False, default=0) # Contracts
    foreign_buy_net_contracts = Column(BigInteger, nullable=True, default=0) # Contracts
    institution_buy_net_contracts = Column(BigInteger, nullable=True, default=0) # Contracts
    created_at = Column(DateTime, default=get_kst_now)

class KospiPrediction(Base):
    __tablename__ = "kospi_predictions"

    id = Column(Integer, primary_key=True, index=True)
    predict_date = Column(Date, unique=True, index=True, nullable=False) # e.g. 2026-08-11
    gap_direction = Column(String(50), nullable=False, default="보합") # "갭상승", "보합", "갭하락"
    predicted_change_rate = Column(String(100), nullable=True) # e.g. "+0.32%"
    prediction_text = Column(Text, nullable=False) # Full Markdown AI Opening Briefing

    # Accuracy & Backtesting verification fields
    actual_gap_direction = Column(String(50), nullable=True) # "갭상승", "보합", "갭하락"
    actual_change_rate = Column(Float, nullable=True) # Actual KOSPI 09:00 Open Gap Rate e.g. +0.25 (%)
    is_accurate = Column(Boolean, nullable=True) # True / False / None (pending)
    error_margin = Column(Float, nullable=True) # Absolute error margin e.g. 0.07 (%p)
    evaluated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=get_kst_now)


class MacroIndicatorDailyData(Base):
    __tablename__ = "macro_indicator_daily_data"

    id = Column(Integer, primary_key=True, index=True)
    trade_date = Column(Date, unique=True, index=True, nullable=False)
    nasdaq_close = Column(Float, nullable=False, default=0.0)
    nasdaq_change_rate = Column(Float, nullable=False, default=0.0)
    usd_krw = Column(Float, nullable=False, default=0.0)
    sox_change_rate = Column(Float, nullable=False, default=0.0)
    us10y_yield = Column(Float, nullable=False, default=0.0)
    wti_oil = Column(Float, nullable=False, default=0.0)

    # 6 Domestic Market Indices
    kospi_close = Column(Float, nullable=False, default=0.0)
    kospi_change_rate = Column(Float, nullable=False, default=0.0)
    kosdaq_close = Column(Float, nullable=False, default=0.0)
    kosdaq_change_rate = Column(Float, nullable=False, default=0.0)
    kospi200_close = Column(Float, nullable=False, default=0.0)
    kospi200_change_rate = Column(Float, nullable=False, default=0.0)
    kospi200_futures_close = Column(Float, nullable=False, default=0.0)
    kospi200_futures_change_rate = Column(Float, nullable=False, default=0.0)
    kosdaq150_close = Column(Float, nullable=False, default=0.0)
    kosdaq150_change_rate = Column(Float, nullable=False, default=0.0)
    valueup_close = Column(Float, nullable=False, default=0.0)
    valueup_change_rate = Column(Float, nullable=False, default=0.0)

    news_headlines = Column(Text, nullable=True) # JSON list or newline separated string of news titles
    created_at = Column(DateTime, default=get_kst_now)




