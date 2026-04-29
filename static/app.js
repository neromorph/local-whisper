/**
 * Whisper Transcription App - Frontend Logic
 * Vanilla JS, no frameworks. Handles upload, URL transcription, and result display.
 */
(function () {
  'use strict';

  // ── Constants ──
  const MODE_UPLOAD = 'upload';
  const MODE_URL = 'url';
  const POLL_INTERVAL_MS = 1000;
  const MAX_POLL_MS = 35 * 60 * 1000; // 35 minutes

  // ── State ──
  const state = {
    mode: MODE_UPLOAD,
    file: null,
    jobId: null,
    pollTimer: null,
    pollStartTime: null,
    status: 'idle',
    segments: [],
    language: 'auto',
    duration: 0,
    allowedExtensions: [],
  };

  // ── DOM refs ──
  const els = {
    inputArea: document.getElementById('input-area'),
    progressArea: document.getElementById('progress-area'),
    resultArea: document.getElementById('result-area'),
    modeSwitcher: document.getElementById('mode-switcher'),
    modeUploadBtn: document.getElementById('mode-upload'),
    modeUrlBtn: document.getElementById('mode-url'),
    uploadZone: document.getElementById('upload-zone'),
    fileInput: document.getElementById('file-input'),
    fileInfo: document.getElementById('file-info'),
    urlSection: document.getElementById('url-section'),
    urlInput: document.getElementById('url-input'),
    metadataInfo: document.getElementById('metadata-info'),
    metaTitle: document.getElementById('meta-title'),
    metaDuration: document.getElementById('meta-duration'),
    metaUploader: document.getElementById('meta-uploader'),
    modelSelect: document.getElementById('model-select'),
    languageSelect: document.getElementById('language-select'),
    taskSelect: document.getElementById('task-select'),
    startBtn: document.getElementById('start-btn'),
    cancelBtn: document.getElementById('cancel-btn'),
    startOverBtn: document.getElementById('start-over-btn'),
    resetBtn: document.getElementById('reset-btn'),
    newTranscriptionBtn: document.getElementById('new-transcription-btn'),
    statusText: document.getElementById('status-text'),
    statusSpinner: document.getElementById('status-spinner'),
    progressWrapper: document.getElementById('progress-wrapper'),
    progressBar: document.getElementById('progress-bar'),
    progressPercent: document.getElementById('progress-percent'),
    errorText: document.getElementById('error-text'),
    transcriptArea: document.getElementById('transcript-area'),
    copyBtn: document.getElementById('copy-btn'),
    downloadTxtBtn: document.getElementById('download-txt-btn'),
    downloadSrtBtn: document.getElementById('download-srt-btn'),
  };

  // ── Helpers ──
  function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  function formatDuration(seconds) {
    if (!seconds || seconds <= 0) return '—';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  // ── SRT generation (client-side) ──
  function formatSrtTime(seconds) {
    const h = String(Math.floor(seconds / 3600)).padStart(2, '0');
    const m = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0');
    const sec = String(Math.floor(seconds % 60)).padStart(2, '0');
    const ms = String(Math.round((seconds % 1) * 1000)).padStart(3, '0');
    return `${h}:${m}:${sec},${ms}`;
  }

  function generateSrt(segments) {
    return segments
      .map((seg, i) =>
        `${i + 1}\n${formatSrtTime(seg.start)} --> ${formatSrtTime(seg.end)}\n${seg.text.trim()}\n`
      )
      .join('\n');
  }

  // ── View switching ──
  function showView(view) {
    els.inputArea.hidden = view !== 'input';
    els.progressArea.hidden = view !== 'progress';
    els.resultArea.hidden = view !== 'result';
  }

  // ── Settings persistence ──
  function loadSettings() {
    try {
      const saved = JSON.parse(localStorage.getItem('whisper_settings') || '{}');
      if (saved.model) els.modelSelect.value = saved.model;
      if (saved.language) els.languageSelect.value = saved.language;
      if (saved.task) els.taskSelect.value = saved.task;
      if (saved.mode === MODE_URL || saved.mode === MODE_UPLOAD) {
        switchMode(saved.mode);
      }
    } catch {
      // ignore parse errors
    }
  }

  function saveSettings() {
    const settings = {
      model: els.modelSelect.value,
      language: els.languageSelect.value,
      task: els.taskSelect.value,
      mode: state.mode,
    };
    localStorage.setItem('whisper_settings', JSON.stringify(settings));
  }

  // ── Mode Switching ──
  function switchMode(mode) {
    // If a URL job is in progress, abort polling and reset UI
    if (state.status === 'processing' || state.status === 'uploading') {
      stopPolling();
      if (state.jobId) {
        // Fire-and-forget cancel request to the backend
        fetch(`/jobs/${state.jobId}/cancel`, { method: 'POST' }).catch(() => {});
      }
      setStatus('idle', '');
      restoreStartButton();
    }

    state.mode = mode;
    els.modeUploadBtn.classList.toggle('active', mode === MODE_UPLOAD);
    els.modeUrlBtn.classList.toggle('active', mode === MODE_URL);

    if (mode === MODE_UPLOAD) {
      els.uploadZone.hidden = false;
      els.urlSection.hidden = true;
      els.cancelBtn.hidden = true;
      updateStartButtonState();
    } else {
      els.uploadZone.hidden = true;
      els.urlSection.hidden = false;
      els.cancelBtn.hidden = state.status === 'idle' || state.status === 'done' || state.status === 'error';
      updateStartButtonState();
    }
    saveSettings();
  }

  // ── File handling (upload mode) ──
  function handleFile(file) {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    const allowed = state.allowedExtensions.length
      ? state.allowedExtensions
      : ['mp3', 'wav', 'm4a', 'mp4', 'mkv', 'mov', 'webm', 'flac', 'ogg', 'aac', 'wma', 'aiff'];
    if (!allowed.includes(ext)) {
      setStatus('error', `Unsupported file type: .${ext}. Allowed: ${allowed.join(', ')}`);
      return;
    }
    state.file = file;
    els.fileInfo.textContent = `${file.name} (${formatBytes(file.size)})`;
    els.fileInfo.classList.add('has-file');
    updateStartButtonState();
    setStatus('idle', 'Ready to transcribe');
    saveSettings();
  }

  // ── Start button state ──
  function updateStartButtonState() {
    if (state.status === 'uploading' || state.status === 'processing') {
      els.startBtn.disabled = true;
      return;
    }
    if (state.mode === MODE_UPLOAD) {
      els.startBtn.disabled = !state.file;
    } else {
      const url = els.urlInput.value.trim();
      els.startBtn.disabled = !url;
    }
  }

  // ── Status management ──
  function setStatus(status, message) {
    state.status = status;
    els.statusText.textContent = message;
    els.errorText.hidden = true;
    els.errorText.textContent = '';

    const row = els.statusText.parentElement;
    row.classList.remove('active', 'error', 'success', 'cancelled');

    if (status === 'idle') {
      showView('input');
      els.statusSpinner.hidden = true;
      els.progressWrapper.hidden = true;
    } else if (status === 'uploading' || status === 'processing') {
      showView('progress');
      row.classList.add('active');
      els.statusSpinner.hidden = false;
      els.progressWrapper.hidden = false;
      els.cancelBtn.hidden = false;
      els.startOverBtn.hidden = true;
    } else if (status === 'done') {
      showView('result');
      row.classList.add('success');
      els.statusSpinner.hidden = true;
      els.progressWrapper.hidden = true;
    } else if (status === 'error') {
      showView('progress');
      row.classList.add('error');
      els.statusSpinner.hidden = true;
      els.progressWrapper.hidden = true;
      els.errorText.textContent = message;
      els.errorText.hidden = false;
      els.cancelBtn.hidden = true;
      els.startOverBtn.hidden = false;
    } else if (status === 'cancelled') {
      showView('progress');
      row.classList.add('cancelled');
      els.statusSpinner.hidden = true;
      els.progressWrapper.hidden = true;
      els.errorText.textContent = message;
      els.errorText.hidden = false;
      els.cancelBtn.hidden = true;
      els.startOverBtn.hidden = false;
    }
  }

  function updateProgress(percent, message) {
    const pct = Math.max(0, Math.min(100, Math.round(percent)));
    els.progressBar.value = pct;
    els.progressPercent.textContent = pct + '%';
    if (message) {
      els.statusText.textContent = message;
    }
  }

  // ── Reset ──
  function resetAll() {
    // Stop any active polling
    stopPolling();

    state.file = null;
    state.jobId = null;
    state.pollStartTime = null;
    state.segments = [];
    state.status = 'idle';
    localStorage.removeItem('active_job_id');

    els.fileInput.value = '';
    els.fileInfo.textContent = 'No file selected';
    els.fileInfo.classList.remove('has-file');

    els.urlInput.value = '';
    els.metadataInfo.hidden = true;
    els.metaTitle.textContent = '—';
    els.metaDuration.textContent = '—';
    els.metaUploader.textContent = '—';

    els.startBtn.disabled = state.mode === MODE_UPLOAD;
    els.startBtn.hidden = false;
    els.startBtn.removeAttribute('aria-busy');

    els.cancelBtn.hidden = true;
    els.startOverBtn.hidden = true;

    els.progressBar.value = 0;
    els.progressPercent.textContent = '0%';
    els.statusText.textContent = 'Ready';
    els.statusSpinner.hidden = true;
    els.progressWrapper.hidden = true;
    els.errorText.hidden = true;
    els.errorText.textContent = '';

    els.transcriptArea.value = '';

    showView('input');
  }

  // ── Upload transcription ──
  async function startUploadTranscription() {
    if (!state.file || state.status === 'uploading' || state.status === 'processing') return;

    setStatus('uploading', 'Uploading file...');
    els.startBtn.disabled = true;
    els.startBtn.setAttribute('aria-busy', 'true');
    els.transcriptArea.value = '';

    const formData = new FormData();
    formData.append('file', state.file);
    formData.append('model', els.modelSelect.value);
    formData.append('language', els.languageSelect.value);
    formData.append('task', els.taskSelect.value);

    try {
      setStatus('processing', 'Transcribing... This may take a while');
      const response = await fetch('/transcribe', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || `Server error: ${response.status}`);
      }

      if (!data.success) {
        throw new Error(data.detail || 'Transcription failed');
      }

      state.segments = data.segments || [];
      state.language = data.language || 'unknown';
      state.duration = data.duration || 0;

      els.transcriptArea.value = data.text || '';
      setStatus('done', `Done! Detected language: ${data.language}, Duration: ${data.duration}s`);

      saveSettings();
    } catch (err) {
      console.error(err);
      setStatus('error', err.message || 'An unexpected error occurred');
    } finally {
      els.startBtn.disabled = false;
      els.startBtn.removeAttribute('aria-busy');
    }
  }

  // ── URL transcription ──
  async function startUrlTranscription() {
    const url = els.urlInput.value.trim();
    if (!url || state.status === 'processing') return;

    setStatus('processing', 'Starting URL transcription...');
    updateProgress(0, 'Validating URL...');

    els.startBtn.disabled = true;
    els.startBtn.hidden = true;
    els.cancelBtn.hidden = false;
    els.startOverBtn.hidden = true;
    els.transcriptArea.value = '';
    els.metadataInfo.hidden = true;

    try {
      const response = await fetch('/transcribe/url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: url,
          model: els.modelSelect.value,
          language: els.languageSelect.value,
          task: els.taskSelect.value,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || `Server error: ${response.status}`);
      }

      if (!data.job_id) {
        throw new Error('No job ID returned from server');
      }

      state.jobId = data.job_id;
      localStorage.setItem('active_job_id', data.job_id);
      state.pollStartTime = Date.now();
      setStatus('processing', 'Job started...');
      startPolling(data.job_id);
      saveSettings();
    } catch (err) {
      console.error(err);
      setStatus('error', err.message || 'Failed to start URL transcription');
      restoreStartButton();
    }
  }

  // ── Refresh recovery ──
  async function tryResumeJob() {
    const jobId = localStorage.getItem('active_job_id');
    if (!jobId) return;

    try {
      const res = await fetch(`/jobs/${jobId}/status`);
      if (!res.ok) {
        // Job no longer exists (server restarted)
        localStorage.removeItem('active_job_id');
        return;
      }
      const data = await res.json();

      if (data.state === 'completed') {
        localStorage.removeItem('active_job_id');
        if (data.result) {
          state.segments = data.result.segments || [];
          state.language = data.result.language || 'unknown';
          state.duration = data.result.duration || 0;
          els.transcriptArea.value = data.result.text || '';
          setStatus('done', `Done! Detected language: ${data.result.language}, Duration: ${data.result.duration}s`);
        }
      } else if (data.state === 'error' || data.state === 'cancelled') {
        localStorage.removeItem('active_job_id');
        setStatus(data.state, data.error || data.message || 'Job ended');
      } else {
        // Still running — resume polling
        state.jobId = jobId;
        state.mode = MODE_URL;
        switchMode(MODE_URL);
        setStatus('processing', data.message || 'Resuming...');
        updateProgress(data.progress || 0, data.message);
        startPolling(jobId);
      }
    } catch {
      localStorage.removeItem('active_job_id');
    }
  }

  // ── Polling ──
  function startPolling(jobId) {
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
    }
    state.pollTimer = setInterval(() => pollJobStatus(jobId), POLL_INTERVAL_MS);
  }

  function stopPolling() {
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  async function pollJobStatus(jobId) {
    // Polling timeout guard
    if (state.pollStartTime && Date.now() - state.pollStartTime > MAX_POLL_MS) {
      stopPolling();
      setStatus('error', 'Transcription timed out. The job took too long to complete.');
      restoreStartButton();
      return;
    }

    try {
      const response = await fetch(`/jobs/${jobId}/status`);

      // 404 means the job no longer exists (server restart, eviction, etc.)
      if (response.status === 404) {
        stopPolling();
        setStatus('error', 'Job not found — the server may have restarted.');
        restoreStartButton();
        return;
      }

      if (!response.ok) {
        throw new Error(`Status check failed: ${response.status}`);
      }
      const data = await response.json();

      // Update progress
      updateProgress(data.progress || 0, data.message || '');

      // Show metadata if available
      if (data.metadata && data.metadata.title) {
        els.metadataInfo.hidden = false;
        els.metaTitle.textContent = data.metadata.title || '—';
        els.metaDuration.textContent = formatDuration(data.metadata.duration);
        els.metaUploader.textContent = data.metadata.uploader || '—';
      }

      if (data.state === 'completed') {
        stopPolling();
        if (data.result) {
          state.segments = data.result.segments || [];
          state.language = data.result.language || 'unknown';
          state.duration = data.result.duration || 0;
          els.transcriptArea.value = data.result.text || '';
          setStatus('done', `Done! Detected language: ${data.result.language}, Duration: ${data.result.duration}s`);
        } else {
          setStatus('error', 'Transcription completed but no result was returned');
        }
        restoreStartButton();
      } else if (data.state === 'error') {
        stopPolling();
        setStatus('error', data.error || data.message || 'Transcription failed');
        restoreStartButton();
      } else if (data.state === 'cancelled') {
        stopPolling();
        setStatus('cancelled', 'Transcription was cancelled.');
        restoreStartButton();
      }
      // Otherwise still processing; keep polling
    } catch (err) {
      console.error('Polling error:', err);
      // Don't stop polling on transient network errors
    }
  }

  function restoreStartButton() {
    els.startBtn.hidden = false;
    els.startBtn.disabled = false;
    els.startBtn.removeAttribute('aria-busy');
    els.cancelBtn.hidden = true;
    updateStartButtonState();
  }

  // ── Cancel ──
  async function cancelTranscription() {
    if (!state.jobId) return;

    els.cancelBtn.disabled = true;
    els.cancelBtn.textContent = 'Cancelling...';

    try {
      await fetch(`/jobs/${state.jobId}/cancel`, { method: 'POST' });
      // Polling will pick up the cancelled state
    } catch (err) {
      console.error('Cancel error:', err);
      els.cancelBtn.disabled = false;
      els.cancelBtn.textContent = 'Cancel';
    }
  }

  // ── Download helpers ──
  function downloadTextFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function downloadSrt() {
    if (!state.segments.length) return;
    const srtContent = generateSrt(state.segments);
    downloadTextFile(srtContent, 'transcript.srt', 'text/plain');
  }

  // ── Event listeners ──

  // Mode switching
  els.modeUploadBtn.addEventListener('click', () => switchMode(MODE_UPLOAD));
  els.modeUrlBtn.addEventListener('click', () => switchMode(MODE_URL));

  // Upload mode events
  els.uploadZone.addEventListener('click', () => els.fileInput.click());

  els.fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) handleFile(file);
  });

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((eventName) => {
    els.uploadZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
    });
  });

  ['dragenter', 'dragover'].forEach((eventName) => {
    els.uploadZone.addEventListener(eventName, () => {
      els.uploadZone.classList.add('drag-over');
    });
  });

  ['dragleave', 'drop'].forEach((eventName) => {
    els.uploadZone.addEventListener(eventName, () => {
      els.uploadZone.classList.remove('drag-over');
    });
  });

  els.uploadZone.addEventListener('drop', (e) => {
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  });

  // URL input events
  els.urlInput.addEventListener('input', () => {
    updateStartButtonState();
  });

  els.urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !els.startBtn.disabled && state.mode === MODE_URL) {
      startUrlTranscription();
    }
  });

  // Start / Cancel / Reset / Start Over / New Transcription buttons
  els.startBtn.addEventListener('click', () => {
    if (state.mode === MODE_UPLOAD) {
      startUploadTranscription();
    } else {
      startUrlTranscription();
    }
  });

  els.cancelBtn.addEventListener('click', cancelTranscription);
  els.resetBtn.addEventListener('click', resetAll);
  els.startOverBtn.addEventListener('click', resetAll);
  els.newTranscriptionBtn.addEventListener('click', resetAll);

  // Result actions
  els.copyBtn.addEventListener('click', async () => {
    const text = els.transcriptArea.value;
    if (!text) return;
    const originalText = els.copyBtn.textContent;
    try {
      await navigator.clipboard.writeText(text);
      els.copyBtn.textContent = 'Copied!';
    } catch {
      els.copyBtn.textContent = 'Failed';
    }
    setTimeout(() => {
      els.copyBtn.textContent = originalText;
    }, 2000);
  });

  els.downloadTxtBtn.addEventListener('click', () => {
    const text = els.transcriptArea.value;
    if (!text) return;
    downloadTextFile(text, 'transcript.txt', 'text/plain');
  });

  els.downloadSrtBtn.addEventListener('click', downloadSrt);

  // Settings persistence
  [els.modelSelect, els.languageSelect, els.taskSelect].forEach((sel) => {
    sel.addEventListener('change', saveSettings);
  });

  // Keyboard shortcut
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
      if (!els.startBtn.disabled && !els.startBtn.hidden) {
        if (state.mode === MODE_UPLOAD) {
          startUploadTranscription();
        } else {
          startUrlTranscription();
        }
      }
    }
  });

  // ── Fetch allowed extensions from backend ──
  async function fetchExtensions() {
    try {
      const res = await fetch('/extensions');
      const data = await res.json();
      if (data.extensions) {
        state.allowedExtensions = data.extensions;
      }
    } catch {
      // fallback to hardcoded list already in handleFile
    }
  }

  // ── Init ──
  loadSettings();
  fetchExtensions();
  updateStartButtonState();
  tryResumeJob();
})();
