(() => {
  const HISTORY_KEY = "yt_web_audio_history_v1";
  const THEME_KEY = "yt_web_audio_theme_v1";

  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

  const state = {
    results: [],
    selectedVideo: null,
    format: "mp3",
    quality: "192",
    activeJobId: null,
    pollTimer: null,
    completedJob: null,
  };

  // DOM References
  const searchForm = document.getElementById("searchForm");
  const searchInput = document.getElementById("searchInput");
  const btnPaste = document.getElementById("btnPaste");
  const btnSearchSubmit = document.getElementById("btnSearchSubmit");

  const previewStage = document.getElementById("previewStage");
  const ytPlayerFrame = document.getElementById("ytPlayerFrame");
  const previewTitle = document.getElementById("previewTitle");
  const previewChannel = document.getElementById("previewChannel");
  const btnClosePreview = document.getElementById("btnClosePreview");
  const btnStartDownload = document.getElementById("btnStartDownload");
  const btnStartDownloadLabel = document.getElementById("btnStartDownloadLabel");

  const resultsHeader = document.getElementById("resultsHeader");
  const resultsHeading = document.getElementById("resultsHeading");
  const resultsCount = document.getElementById("resultsCount");
  const resultsContainer = document.getElementById("resultsContainer");

  const progressModal = document.getElementById("progressModal");
  const progressPercent = document.getElementById("progressPercent");
  const progressTrackName = document.getElementById("progressTrackName");
  const progressFill = document.getElementById("progressFill");
  const progressStatusText = document.getElementById("progressStatusText");
  const btnCancelJob = document.getElementById("btnCancelJob");

  const completeModal = document.getElementById("completeModal");
  const completeSub = document.getElementById("completeSub");
  const completeFileName = document.getElementById("completeFileName");
  const completeFileMeta = document.getElementById("completeFileMeta");
  const completeAudioPlayer = document.getElementById("completeAudioPlayer");
  const btnSaveFileLink = document.getElementById("btnSaveFileLink");
  const btnSaveFileText = document.getElementById("btnSaveFileText");
  const btnNativeShare = document.getElementById("btnNativeShare");
  const btnCloseComplete = document.getElementById("btnCloseComplete");

  const historyModal = document.getElementById("historyModal");
  const historyList = document.getElementById("historyList");
  const btnOpenHistory = document.getElementById("btnOpenHistory");
  const btnClearHistory = document.getElementById("btnClearHistory");
  const btnCloseHistory = document.getElementById("btnCloseHistory");

  const btnToggleTheme = document.getElementById("btnToggleTheme");
  const toastEl = document.getElementById("toast");

  let toastTimer = null;

  function showToast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add("visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove("visible"), 2600);
  }

  function formatSize(bytes) {
    if (!bytes || bytes < 1024) return `${bytes || 0} B`;
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    return `${(kb / 1024).toFixed(2)} MB`;
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // Theme Initialization
  function initTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    const theme = saved || (prefersDark ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", theme);
  }

  btnToggleTheme.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(THEME_KEY, next);
  });

  // Format Selector
  document.querySelectorAll(".format-option").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".format-option").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.format = btn.dataset.format || "mp3";
      state.quality = btn.dataset.quality || "192";
      updateDownloadButtonLabel();
    });
  });

  function updateDownloadButtonLabel() {
    const label = state.format === "m4a"
      ? "M4A 음원 다운로드"
      : `MP3 (${state.quality}k) 음원 다운로드`;
    btnStartDownloadLabel.textContent = label;
  }

  // Quick Search Chips
  document.querySelectorAll(".quick-tag").forEach((chip) => {
    chip.addEventListener("click", () => {
      const q = chip.dataset.query || "";
      searchInput.value = q;
      performSearch(q);
    });
  });

  // Clipboard Paste Button (especially handy on iPhone)
  btnPaste.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text && text.trim()) {
        searchInput.value = text.trim();
        performSearch(text.trim());
      } else {
        showToast("클립보드에 복사된 내용이 없습니다.");
      }
    } catch {
      searchInput.focus();
      showToast("입력창을 길게 눌러 '붙여넣기'를 선택해 주세요.");
    }
  });

  // Search Submit
  searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = searchInput.value.trim();
    if (!q) {
      showToast("곡명이나 유튜브 링크를 입력해 주세요.");
      searchInput.focus();
      return;
    }
    searchInput.blur();
    performSearch(q);
  });

  async function performSearch(query) {
    btnSearchSubmit.disabled = true;
    resultsHeader.style.display = "none";
    resultsContainer.innerHTML = `
      <div class="empty-state">
        <div class="spinner"></div>
        <h2>유튜브에서 찾는 중...</h2>
        <p>${escapeHtml(query)}</p>
      </div>
    `;

    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&limit=10`);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "검색에 실패했습니다.");
      }
      state.results = data.items || [];
      renderResults(query, data.is_direct_url);

      if (data.is_direct_url && state.results.length > 0) {
        selectVideo(state.results[0], true);
      }
    } catch (err) {
      resultsContainer.innerHTML = `
        <div class="empty-state">
          <h2>검색 중 오류가 발생했습니다</h2>
          <p>${escapeHtml(err.message)}</p>
        </div>
      `;
    } finally {
      btnSearchSubmit.disabled = false;
    }
  }

  function renderResults(query, isDirectUrl) {
    if (!state.results.length) {
      resultsHeader.style.display = "none";
      resultsContainer.innerHTML = `
        <div class="empty-state">
          <h2>검색 결과가 없습니다</h2>
          <p>다른 검색어를 입력하거나 유튜브 링크를 직접 붙여넣어 보세요.</p>
        </div>
      `;
      return;
    }

    resultsHeader.style.display = "flex";
    resultsHeading.textContent = isDirectUrl ? "링크에서 찾은 영상" : `"${query}" 검색 결과`;
    resultsCount.textContent = `${state.results.length}개`;

    resultsContainer.innerHTML = state.results.map((item) => {
      const isSelected = state.selectedVideo && state.selectedVideo.id === item.id;
      const durBadge = item.duration_text
        ? `<span class="duration-badge">${escapeHtml(item.duration_text)}</span>`
        : "";
      return `
        <article class="result-card ${isSelected ? "selected" : ""}" data-video-id="${escapeHtml(item.id)}">
          <div class="result-thumb-wrap">
            <img class="result-thumb" src="${escapeHtml(item.thumbnail)}" alt="" loading="lazy" />
            ${durBadge}
          </div>
          <div class="result-info">
            <h3 class="result-title">${escapeHtml(item.title)}</h3>
            <p class="result-channel">${escapeHtml(item.channel || "YouTube")}</p>
          </div>
          <button type="button" class="quick-dl-btn" data-dl-id="${escapeHtml(item.id)}" aria-label="바로 다운로드" title="바로 음원 다운로드">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M5 20h14v-2H5v2zM19 9h-4V3H9v6H5l7 7 7-7z" />
            </svg>
          </button>
        </article>
      `;
    }).join("");

    resultsContainer.querySelectorAll(".result-card").forEach((card) => {
      card.addEventListener("click", (e) => {
        const dlBtn = e.target.closest(".quick-dl-btn");
        const vid = card.dataset.videoId;
        const item = state.results.find((r) => r.id === vid);
        if (!item) return;

        if (dlBtn) {
          selectVideo(item, false);
          startDownload(item);
        } else {
          selectVideo(item, true);
        }
      });
    });
  }

  function selectVideo(item, autoplay) {
    state.selectedVideo = item;
    previewTitle.textContent = item.title;
    previewChannel.textContent = item.channel ? `${item.channel}${item.duration_text ? ` · ${item.duration_text}` : ""}` : "YouTube";

    // playsinline=1 is crucial on iOS Safari so playback stays inside the web app
    const autoParam = autoplay ? "1" : "0";
    ytPlayerFrame.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(item.id)}?autoplay=${autoParam}&playsinline=1&rel=0`;
    previewStage.classList.remove("hidden");

    resultsContainer.querySelectorAll(".result-card").forEach((c) => {
      c.classList.toggle("selected", c.dataset.videoId === item.id);
    });

    if (autoplay) {
      previewStage.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  btnClosePreview.addEventListener("click", () => {
    ytPlayerFrame.src = "";
    previewStage.classList.add("hidden");
    state.selectedVideo = null;
  });

  btnStartDownload.addEventListener("click", () => {
    if (!state.selectedVideo) {
      showToast("먼저 영상을 선택해 주세요.");
      return;
    }
    startDownload(state.selectedVideo);
  });

  // Download Job Lifecycle
  async function startDownload(video) {
    if (state.activeJobId) {
      showToast("이미 다른 음원을 변환 중입니다.");
      return;
    }

    openProgressModal(video.title);

    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: video.url,
          format: state.format,
          quality: state.quality,
          title_hint: video.title,
        }),
      });
      const job = await res.json();
      if (!res.ok) {
        throw new Error(job.detail || "다운로드 요청에 실패했습니다.");
      }

      state.activeJobId = job.job_id;
      pollJobStatus(job.job_id);
    } catch (err) {
      closeProgressModal();
      showToast(err.message || "다운로드를 시작할 수 없습니다.");
    }
  }

  function pollJobStatus(jobId) {
    clearTimeout(state.pollTimer);

    const tick = async () => {
      if (state.activeJobId !== jobId) return;
      try {
        const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
        if (!res.ok) throw new Error("작업 상태 조회 실패");
        const job = await res.json();

        updateProgressModal(job.percent || 0, job.status_text || "처리 중...");

        if (job.status === "completed") {
          state.activeJobId = null;
          closeProgressModal();
          openCompleteModal(job);
          saveToHistory(job);
          return;
        }

        if (job.status === "failed") {
          state.activeJobId = null;
          closeProgressModal();
          showToast(`실패: ${job.error || "음원 추출 오류"}`);
          return;
        }

        if (job.status === "cancelled") {
          state.activeJobId = null;
          closeProgressModal();
          showToast("다운로드를 취소했습니다.");
          return;
        }

        state.pollTimer = setTimeout(tick, 650);
      } catch (err) {
        state.activeJobId = null;
        closeProgressModal();
        showToast(err.message || "서버와 연결이 끊어졌습니다.");
      }
    };

    tick();
  }

  function openProgressModal(title) {
    progressTrackName.textContent = title || "YouTube 음원";
    progressPercent.textContent = "0%";
    progressFill.style.width = "6%";
    progressStatusText.textContent = "서버에서 음원 정보를 분석하는 중...";
    progressModal.classList.remove("hidden");
  }

  function updateProgressModal(percent, statusText) {
    const pct = Math.max(0, Math.min(100, percent));
    progressPercent.textContent = `${pct}%`;
    progressFill.style.width = `${Math.max(6, pct)}%`;
    progressStatusText.textContent = statusText;
  }

  function closeProgressModal() {
    clearTimeout(state.pollTimer);
    progressModal.classList.add("hidden");
  }

  btnCancelJob.addEventListener("click", async () => {
    const jid = state.activeJobId;
    state.activeJobId = null;
    closeProgressModal();
    if (jid) {
      try {
        await fetch(`/api/jobs/${encodeURIComponent(jid)}`, { method: "DELETE" });
      } catch {
        // ignore cancel network error
      }
    }
    showToast("다운로드를 취소했습니다.");
  });

  // Completion Modal & iPhone Native Save / Share
  function openCompleteModal(job) {
    state.completedJob = job;
    completeFileName.textContent = job.file_name || "youtube_audio.mp3";
    completeFileMeta.textContent = `${(job.format || "mp3").toUpperCase()} · ${formatSize(job.file_size)}`;

    btnSaveFileLink.href = job.download_url;
    btnSaveFileLink.setAttribute("download", job.file_name || "youtube_audio.mp3");
    btnSaveFileText.textContent = isIOS ? "아이폰 '파일' 앱에 저장" : "기기에 음원 파일 저장";
    completeSub.textContent = isIOS
      ? "아래 버튼을 누르면 Safari 다운로드로 '파일' 앱에 저장됩니다."
      : "변환된 고음질 음원을 바로 저장하거나 미리 들어볼 수 있습니다.";

    completeAudioPlayer.src = job.stream_url;
    completeAudioPlayer.load();

    // Show Web Share button when navigator.share is available (iOS 15+ Safari supports sharing File objects)
    btnNativeShare.style.display = typeof navigator.share === "function" ? "inline-flex" : "none";

    completeModal.classList.remove("hidden");
  }

  btnNativeShare.addEventListener("click", async () => {
    const job = state.completedJob;
    if (!job || !job.download_url) return;

    const origText = btnNativeShare.textContent;
    btnNativeShare.disabled = true;
    btnNativeShare.textContent = "공유 파일 준비 중...";

    try {
      const resp = await fetch(job.download_url);
      const blob = await resp.blob();
      const file = new File([blob], job.file_name || "audio.mp3", {
        type: job.mime_type || "audio/mpeg",
      });

      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({
          files: [file],
          title: job.title || job.file_name,
        });
      } else {
        // Fallback: trigger standard file download
        btnSaveFileLink.click();
      }
    } catch (err) {
      if (err && err.name !== "AbortError") {
        btnSaveFileLink.click();
      }
    } finally {
      btnNativeShare.disabled = false;
      btnNativeShare.textContent = origText;
    }
  });

  function closeCompleteModal() {
    completeAudioPlayer.pause();
    completeAudioPlayer.removeAttribute("src");
    completeModal.classList.add("hidden");
  }

  btnCloseComplete.addEventListener("click", closeCompleteModal);
  completeModal.addEventListener("click", (e) => {
    if (e.target === completeModal) closeCompleteModal();
  });

  // Local Download History
  function loadHistory() {
    try {
      return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    } catch {
      return [];
    }
  }

  function saveToHistory(job) {
    const items = loadHistory();
    const now = new Date();
    const timeLabel = `${now.getMonth() + 1}/${now.getDate()} ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    items.unshift({
      fileName: job.file_name,
      format: (job.format || "mp3").toUpperCase(),
      size: formatSize(job.file_size),
      time: timeLabel,
    });
    localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, 25)));
  }

  function renderHistory() {
    const items = loadHistory();
    if (!items.length) {
      historyList.innerHTML = `<p style="text-align:center;color:var(--ink-muted);font-size:13.5px;padding:18px 0;">아직 저장한 음원 기록이 없습니다.</p>`;
      return;
    }
    historyList.innerHTML = items.map((it) => `
      <div class="history-item">
        <div>
          <div class="history-name">${escapeHtml(it.fileName)}</div>
          <div class="history-meta">${escapeHtml(it.time)} · ${escapeHtml(it.format)} · ${escapeHtml(it.size)}</div>
        </div>
      </div>
    `).join("");
  }

  btnOpenHistory.addEventListener("click", () => {
    renderHistory();
    historyModal.classList.remove("hidden");
  });

  btnClearHistory.addEventListener("click", () => {
    localStorage.removeItem(HISTORY_KEY);
    renderHistory();
    showToast("저장 기록을 삭제했습니다.");
  });

  btnCloseHistory.addEventListener("click", () => historyModal.classList.add("hidden"));
  historyModal.addEventListener("click", (e) => {
    if (e.target === historyModal) historyModal.classList.add("hidden");
  });

  // Initialize
  initTheme();
  updateDownloadButtonLabel();
})();
