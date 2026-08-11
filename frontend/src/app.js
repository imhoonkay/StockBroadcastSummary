const API_BASE = '/api';
let authToken = localStorage.getItem('stockbs_token') || null;

document.addEventListener('DOMContentLoaded', () => {
  if (authToken) {
    showDashboard();
  } else {
    showLogin();
  }
});

function showLogin() {
  document.getElementById('loginView').style.display = 'block';
  document.getElementById('appDashboard').style.display = 'none';
  document.getElementById('sidebarNav').style.display = 'none';
  document.querySelector('.main-content').style.marginLeft = '0';
  document.getElementById('authBtn').innerHTML = '<i class="fa-solid fa-right-to-bracket"></i> 로그인';
}

function showDashboard() {
  document.getElementById('loginView').style.display = 'none';
  document.getElementById('appDashboard').style.display = 'block';
  document.getElementById('sidebarNav').style.display = 'flex';
  document.querySelector('.main-content').style.marginLeft = '260px';
  document.getElementById('authBtn').innerHTML = '<i class="fa-solid fa-right-from-bracket"></i> 로그아웃';

  // Restore persistent active tab or default to channelsTab
  const savedTab = localStorage.getItem('stockbs_active_tab') || 'channelsTab';
  switchTab(savedTab);

  loadChannels();
  loadSummaries();
  loadSubtitles();
  loadBuffers();
  loadKospi200Data();
  loadKospiPredictions();
}

function handleAuthClick() {
  if (authToken) {
    authToken = null;
    localStorage.removeItem('stockbs_token');
    showLogin();
  } else {
    showLogin();
  }
}

async function submitLogin(e) {
  e.preventDefault();
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || '로그인 실패');
      return;
    }
    const data = await res.json();
    authToken = data.access_token;
    localStorage.setItem('stockbs_token', authToken);
    showDashboard();
  } catch (err) {
    console.error('Login error:', err);
    alert('로그인 요청 중 오류가 발생했습니다.');
  }
}

function formatKST(dateStr) {
  if (!dateStr) return '-';
  // Ensure date string ends with +09:00 or Z if naive string
  let str = String(dateStr);
  if (!str.includes('Z') && !str.includes('+')) {
    str += '+09:00';
  }
  const d = new Date(str);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', hour12: false });
}

// Global Tab Switcher
function switchTab(tabId) {
  // Save selected tab in localStorage for page refresh persistence
  localStorage.setItem('stockbs_active_tab', tabId);

  // Update navbar items
  document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
  const activeNavItem = document.getElementById(`nav-${tabId}`);
  if (activeNavItem) {
    activeNavItem.classList.add('active');
  }

  // Update tab content displays
  document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
  const targetTab = document.getElementById(tabId);
  if (targetTab) {
    targetTab.classList.add('active');
  }

  if (tabId === 'buffersTab') {
    loadBuffers();
  } else if (tabId === 'kospiTab') {
    loadKospi200Data();
  } else if (tabId === 'predictTab') {
    loadKospiPredictions();
  }
}

// Channels Logic
async function loadChannels() {
  try {
    const res = await fetch(`${API_BASE}/channels`);
    const channels = await res.json();
    const tbody = document.getElementById('channelsTableBody');
    tbody.innerHTML = '';

    channels.forEach(ch => {
      const tr = document.createElement('tr');
      const isChecked = ch.status === 'on';
      tr.innerHTML = `
        <td><strong>${ch.id}</strong></td>
        <td><strong>${ch.name}</strong></td>
        <td><code>${ch.identifier}</code></td>
        <td>${ch.handle}</td>
        <td><a href="${ch.url}" target="_blank" style="color: #000000; font-weight: 700; text-decoration: underline; font-family: monospace; font-size: 0.85rem;"><i class="fa-solid fa-arrow-up-right-from-square"></i> ${ch.url}</a></td>
        <td>
          <label class="switch">
            <input type="checkbox" ${isChecked ? 'checked' : ''} onchange="toggleChannelStatus(${ch.id}, this.checked)">
            <span class="slider"></span>
          </label>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Failed to load channels:', err);
  }
}

async function toggleChannelStatus(channelId, isChecked) {
  const newStatus = isChecked ? 'on' : 'off';
  try {
    const res = await fetch(`${API_BASE}/channels/${channelId}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) {
      loadChannels();
    } else {
      alert('채널 상태 변경 실패');
    }
  } catch (err) {
    console.error('Error toggling channel status:', err);
  }
}

function initDateFilters() {
  const today = new Date();
  const past = new Date();
  past.setDate(today.getDate() - 7); // Default to last 7 days for stock/macro trading dates

  const formatD = (d) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  };

  const todayStr = formatD(today);
  const pastStr = formatD(past);

  ['summary', 'sub', 'buf'].forEach(prefix => {
    const startInput = document.getElementById(`${prefix}StartDate`);
    const endInput = document.getElementById(`${prefix}EndDate`);
    if (startInput && !startInput.value) startInput.value = todayStr;
    if (endInput && !endInput.value) endInput.value = todayStr;
  });

  ['kospi', 'predict'].forEach(prefix => {
    const startInput = document.getElementById(`${prefix}StartDate`);
    const endInput = document.getElementById(`${prefix}EndDate`);
    if (startInput && !startInput.value) startInput.value = pastStr;
    if (endInput && !endInput.value) endInput.value = todayStr;
  });
}


// Summaries & Stock Analysis Logic
async function loadSummaries() {
  initDateFilters();
  const startDate = document.getElementById('summaryStartDate')?.value || '';
  const endDate = document.getElementById('summaryEndDate')?.value || '';
  const filter = document.getElementById('summaryChannelFilter')?.value || '';

  const params = new URLSearchParams();
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  if (filter) params.append('channel_identifier', filter);

  const queryString = params.toString();
  const url = `${API_BASE}/summaries${queryString ? '?' + queryString : ''}`;

  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.error(`Summaries API error: ${res.status}`);
      return;
    }
    const summaries = await res.json();
    const container = document.getElementById('summariesContainer');
    container.innerHTML = '';

    if (!Array.isArray(summaries) || summaries.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 3rem; color: var(--text-muted);">
          <i class="fa-solid fa-inbox" style="font-size: 2.5rem; margin-bottom: 1rem;"></i>
          <p>선택하신 조건에 해당하는 AI 요약 정보가 없습니다.</p>
        </div>
      `;
      return;
    }

    summaries.forEach(s => {
      const card = document.createElement('div');
      card.className = 'card';

      const channelNameMap = {
        'mkeconomy_tv': '매일경제TV',
        'seouleconomytv': '서울경제TV',
        'hkwowtv': '한국경제TV'
      };

      const channelTitle = channelNameMap[s.channel_identifier] || s.channel_identifier;
      let htmlContent = marked.parse(s.summary_text);

      // Enhance table investment opinion badges to monochrome style
      htmlContent = htmlContent.replace(/<strong>적극 추천<\/strong>/g, '<span class="badge badge-rec-strongly">적극 추천</span>');
      htmlContent = htmlContent.replace(/<strong>추천<\/strong>/g, '<span class="badge badge-rec">추천</span>');
      htmlContent = htmlContent.replace(/<strong>관망<\/strong>/g, '<span class="badge badge-watch">관망</span>');
      htmlContent = htmlContent.replace(/<strong>비추천<\/strong>/g, '<span class="badge badge-not-rec">비추천</span>');

      card.innerHTML = `
        <div class="card-header" style="border-bottom: 1px solid var(--border-color); padding-bottom: 0.75rem; margin-bottom: 1rem;">
          <div>
            <span class="badge badge-on" style="margin-right: 0.5rem;">${channelTitle}</span>
            <strong style="font-size: 1.05rem;">시간 구간: ${s.window_label}</strong>
          </div>
          <span style="color: var(--text-muted); font-size: 0.85rem;">
            <i class="fa-regular fa-clock"></i> 생성일시: ${formatKST(s.created_at)}
          </span>
        </div>
        <div class="markdown-body">
          ${htmlContent}
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error('Failed to load summaries:', err);
  }
}

// Subtitles Logic
async function loadSubtitles() {
  initDateFilters();
  const startDate = document.getElementById('subStartDate')?.value || '';
  const endDate = document.getElementById('subEndDate')?.value || '';
  const filter = document.getElementById('subChannelFilter')?.value || '';

  const params = new URLSearchParams();
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  if (filter) params.append('channel_identifier', filter);

  const queryString = params.toString();
  const url = `${API_BASE}/subtitles${queryString ? '?' + queryString : ''}`;

  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.error(`Subtitles API error: ${res.status}`);
      return;
    }
    const subs = await res.json();
    const tbody = document.getElementById('subtitlesTableBody');
    tbody.innerHTML = '';

    if (!Array.isArray(subs) || subs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">선택하신 조건에 해당하는 자막 파일이 없습니다.</td></tr>`;
      return;
    }

    subs.forEach(sub => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${sub.id}</td>
        <td><code>${sub.channel_identifier}</code></td>
        <td><strong>${sub.file_name}</strong></td>
        <td>${sub.window_label}</td>
        <td>${(sub.file_size / 1024).toFixed(1)} KB</td>
        <td>${formatKST(sub.collected_at)}</td>
        <td>
          <button class="btn btn-secondary" style="padding: 0.3rem 0.7rem; font-size: 0.8rem;" onclick="viewSubtitleContent(${sub.id}, '${sub.file_name}')">
            <i class="fa-solid fa-eye"></i> 자막 보기
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Failed to load subtitles:', err);
  }
}

async function viewSubtitleContent(subId, fileName) {
  try {
    const res = await fetch(`${API_BASE}/subtitles/${subId}`);
    const sub = await res.json();
    document.getElementById('modalTitle').innerText = `[자막 원문] ${fileName}`;
    document.getElementById('modalBody').innerText = sub.transcript_text;
    document.getElementById('subModal').classList.add('active');
  } catch (err) {
    console.error('Error viewing subtitle:', err);
  }
}

function closeModal(modalId) {
  document.getElementById(modalId).classList.remove('active');
}

// Global Keydown & Click listener for closing modal via ESC or clicking overlay
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' || e.key === 'Esc') {
    closeModal('subModal');
  }
});

document.addEventListener('click', (e) => {
  const modal = document.getElementById('subModal');
  if (e.target === modal) {
    closeModal('subModal');
  }
});

// 10-Min Rolling Subtitle Buffers Logic
async function loadBuffers() {
  initDateFilters();
  const startDate = document.getElementById('bufStartDate')?.value || '';
  const endDate = document.getElementById('bufEndDate')?.value || '';
  const filter = document.getElementById('bufChannelFilter')?.value || '';

  const params = new URLSearchParams();
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  if (filter) params.append('channel_identifier', filter);

  const queryString = params.toString();
  const url = `${API_BASE}/buffers${queryString ? '?' + queryString : ''}`;

  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.error(`Buffers API error: ${res.status}`);
      return;
    }
    const buffers = await res.json();
    const tbody = document.getElementById('buffersTableBody');
    tbody.innerHTML = '';

    if (!Array.isArray(buffers) || buffers.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">선택하신 조건에 해당하는 자막 버퍼 조각이 없습니다.</td></tr>`;
      return;
    }

    buffers.forEach(buf => {
      const tr = document.createElement('tr');
      const textLen = buf.chunk_text ? buf.chunk_text.length : 0;
      tr.innerHTML = `
        <td>${buf.id}</td>
        <td><code>${buf.channel_identifier}</code></td>
        <td>${buf.window_label}</td>
        <td>${(textLen / 1024).toFixed(1)} KB</td>
        <td>${formatKST(buf.created_at)}</td>
        <td>
          <button class="btn btn-secondary" style="padding: 0.3rem 0.7rem; font-size: 0.8rem;" onclick="viewBufferContent(${buf.id}, '${buf.channel_identifier}')">
            <i class="fa-solid fa-eye"></i> 조각 보기
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Failed to load buffers:', err);
  }
}

async function viewBufferContent(bufferId, channelIdent) {
  try {
    const res = await fetch(`${API_BASE}/buffers/${bufferId}`);
    const buf = await res.json();
    document.getElementById('modalTitle').innerText = `[10분 롤링 버퍼 조각] ${channelIdent} (#${bufferId})`;
    document.getElementById('modalBody').innerText = buf.chunk_text;
    document.getElementById('subModal').classList.add('active');
  } catch (err) {
    console.error('Error viewing buffer:', err);
  }
}

// Manual trigger action
async function triggerManualCollection() {
  const btn = document.getElementById('collectNowBtn');
  const originalText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 수집 중...';

  try {
    const res = await fetch(`${API_BASE}/collect/run`, { method: 'POST' });
    const data = await res.json();
    alert('자막 수집 및 Gemini AI 요약 분석이 완료되었습니다!');
    loadChannels();
    loadSummaries();
    loadSubtitles();
    loadBuffers();
  } catch (err) {
    console.error('Error triggering manual collection:', err);
    alert('자막 수집 중 오류가 발생했습니다.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalText;
  }
}

function formatKRW(val) {
  if (val === null || val === undefined || isNaN(val)) return '-';
  const num = Number(val);
  const abs = Math.abs(num);
  const sign = num > 0 ? '+' : (num < 0 ? '-' : '');
  
  if (abs >= 1_0000_0000_0000) {
    const jo = (abs / 1_0000_0000_0000).toFixed(1);
    return `${sign}${jo}조원`;
  } else if (abs >= 1_0000_0000) {
    const eok = Math.round(abs / 1_0000_0000).toLocaleString();
    return `${sign}${eok}억원`;
  } else {
    return `${num.toLocaleString()}원`;
  }
}

async function loadKospi200Data() {
  initDateFilters();
  const startDate = document.getElementById('kospiStartDate')?.value || '';
  const endDate = document.getElementById('kospiEndDate')?.value || '';
  const keyword = document.getElementById('kospiKeyword')?.value || '';

  // 1. Fetch Night Futures
  try {
    const nfParams = new URLSearchParams();
    if (startDate) nfParams.append('start_date', startDate);
    if (endDate) nfParams.append('end_date', endDate);
    
    const nfRes = await fetch(`${API_BASE}/kospi200/night-futures?${nfParams.toString()}`);
    if (nfRes.ok) {
      const nfData = await nfRes.json();
      const tbody = document.getElementById('nightFuturesTableBody');
      tbody.innerHTML = '';

      if (!Array.isArray(nfData) || nfData.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">수집된 야간 선물 데이터가 없습니다.</td></tr>`;
        document.getElementById('statNightFutures').innerText = '-';
      } else {
        const latest = nfData[0];
        const changeStr = latest.change_price >= 0 ? `+${latest.change_price}` : `${latest.change_price}`;
        const rateStr = latest.change_rate >= 0 ? `+${latest.change_rate}%` : `${latest.change_rate}%`;
        const rateColor = latest.change_rate > 0 ? '#4ade80' : (latest.change_rate < 0 ? '#f87171' : '#94a3b8');

        document.getElementById('statNightFutures').innerHTML = `
          ${latest.close_price} pt <span style="font-size: 1rem; color: ${rateColor}; margin-left: 0.5rem;">(${changeStr} / ${rateStr})</span>
        `;

        nfData.forEach(r => {
          const tr = document.createElement('tr');
          const rColor = r.change_rate > 0 ? '#4ade80' : (r.change_rate < 0 ? '#f87171' : 'inherit');
          tr.innerHTML = `
            <td><strong>${r.trade_date}</strong></td>
            <td><strong>${r.close_price} pt</strong></td>
            <td style="color: ${rColor}">${r.change_price >= 0 ? '+' + r.change_price : r.change_price}</td>
            <td style="color: ${rColor}; font-weight: bold;">${r.change_rate >= 0 ? '+' + r.change_rate : r.change_rate}%</td>
            <td>${r.volume.toLocaleString()} 계약</td>
            <td>${formatKST(r.created_at)}</td>
          `;
          tbody.appendChild(tr);
        });
      }
    }
  } catch (err) {
    console.error('Failed to load night futures:', err);
  }

  // 2. Fetch KOSPI 200 Daily Stocks
  try {
    const dailyParams = new URLSearchParams();
    if (startDate) dailyParams.append('start_date', startDate);
    if (endDate) dailyParams.append('end_date', endDate);
    if (keyword) dailyParams.append('keyword', keyword);

    const dailyRes = await fetch(`${API_BASE}/kospi200/daily?${dailyParams.toString()}`);
    if (dailyRes.ok) {
      const dailyData = await dailyRes.json();
      const tbody = document.getElementById('kospiDailyTableBody');
      tbody.innerHTML = '';

      if (!Array.isArray(dailyData) || dailyData.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">조회 조건에 해당하는 KOSPI 200 종목 데이터가 없습니다.</td></tr>`;
        document.getElementById('statTopForeignBuy').innerText = '-';
        document.getElementById('statTopForeignSell').innerText = '-';
      } else {
        // Find top foreign buy / sell stocks
        const topBuy = [...dailyData].sort((a,b) => b.foreign_buy_net_amount - a.foreign_buy_net_amount)[0];
        const topSell = [...dailyData].sort((a,b) => a.foreign_buy_net_amount - b.foreign_buy_net_amount)[0];

        if (topBuy && topBuy.foreign_buy_net_amount > 0) {
          document.getElementById('statTopForeignBuy').innerHTML = `${topBuy.name} <span style="font-size: 0.95rem; font-weight: normal;">(${formatKRW(topBuy.foreign_buy_net_amount)})</span>`;
        } else {
          document.getElementById('statTopForeignBuy').innerText = '-';
        }

        if (topSell && topSell.foreign_buy_net_amount < 0) {
          document.getElementById('statTopForeignSell').innerHTML = `${topSell.name} <span style="font-size: 0.95rem; font-weight: normal;">(${formatKRW(topSell.foreign_buy_net_amount)})</span>`;
        } else {
          document.getElementById('statTopForeignSell').innerText = '-';
        }

        dailyData.forEach(r => {
          const tr = document.createElement('tr');
          const frgColor = r.foreign_buy_net_amount > 0 ? '#4ade80' : (r.foreign_buy_net_amount < 0 ? '#f87171' : 'inherit');
          const instColor = r.institution_buy_net_amount > 0 ? '#4ade80' : (r.institution_buy_net_amount < 0 ? '#f87171' : 'inherit');

          tr.innerHTML = `
            <td>${r.trade_date}</td>
            <td><strong>${r.name}</strong></td>
            <td><code>${r.ticker}</code></td>
            <td>${r.close_price.toLocaleString()} 원</td>
            <td>${formatKRW(r.market_cap)}</td>
            <td><strong style="color: #38bdf8;">${r.foreign_holding_ratio}%</strong></td>
            <td style="color: ${frgColor}; font-weight: bold;">${formatKRW(r.foreign_buy_net_amount)}</td>
            <td style="color: ${instColor}">${formatKRW(r.institution_buy_net_amount)}</td>
          `;
          tbody.appendChild(tr);
        });
      }
    }
  } catch (err) {
    console.error('Failed to load KOSPI 200 daily data:', err);
  }
}

async function loadMacroIndicators() {
  try {
    const res = await fetch(`${API_BASE}/kospi200/macro`);
    if (!res.ok) return;

    const data = await res.json();
    if (!Array.isArray(data) || data.length === 0) return;

    const latest = data[0];
    const nqColor = latest.nasdaq_change_rate > 0 ? '#4ade80' : (latest.nasdaq_change_rate < 0 ? '#f87171' : '#94a3b8');
    const nqSign = latest.nasdaq_change_rate >= 0 ? '+' : '';
    
    document.getElementById('statNasdaq').innerHTML = `
      ${latest.nasdaq_close.toLocaleString()} <span style="font-size: 0.95rem; color: ${nqColor}; font-weight: normal;">(${nqSign}${latest.nasdaq_change_rate}%)</span>
    `;

    document.getElementById('statUsdKrw').innerText = `${latest.usd_krw.toLocaleString()} 원`;

    const soxSign = latest.sox_change_rate >= 0 ? '+' : '';
    const soxColor = latest.sox_change_rate > 0 ? '#4ade80' : (latest.sox_change_rate < 0 ? '#f87171' : '#94a3b8');
    
    document.getElementById('statMacroSummary').innerHTML = `
      반도체(SOX): <span style="color: ${soxColor}">${soxSign}${latest.sox_change_rate}%</span><br>
      미 국채금리: ${latest.us10y_yield}% | WTI유가: $${latest.wti_oil}
    `;

    const newsUl = document.getElementById('macroNewsList');
    if (Array.isArray(latest.news_headlines) && latest.news_headlines.length > 0) {
      newsUl.innerHTML = '';
      latest.news_headlines.forEach(title => {
        const li = document.createElement('li');
        li.innerText = title;
        newsUl.appendChild(li);
      });
    }

    // Populate Historical Macro Data Table
    const macroTbody = document.getElementById('macroHistoryTableBody');
    if (macroTbody) {
      macroTbody.innerHTML = '';
      data.forEach(r => {
        const tr = document.createElement('tr');
        const fmtIdx = (close, rate) => {
          if (!close || close === 0) return '-';
          const color = rate > 0 ? '#4ade80' : (rate < 0 ? '#f87171' : '#94a3b8');
          const sign = rate >= 0 ? '+' : '';
          return `<strong>${close.toLocaleString()}</strong> <span style="color:${color}; font-size:0.8rem;">(${sign}${rate}%)</span>`;
        };

        const nqC = r.nasdaq_change_rate > 0 ? '#4ade80' : (r.nasdaq_change_rate < 0 ? '#f87171' : 'inherit');
        const soxC = r.sox_change_rate > 0 ? '#4ade80' : (r.sox_change_rate < 0 ? '#f87171' : 'inherit');

        tr.innerHTML = `
          <td><strong>${r.trade_date}</strong></td>
          <td>${fmtIdx(r.kospi_close, r.kospi_change_rate)}</td>
          <td>${fmtIdx(r.kosdaq_close, r.kosdaq_change_rate)}</td>
          <td>${fmtIdx(r.kospi200_close, r.kospi200_change_rate)}</td>
          <td>${fmtIdx(r.kospi200_futures_close, r.kospi200_futures_change_rate)}</td>
          <td>${fmtIdx(r.kosdaq150_close, r.kosdaq150_change_rate)}</td>
          <td>${fmtIdx(r.valueup_close, r.valueup_change_rate)}</td>
          <td>${r.nasdaq_close.toLocaleString()} <span style="color:${nqC}; font-size:0.8rem;">(${r.nasdaq_change_rate >= 0 ? '+' : ''}${r.nasdaq_change_rate}%)</span></td>
          <td><strong>${r.usd_krw.toLocaleString()} 원</strong></td>
          <td style="color: ${soxC}">${r.sox_change_rate >= 0 ? '+' + r.sox_change_rate : r.sox_change_rate}%</td>
          <td>${r.us10y_yield}%</td>
          <td>$${r.wti_oil}</td>
          <td>${formatKST(r.created_at)}</td>
        `;
        macroTbody.appendChild(tr);
      });
    }

  } catch (err) {
    console.error('Failed to load macro indicators:', err);
  }
}


async function loadKospiPredictions() {
  initDateFilters();
  loadMacroIndicators();
  const startDate = document.getElementById('predictStartDate')?.value || '';
  const endDate = document.getElementById('predictEndDate')?.value || '';


  const params = new URLSearchParams();
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  try {
    const res = await fetch(`${API_BASE}/kospi200/predictions?${params.toString()}`);
    if (!res.ok) return;

    const responseData = await res.json();
    const metrics = responseData.metrics || {};
    const predictions = responseData.predictions || (Array.isArray(responseData) ? responseData : []);

    const latestCard = document.getElementById('latestPredictionCard');
    const tbody = document.getElementById('predictTableBody');
    tbody.innerHTML = '';

    // Update accuracy stat card
    const accRateEl = document.getElementById('statAccuracyRate');
    if (accRateEl) {
      if (metrics.total_evaluated > 0) {
        accRateEl.innerHTML = `<span style="color: #c084fc;">${metrics.accuracy_rate}%</span> <span style="font-size: 0.8rem; color: #94a3b8;">(${metrics.accurate_count}/${metrics.total_evaluated}일 적중)</span>`;
      } else {
        accRateEl.innerHTML = '<span style="color: #94a3b8; font-size: 0.9rem;">⏳ 데이터 집계 중</span>';
      }
    }

    if (!Array.isArray(predictions) || predictions.length === 0) {
      document.getElementById('statPredictDate').innerText = '-';
      document.getElementById('statGapDirection').innerText = '-';
      latestCard.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 2rem;">생성된 AI KOSPI 개장 예측 브리핑이 없습니다. [즉시 AI 개장 예측 생성] 버튼을 눌러보세요.</div>`;
      tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted);">저장된 예측 이력이 없습니다.</td></tr>`;
      return;
    }

    const latest = predictions[0];
    document.getElementById('statPredictDate').innerText = latest.predict_date;

    const dirBadgeColor = latest.gap_direction === '갭상승' ? '#4ade80' : (latest.gap_direction === '갭하락' ? '#f87171' : '#38bdf8');
    document.getElementById('statGapDirection').innerHTML = `<span style="color: ${dirBadgeColor};">${latest.gap_direction}</span>`;

    // Render markdown for latest briefing
    latestCard.innerHTML = marked.parse(latest.prediction_text);

    window._predictionCache = predictions;

    predictions.forEach(r => {
      const tr = document.createElement('tr');
      const dColor = r.gap_direction === '갭상승' ? '#4ade80' : (r.gap_direction === '갭하락' ? '#f87171' : '#38bdf8');

      let accuracyBadge = '<span style="color: #94a3b8; font-size: 0.85rem;">⏳ 대기 중</span>';
      if (r.is_accurate === true) {
        accuracyBadge = '<span class="badge" style="background: rgba(74,222,128,0.15); color: #4ade80; border: 1px solid #4ade80; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600;">🎯 적중</span>';
      } else if (r.is_accurate === false) {
        accuracyBadge = '<span class="badge" style="background: rgba(248,113,113,0.15); color: #f87171; border: 1px solid #f87171; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600;">❌ 미적중</span>';
      }

      tr.innerHTML = `
        <td>${r.id}</td>
        <td><strong>${r.predict_date}</strong></td>
        <td><strong style="color: ${dColor};">${r.gap_direction}</strong></td>
        <td><code>${r.predicted_change_rate || '-'}</code></td>
        <td><code>${r.actual_change_rate || '-'}</code></td>
        <td>${accuracyBadge}</td>
        <td><code>${r.error_margin || '-'}</code></td>
        <td>${formatKST(r.created_at)}</td>
        <td>
          <button class="btn btn-secondary" style="padding: 0.3rem 0.7rem; font-size: 0.8rem;" onclick="viewPredictionDetail(${r.id})">
            <i class="fa-solid fa-eye"></i> 브리핑 보기
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });


  } catch (err) {
    console.error('Failed to load predictions:', err);
  }
}

async function triggerManualPrediction() {
  const btn = document.getElementById('runPredictBtn');
  const origText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> AI 예측 생성 중...';

  try {
    const res = await fetch(`${API_BASE}/kospi200/predictions/run`, { method: 'POST' });
    if (res.ok) {
      alert('당일 KOSPI AI 개장 예측 브리핑이 성공적으로 생성되었습니다!');
      loadKospiPredictions();
    } else {
      alert('AI 예측 생성 실패');
    }
  } catch (err) {
    console.error('Error running manual prediction:', err);
    alert('AI 예측 생성 요청 중 오류가 발생했습니다.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = origText;
  }
}

async function viewPredictionDetail(id) {
  try {
    let pred = (window._predictionCache && Array.isArray(window._predictionCache)) ? window._predictionCache.find(x => x.id === id) : null;
    if (!pred) {
      const res = await fetch(`${API_BASE}/kospi200/predictions`);
      const responseData = await res.json();
      const predictions = responseData.predictions || (Array.isArray(responseData) ? responseData : []);
      pred = predictions.find(x => x.id === id);
    }
    if (pred) {
      document.getElementById('modalTitle').innerText = `[AI KOSPI 개장 예측] ${pred.predict_date} (${pred.gap_direction})`;
      document.getElementById('modalBody').innerHTML = marked.parse(pred.prediction_text);
      document.getElementById('subModal').classList.add('active');
    }
  } catch (err) {
    console.error('Error viewing prediction detail:', err);
  }
}



