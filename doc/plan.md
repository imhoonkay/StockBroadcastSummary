구성

모든 구성은 podman container 로 구성해줘.

1. db

   - postgresql 최신버전 포트 5438
   - db명은 stockbs, 아이디/패스워드 admin/passw0rd!
2. backend 포트는 8099

   * 테이블 하나 만들어서 채널명 : 매일경제TV, 식별자 : `mkeconomy_tv`, 핸들 :MKeconomy_TV , 방송 url : [www.youtube.com/@MKeconomy_TV/live](https://www.youtube.com/@MKeconomy_TV/live) , 수집상태 : on/off
     서울경제TV, `seouleconomytv`, SeoulEconomyTV, [www.youtube.com/@SeoulEconomyTV/live](https://www.youtube.com/@SeoulEconomyTV/live) , on
     **한국경제TV**, `hkwowtv`, hkwowtv, [www.youtube.com/@hkwowtv/live](https://www.youtube.com/hkwowtv/live) , on 등록해줘.
   * 한시간에 한번씩(정시에) 각 채널의 자막을 txt 로 만들어서 저장. txt 파일 정보는 테이블만들어서 저장.
   * 자막 파일을 `Google Antigravity SDK (gemini-3.5-flash)를 통해 1시간 자막 통합 요약 및 종목 분석 반환`, 테이블 만들어서 저장.
     .env 에 저장될 키 : `GEMINI_API_KEY=YOUR_GEMINI_API_KEY`

   * 요약에 사용될 프롬프트

   ```
   prompt = f"""아래 제공하는 [분석할 텍스트]를 바탕으로, 지시된 [작성 규칙]과 [출력 양식]을 '엄격히 준수'하여 요약 및 정리해 줘.

   [작성 규칙]
   1. (핵심) 단순 문장 복사(Copy-Paste) 절대 금지. 
      - 원문의 대화체, 단편적인 자막 문장, 불완전한 표현(예: "안녕하세요", "한 5%가 줄었습니다" 등)을 그대로 출력하지 말 것.
      - 전체 맥락을 완전히 이해한 뒤, 완성된 격식체 표준 문장(개조식)으로 재구성(Synthesis)하여 정리할 것.
   2. 주요 주제 수 유연화:
      - 텍스트의 핵심 주제 개수에 맞춰 주제 항목(## 1, ## 2...)을 유연하게 늘리거나 줄여서 구성할 것.
   3. [언급된 주요 종목별 투자 의견] 표 작성 원칙:
      - 텍스트 내에서 실제 언급된 종목/기업/시장 영역(예: 삼성전자, SK하이닉스, TCK 등)에 대해 분석된 투자 의견과 핵심 요약을 작성할 것.
      - '포착 종목', '유망주' 같은 모호한 대명사나 가짜 데이터(Dummy) 사용 금지. 실제 언급된 종목이 없으면 "특정 종목 언급 없음"으로 명시할 것.
      - 투자 의견은 [적극 추천 / 추천 / 관망 / 비추천 / 손절] 중 하나로 명확히 표기할 것.

   ---

   [출력 양식]

   ## 1. [핵심 주제 1]
   * **[소주제 타이틀]:**
     * 요약 내용 1 (문맥이 완벽히 정리된 개조식 문장)
     * 요약 내용 2

   ## 2. [핵심 주제 2]
   * **[소주제 타이틀]:**
     * 요약 내용 1
     * 요약 내용 2
   (※ 본문 주제 수에 따라 항목 수 유연하게 조율)

   ---

   ## N. 언급된 주요 종목별 투자 의견

   | 종목 / 대상 | 투자 의견 | 녹취록 핵심 요약 내용 |
   | :--- | :---: | :--- |
   | **[실제 종목명]** | **[투자의견]** | • 핵심 분석 내용 1<br>• 핵심 분석 내용 2 |

   ---

   [분석할 텍스트 입력]
   유튜브 라이브 방송 {channel_title} {window_label} 수집 자막:
   {concatenated_transcript[:25000]}
   """
   ```
3. frontend 포트는 8090
   로그인 기능
   메뉴를 만들어서 위에 테이블에 들어 있는 내용들을 보여줘
