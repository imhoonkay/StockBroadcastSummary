# KOSPI 200 및 야간 선물 일별 수집 시스템 설계서

## 1. 개요 (Overview)
본 문서에서는 **KOSPI 200 구성 종목 / 일별 외국인·기관 수급 데이터**와 **야간 선물(Eurex KOSPI 200 선물) 일별 지수·수급 데이터**를 매일 새벽 별도의 독립 컨테이너 프로세스를 통해 동시 수집하고 관리하기 위한 데이터베이스 설계 및 수집 프로세스 사양을 정의합니다.

---

## 2. 수집 주기 및 시간 설정 (Collection Schedule)

* **수집 주기**: 매일 1회 (주말/공휴일 포함 및 장 휴장일 체크)
* **추천 수집 시간**: **매일 새벽 `05:30 KST`** (`CronTrigger: hour=5, minute=30`)

### 💡 새벽 05:30 수집 선택 근거
1. **야간 선물(Eurex) 최종 마감 시각 반영**:  
   야간 선물 시장은 **새벽 05:00(동절기 06:00)**에 마감되므로, 마감 직후인 **새벽 05:30**에 수집하면 야간 선물의 최종 종가, 등락률, 야간 외인 순매수를 오차 없이 확정 획득할 수 있습니다.
2. **KOSPI 200 주간장 마감 데이터 완전성**:  
   전일 주간장 KRX의 KOSPI 200 외국인/기관 순매수 및 지분 소진율 마감 배치는 저녁 20:00 경 100% 완료되어 있으므로, 새벽 시간대는 가장 안정적인 정적 수집 시점입니다.
3. **장 시작 전 정적 준비 완료**:  
   오전 09:00 정규장 개장 전 데이터를 완비하여 아침 AI 요약 브리핑 및 웹 UI에서 KOSPI 200 현물 팩트 + 야간 선물 예측 지표를 동시에 활용할 수 있습니다.

---

## 3. 데이터베이스 테이블 설계 (DB Schema Design)

수집 데이터는 총 3개의 테이블로 나누어 관리합니다:
1. **`kospi200_stocks`**: KOSPI 200 구성 종목 마스터 (`use_yn` 포함)
2. **`kospi200_daily_data`**: KOSPI 200 일별 현물 수급/가격/외인 지분율
3. **`night_futures_daily_data`**: 야간 선물(Eurex) 일별 종가/등락률/야간 외인 수급

---

### 3.1. KOSPI 200 종목 마스터 테이블 (`kospi200_stocks`)
KOSPI 200 구성 종목의 기본 정보와 **사용 여부(`use_yn`)**를 관리합니다.

| 컬럼명 | 데이터 타입 | 제약 조건 | 설명 |
| :--- | :--- | :--- | :--- |
| `ticker` | `VARCHAR(10)` | `PRIMARY KEY` | 종목코드 (예: `"005930"`) |
| `name` | `VARCHAR(100)` | `NOT NULL` | 종목명 (예: `"삼성전자"`) |
| `sector` | `VARCHAR(100)` | `NULL` | 업종/섹터명 (예: `"전기전자"`) |
| `weight` | `FLOAT` | `NULL` | KOSPI 200 내 구성 비중 (%) |
| **`use_yn`** | `VARCHAR(1)` | `NOT NULL, DEFAULT 'Y'` | **사용 여부 / 편입 여부 ('Y' / 'N')** |
| `created_at` | `TIMESTAMP` | `DEFAULT NOW()` | 최초 등록일시 |
| `updated_at` | `TIMESTAMP` | `DEFAULT NOW()` | 최종 갱신일시 |

#### ⭐️ `use_yn` (사용여부) 갱신 및 이력 관리 방식
* **신규 편입 종목**: 수집 시 KOSPI 200에 새롭게 들어온 종목은 `use_yn = 'Y'`로 등록 또는 갱신합니다.
* **편출 종목 (KOSPI 200에서 제외)**:  
  * 종목 레코드를 **실제 DB에서 삭제(DELETE)하지 않고, `use_yn = 'N'`으로 변경**합니다.
  * 이를 통해 과거 날짜의 KOSPI 200 수급 데이터를 조회할 때 **외래키(FK) 참조 무결성 및 과거 데이터 이력(Historical Data)을 100% 보존**합니다.
* **조회 시 활용**: 현재 시점의 KOSPI 200 활성 종목을 다룰 때 `WHERE use_yn = 'Y'` 조건을 적용하여 간편하게 필터링합니다.

---

### 3.2. KOSPI 200 일별 수급 및 가격 테이블 (`kospi200_daily_data`)
매일 새벽 수집되는 종목별 외국인/기관 수급 데이터와 가격/시총 정보를 누적 저장합니다.

| 컬럼명 | 데이터 타입 | 제약 조건 | 설명 |
| :--- | :--- | :--- | :--- |
| `id` | `BIGSERIAL` | `PRIMARY KEY` | 일련번호 |
| `trade_date` | `DATE` | `NOT NULL, INDEX` | 거래일자 (예: `'2026-08-10'`) |
| `ticker` | `VARCHAR(10)` | `FOREIGN KEY, INDEX` | 종목코드 (`kospi200_stocks.ticker` 참조) |
| `close_price` | `BIGINT` | `NOT NULL` | 종가 (원) |
| `market_cap` | `BIGINT` | `NOT NULL` | 시가총액 (원) |
| `foreign_buy_net_amount` | `BIGINT` | `NOT NULL` | 외국인 순매수 금액 (원) |
| `foreign_buy_net_volume` | `BIGINT` | `NOT NULL` | 외국인 순매수 수량 (주) |
| `foreign_holding_ratio` | `FLOAT` | `NOT NULL` | 외국인 지분율 (%) |
| `institution_buy_net_amount` | `BIGINT` | `NOT NULL` | 기관 순매수 금액 (원) |
| `created_at` | `TIMESTAMP` | `DEFAULT NOW()` | 수집일시 |

* **복합 유니크 제약조건 (Unique Constraint)**: `(trade_date, ticker)`

---

### 3.3. 야간 선물 일별 데이터 테이블 (`night_futures_daily_data`)
매일 새벽 마감된 야간 선물(Eurex KOSPI 200 선물) 지수 및 야간 수급 정보를 누적 저장합니다.

| 컬럼명 | 데이터 타입 | 제약 조건 | 설명 |
| :--- | :--- | :--- | :--- |
| `id` | `BIGSERIAL` | `PRIMARY KEY` | 일련번호 |
| `trade_date` | `DATE` | `NOT NULL, UNIQUE` | 거래일자 (예: `'2026-08-10'`) |
| `close_price` | `FLOAT` | `NOT NULL` | 야간 선물 종가 (지수 포인트) |
| `change_price` | `FLOAT` | `NOT NULL` | 전일 대비 변동폭 (+/-) |
| `change_rate` | `FLOAT` | `NOT NULL` | 등락률 (%) |
| `volume` | `BIGINT` | `NOT NULL` | 야간 선물 총 거래량 |
| `foreign_buy_net_contracts` | `BIGINT` | `NULL` | 야간 선물 외국인 순매수 계약 수 |
| `institution_buy_net_contracts` | `BIGINT` | `NULL` | 야간 선물 기관 순매수 계약 수 |
| `created_at` | `TIMESTAMP` | `DEFAULT NOW()` | 수집일시 |

---

## 4. 통합 수집 프로세스 (Collection Logic)

매일 새벽 05:30에 데몬이 실행되어 다음 3단계를 순차적으로 진행합니다:

1. **[단계 1] KOSPI 200 구성 종목 & 마스터(`kospi200_stocks`) 갱신**:
   * KRX에서 현재 KOSPI 200 종목 200개 획득 ➡️ `use_yn = 'Y'` 등록/갱신.
   * 제외된 종목 ➡️ `use_yn = 'N'`으로 상태 변경.
2. **[단계 2] KOSPI 200 일별 수급 (`kospi200_daily_data`) 수집**:
   * 200개 종목의 종가, 시총, 외국인/기관 순매수금, 외국인 지분율 수집 및 저장.
3. **[단계 3] 야간 선물 (`night_futures_daily_data`) 수집**:
   * 방금 마감된 야간 선물(Eurex)의 종가, 등락률, 거래량, 야간 외인 순매수 계약 수 수집 및 저장.

---

## 5. 컨테이너 구성 방안 (Podman Architecture)

* **서비스명**: `stockbs_kospi200_collector`
* **실행 명령**: `python -m app.services.kospi200_daemon`
* **구성 위치**: `podman-compose-all.yml`에 추가하여 독립적인 데몬으로 구동.
