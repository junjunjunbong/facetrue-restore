"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const state = {
    config: null, upload: null, photo: null, reference: null,
    frameImage: null, photoImage: null, box: null, photoBox: null, videoFile: null,
    busy: { video: false, photo: false, canvas: false, job: false },
    canvasVersion: 0, canvasTimer: null, canvasAbort: null,
    jobVersion: 0, pollTimer: null, pollAbort: null, pollErrors: 0,
    duration: 0, playing: false, seeking: false, seekTarget: 0, resultMode: null, playbackFps: 24,
  };
  const videos = [$('originalVideo'), $('withoutVideo'), $('withVideo')];
  const MAX_UPLOAD = 256 * 1024 * 1024;
  const stages = {
    queued: '작업 대기 중', running: '복원 중', preprocessing: '영상 준비 중',
    preprocess: '영상 준비 중', without: '사진 없이 복원 중', with: '사진을 넣고 복원 중',
    without_reference: '사진 없이 복원 중', with_reference: '사진을 넣고 복원 중',
    stitch: '클립을 이어 붙이는 중', stitching: '클립을 이어 붙이는 중',
    export: '비교 영상 내보내는 중', exporting: '비교 영상 내보내는 중',
    succeeded: '완료', failed: '작업을 완료하지 못했습니다',
  };

  function safeUrl(value) {
    if (typeof value !== 'string' || !value) throw new Error('서버가 파일 주소를 반환하지 않았습니다.');
    const url = new URL(value, window.location.href);
    if (url.origin !== window.location.origin || !['http:', 'https:'].includes(url.protocol)) {
      throw new Error('같은 앱의 파일 주소만 열 수 있습니다.');
    }
    return url.href;
  }

  async function api(path, options = {}) {
    const controller = new AbortController();
    const { timeout = 20000, signal, ...rest } = options;
    const abort = () => controller.abort();
    if (signal?.aborted) controller.abort();
    signal?.addEventListener('abort', abort, { once: true });
    const timer = window.setTimeout(abort, timeout);
    try {
      const response = await fetch(path, { ...rest, signal: controller.signal, credentials: 'same-origin' });
      let data;
      try { data = await response.json(); } catch { throw new Error(`서버 응답을 읽지 못했습니다. (HTTP ${response.status})`); }
      if (!response.ok) {
        const detail = data.detail ?? data.error ?? data.message;
        const text = typeof detail === 'string' ? detail : Array.isArray(detail)
          ? detail.map((item) => item.msg || '입력 값을 확인해 주세요.').join(' ') : '';
        const error = new Error(text || `요청을 처리하지 못했습니다. (HTTP ${response.status})`);
        error.status = response.status;
        throw error;
      }
      return data;
    } catch (error) {
      if (controller.signal.aborted && !signal?.aborted) throw new Error('서버 응답 시간이 초과되었습니다. 연결과 실행 상태를 확인해 주세요.');
      if (error instanceof TypeError) throw new Error('서버에 연결하지 못했습니다. 앱 서버가 실행 중인지 확인해 주세요.');
      throw error;
    } finally {
      window.clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
    }
  }

  function showError(error) {
    $('errorMessage').textContent = error instanceof Error ? error.message : String(error);
    $('errorBanner').hidden = false;
  }
  function hideError() { $('errorBanner').hidden = true; }
  function setText(id, value) { $(id).textContent = value; }
  function rememberJob(id, metadata = null) {
    try {
      if (id) {
        sessionStorage.setItem('facetrue-last-job', id);
        if (metadata) sessionStorage.setItem('facetrue-last-job-meta', JSON.stringify(metadata));
      } else {
        sessionStorage.removeItem('facetrue-last-job');
        sessionStorage.removeItem('facetrue-last-job-meta');
      }
    } catch { /* Storage may be disabled. */ }
  }
  function rememberedJob() {
    try { return sessionStorage.getItem('facetrue-last-job'); } catch { return null; }
  }

  function updateUI() {
    const locked = state.busy.job || state.busy.video;
    $('videoInput').disabled = locked;
    $('chooseVideo').disabled = locked;
    $('replaceVideo').disabled = locked;
    $('deinterlace').disabled = locked;
    $('photoInput').disabled = !state.upload || locked || state.busy.photo;
    $('choosePhoto').disabled = !state.upload || locked || state.busy.photo;
    $('replacePhoto').disabled = locked || state.busy.photo;
    $('bboxFields').disabled = !state.box || locked;
    ['seed', 'preset', 'synthetic'].forEach((id) => { $(id).disabled = state.busy.job; });
    const ready = state.config && state.upload && state.reference && state.box && state.photo;
    $('runButton').disabled = !ready || Object.values(state.busy).some(Boolean);
    setText('runLabel', state.busy.job ? '복원 진행 중' : state.busy.canvas ? '캔버스 준비 중' : '비교 영상 만들기');
    $('videoDrop').classList.toggle('busy', state.busy.video);
    $('photoDrop').classList.toggle('busy', state.busy.photo);
    $('stepOne').classList.toggle('active', !state.upload);
    $('stepOne').classList.toggle('complete', Boolean(state.upload));
    $('stepTwo').classList.toggle('active', Boolean(state.upload) && !state.reference);
    $('stepTwo').classList.toggle('complete', Boolean(state.reference));
    $('stepThree').classList.toggle('active', Boolean(state.reference) || state.busy.job);
  }

  function stopPolling() {
    window.clearTimeout(state.pollTimer);
    state.pollTimer = null;
    state.pollAbort?.abort();
    state.pollAbort = null;
  }

  function pauseVideos() {
    videos.forEach((video) => video.pause());
    state.playing = false;
    setText('playButton', '재생');
    $('playButton').setAttribute('aria-label', '세 영상을 함께 재생');
  }

  function resetResults() {
    pauseVideos();
    $('wipeVideo').pause();
    state.duration = 0;
    state.seeking = false;
    state.resultMode = null;
    $('resultsSection').hidden = true;
    $('resultReference').hidden = true;
    $('resultReferencePhoto').removeAttribute('src');
    $('progressSection').hidden = true;
    $('playButton').disabled = true;
    $('scrubber').disabled = true;
    videos.concat($('wipeVideo')).forEach((video) => { video.removeAttribute('src'); video.load(); });
    ['downloadSideBySide', 'downloadWipe', 'downloadManifest'].forEach((id) => $(id).removeAttribute('href'));
    rememberJob(null);
  }

  function clearReference() {
    state.canvasVersion += 1;
    window.clearTimeout(state.canvasTimer);
    state.canvasAbort?.abort();
    state.canvasAbort = null;
    state.reference = null;
    state.busy.canvas = false;
    $('referencePreview').hidden = true;
    $('referencePreview').removeAttribute('src');
    $('canvasPlaceholder').hidden = false;
    $('retryCanvas').hidden = true;
    setText('canvasState', '사진 + 얼굴 위치');
  }

  function clearPhoto() {
    clearReference();
    state.photo = null;
    state.photoImage = null;
    state.photoBox = null;
    $('photoView').hidden = true;
    $('photoPlaceholder').hidden = false;
    $('replacePhoto').hidden = true;
    $('photoInput').value = '';
    setText('photoStatus', state.upload ? '영상과 다른 시점에 찍은 실제 사진을 선택하세요.' : '먼저 원본 영상을 올려주세요.');
  }

  function imageFrom(url) {
    const checked = safeUrl(url);
    return new Promise((resolve, reject) => {
      const img = new Image();
      const timer = window.setTimeout(() => reject(new Error('이미지 미리보기의 응답 시간이 초과되었습니다. 다시 시도해 주세요.')), 20000);
      img.onload = () => { window.clearTimeout(timer); resolve(img); };
      img.onerror = () => { window.clearTimeout(timer); reject(new Error('이미지 미리보기를 불러오지 못했습니다. 다시 업로드해 주세요.')); };
      img.src = checked;
    });
  }

  function clampBox(box, size) {
    const width = Math.max(8, Math.min(size.width, Math.round(box.width)));
    const height = Math.max(8, Math.min(size.height, Math.round(box.height)));
    return {
      x: Math.max(0, Math.min(size.width - width, Math.round(box.x))),
      y: Math.max(0, Math.min(size.height - height, Math.round(box.y))),
      width, height,
    };
  }

  function faceList(data) {
    return (Array.isArray(data.faces) ? data.faces : []).filter((face) =>
      ['x', 'y', 'width', 'height'].every((key) => Number.isFinite(face[key])) && face.width > 0 && face.height > 0
    ).map((face) => clampBox(face, data));
  }

  function defaultBox(x, y, size, photo = false) {
    const width = Math.min(size.width, size.height) * (photo ? 0.68 : 0.27);
    const height = Math.min(size.height, width * 1.18);
    return clampBox({ x: x - width / 2, y: y - height / 2, width, height }, size);
  }

  function renderSelection(kind) {
    const isPhoto = kind === 'photo';
    const info = isPhoto ? state.photo : state.upload;
    const img = isPhoto ? state.photoImage : state.frameImage;
    const box = isPhoto ? state.photoBox : state.box;
    if (!info || !img) return;
    const canvas = isPhoto ? $('photoCanvas') : $('frameCanvas');
    const ratio = Math.min(1, 1280 / Math.max(info.width, info.height));
    canvas.width = Math.round(info.width * ratio);
    canvas.height = Math.round(info.height * ratio);
    const context = canvas.getContext('2d');
    context.scale(canvas.width / info.width, canvas.height / info.height);
    context.drawImage(img, 0, 0, info.width, info.height);
    const scale = info.width / canvas.width;
    if (!box) {
      context.strokeStyle = 'rgba(215,189,131,.7)';
      context.lineWidth = 2 * scale;
      context.setLineDash([7 * scale, 5 * scale]);
      info.faces.forEach((face) => context.strokeRect(face.x, face.y, face.width, face.height));
      return;
    }
    context.fillStyle = 'rgba(8,14,7,.45)';
    context.fillRect(0, 0, info.width, box.y);
    context.fillRect(0, box.y + box.height, info.width, info.height - box.y - box.height);
    context.fillRect(0, box.y, box.x, box.height);
    context.fillRect(box.x + box.width, box.y, info.width - box.x - box.width, box.height);
    context.strokeStyle = '#e9cc8e';
    context.lineWidth = 2 * scale;
    context.strokeRect(box.x, box.y, box.width, box.height);
    const corner = Math.min(box.width, box.height, 35 * scale) * 0.3;
    context.lineWidth = 4 * scale;
    [[box.x, box.y, 1, 1], [box.x + box.width, box.y, -1, 1],
      [box.x, box.y + box.height, 1, -1], [box.x + box.width, box.y + box.height, -1, -1]].forEach(([x, y, dx, dy]) => {
      context.beginPath(); context.moveTo(x + dx * corner, y); context.lineTo(x, y); context.lineTo(x, y + dy * corner); context.stroke();
    });
  }

  function syncBoxFields() {
    if (!state.upload || !state.box) return;
    const map = { bboxX: 'x', bboxY: 'y', bboxWidth: 'width', bboxHeight: 'height' };
    Object.entries(map).forEach(([id, key]) => { $(id).value = state.box[key]; });
    $('bboxX').max = state.upload.width - state.box.width;
    $('bboxY').max = state.upload.height - state.box.height;
    $('bboxWidth').max = state.upload.width;
    $('bboxHeight').max = state.upload.height;
    $('bboxFields').hidden = false;
    setText('frameHint', '선택한 얼굴 · 아래에서 영역 조정');
  }

  function selectionChanged(kind) {
    renderSelection(kind);
    if (kind === 'frame') syncBoxFields();
    resetResults();
    scheduleCanvas();
  }

  function clickCanvas(kind, event) {
    if (state.busy.job || state.busy.video || state.busy.photo) return;
    const photo = kind === 'photo';
    const info = photo ? state.photo : state.upload;
    if (!info) return;
    const canvas = photo ? $('photoCanvas') : $('frameCanvas');
    const rect = canvas.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width * info.width;
    const y = (event.clientY - rect.top) / rect.height * info.height;
    const detected = info.faces.filter((face) => x >= face.x && x <= face.x + face.width && y >= face.y && y <= face.y + face.height)
      .sort((a, b) => a.width * a.height - b.width * b.height)[0];
    const box = detected ? { ...detected } : defaultBox(x, y, info, photo);
    if (photo) {
      state.photoBox = box;
      setText('photoStatus', detected ? '선택한 얼굴을 참조 사진에서 크롭합니다.' : '직접 지정한 위치를 크롭합니다. 얼굴이 잘 들어오는지 확인하세요.');
    } else state.box = box;
    selectionChanged(kind);
  }

  function canvasKeys(kind, event) {
    if (state.busy.job || state.busy.video || state.busy.photo) return;
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Enter', ' '].includes(event.key)) return;
    const photo = kind === 'photo';
    const info = photo ? state.photo : state.upload;
    if (!info) return;
    event.preventDefault();
    let box = { ...(photo ? state.photoBox : state.box) || defaultBox(info.width / 2, info.height / 2, info, photo) };
    const step = event.altKey ? 1 : Math.max(2, Math.round(info.width / 200));
    const horizontal = event.key === 'ArrowLeft' || event.key === 'ArrowRight';
    const vertical = event.key === 'ArrowUp' || event.key === 'ArrowDown';
    const direction = ['ArrowLeft', 'ArrowUp'].includes(event.key) ? -1 : 1;
    if (horizontal) box[event.shiftKey ? 'width' : 'x'] += direction * step;
    if (vertical) box[event.shiftKey ? 'height' : 'y'] += direction * step;
    box = clampBox(box, info);
    if (photo) state.photoBox = box; else state.box = box;
    selectionChanged(kind);
  }

  async function uploadVideo(file) {
    if (!file || state.busy.video || state.busy.job) return;
    if (file.size > MAX_UPLOAD) { showError(new Error('영상은 256 MB 이하로 올려주세요.')); return; }
    hideError();
    state.busy.video = true;
    state.videoFile = file;
    state.upload = null;
    state.frameImage = null;
    state.box = null;
    clearPhoto();
    resetResults();
    $('frameView').hidden = true;
    $('videoPlaceholder').hidden = false;
    $('bboxFields').hidden = true;
    $('videoMetadata').hidden = true;
    $('replaceVideo').hidden = true;
    setText('videoStatus', '영상을 업로드하고 첫 프레임을 준비하고 있습니다…');
    updateUI();
    try {
      const form = new FormData();
      form.append('video', file);
      form.append('deinterlace', String($('deinterlace').checked));
      const data = await api('/api/uploads', { method: 'POST', body: form, timeout: 120000 });
      if (!data.upload_id || !Number.isFinite(data.width) || !Number.isFinite(data.height) || data.width < 8 || data.height < 8) {
        throw new Error('업로드 응답에 영상 정보가 없습니다.');
      }
      const img = await imageFrom(data.frame_url);
      state.upload = { ...data, faces: faceList(data) };
      state.frameImage = img;
      $('videoPlaceholder').hidden = true;
      $('frameView').hidden = false;
      $('replaceVideo').hidden = false;
      $('videoMetadata').hidden = false;
      setText('videoFilename', file.name);
      setText('videoStats', `${data.width} × ${data.height} · ${data.fps} fps · ${Number(data.duration).toFixed(2)}초`);
      setText('videoStatus', state.upload.faces.length ? `얼굴 ${state.upload.faces.length}개 감지. 복원할 한 사람의 얼굴을 클릭하세요.` : '자동으로 찾은 얼굴이 없습니다. 얼굴을 클릭한 뒤 영역을 직접 맞춰주세요.');
      setText('frameHint', '복원할 얼굴을 클릭하세요');
      setText('photoStatus', '영상과 다른 시점에 찍은 실제 사진을 선택하세요.');
      renderSelection('frame');
    } catch (error) {
      setText('videoStatus', '영상을 준비하지 못했습니다. 파일과 연결 상태를 확인해 주세요.');
      showError(error);
    } finally {
      state.busy.video = false;
      $('videoInput').value = '';
      updateUI();
    }
  }

  async function uploadPhoto(file) {
    if (!file || state.busy.photo || state.busy.job || state.busy.video) return;
    if (!state.upload) { showError(new Error('먼저 원본 영상을 올려주세요.')); return; }
    if (file.size > 25 * 1024 * 1024) { showError(new Error('사진은 25 MB 이하로 올려주세요.')); return; }
    hideError();
    clearPhoto();
    resetResults();
    state.busy.photo = true;
    const uploadId = state.upload.upload_id;
    setText('photoStatus', '사진을 업로드하고 얼굴을 확인하고 있습니다…');
    updateUI();
    try {
      const form = new FormData(); form.append('photo', file);
      const data = await api(`/api/uploads/${encodeURIComponent(uploadId)}/photo`, { method: 'POST', body: form, timeout: 60000 });
      if (!data.photo_id || !Number.isFinite(data.width) || !Number.isFinite(data.height) || data.width < 8 || data.height < 8) {
        throw new Error('업로드 응답에 사진 정보가 없습니다.');
      }
      const img = await imageFrom(data.photo_url);
      if (state.upload?.upload_id !== uploadId) return;
      state.photo = { ...data, faces: faceList(data) };
      state.photoImage = img;
      state.photoBox = state.photo.faces.length === 1 ? { ...state.photo.faces[0] }
        : state.photo.faces.length > 1 ? null : defaultBox(data.width / 2, data.height / 2, data, true);
      setText('photoStatus', state.photo.faces.length === 1 ? '얼굴 1개를 자동 선택했습니다. 클릭해서 크롭을 조정할 수 있습니다.'
        : state.photo.faces.length > 1 ? `얼굴 ${state.photo.faces.length}개를 찾았습니다. 사용할 얼굴을 클릭하세요.`
        : '중앙 크롭을 사용합니다. 사용할 얼굴을 클릭해서 조정하세요.');
      $('photoPlaceholder').hidden = true;
      $('photoView').hidden = false;
      $('replacePhoto').hidden = false;
      renderSelection('photo');
      scheduleCanvas();
    } catch (error) {
      setText('photoStatus', '사진을 준비하지 못했습니다. 다른 사진으로 다시 시도해 주세요.');
      showError(error);
    } finally {
      state.busy.photo = false;
      $('photoInput').value = '';
      updateUI();
    }
  }

  function scheduleCanvas() {
    clearReference();
    if (!state.upload || !state.photo || !state.box || !state.photoBox) {
      if (state.photo && !state.box) setText('canvasState', '영상에서 얼굴을 선택하세요');
      else if (state.photo && !state.photoBox) setText('canvasState', '사진에서 사용할 얼굴을 선택하세요');
      updateUI();
      return;
    }
    const version = state.canvasVersion;
    state.busy.canvas = true;
    setText('canvasState', '캔버스 준비 중…');
    updateUI();
    state.canvasTimer = window.setTimeout(() => buildCanvas(version), 350);
  }

  async function buildCanvas(version) {
    if (version !== state.canvasVersion || !state.upload || !state.photo || !state.box) return;
    const controller = new AbortController(); state.canvasAbort = controller;
    const body = { upload_id: state.upload.upload_id, photo_id: state.photo.photo_id, bbox: state.box };
    if (state.photoBox) body.photo_bbox = state.photoBox;
    try {
      const data = await api('/api/canvas', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: controller.signal });
      if (version !== state.canvasVersion) return;
      if (!data.reference_id) throw new Error('서버가 참조 캔버스를 만들지 못했습니다.');
      const previewUrl = safeUrl(data.canvas_url);
      await imageFrom(previewUrl);
      if (version !== state.canvasVersion) return;
      state.reference = data;
      $('referencePreview').src = previewUrl;
      $('referencePreview').hidden = false;
      $('canvasPlaceholder').hidden = true;
      setText('canvasState', '준비 완료');
      $('retryCanvas').hidden = true;
    } catch (error) {
      if (version !== state.canvasVersion || controller.signal.aborted) return;
      setText('canvasState', '생성 실패');
      $('retryCanvas').hidden = false;
      showError(error);
    } finally {
      if (version === state.canvasVersion) {
        state.busy.canvas = false;
        state.canvasAbort = null;
        updateUI();
      }
    }
  }

  async function runJob() {
    if ($('runButton').disabled || !state.upload || !state.reference) return;
    const seed = Number($('seed').value);
    if ($('seed').value.trim() === '' || !Number.isInteger(seed) || seed < 0 || seed > 4294967295) {
      showError(new Error('Seed는 0–4294967295 범위의 정수로 입력하세요.')); $('seed').focus(); return;
    }
    hideError(); resetResults(); stopPolling();
    state.busy.job = true;
    state.pollErrors = 0;
    const version = ++state.jobVersion;
    $('progressSection').hidden = false;
    $('jobProgress').value = 0;
    setText('progressPercent', '0%');
    setText('progressTitle', '작업 요청 중');
    setText('progressMessage', '사진 없는 복원과 사진을 넣은 복원을 요청합니다.');
    setText('jobId', '');
    updateUI();
    try {
      const data = await api('/api/jobs', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ upload_id: state.upload.upload_id, reference_id: state.reference.reference_id, seed,
          preset: $('preset').value, synthetic: $('synthetic').checked }),
      });
      if (!data.id) throw new Error('서버가 작업 ID를 반환하지 않았습니다. 중복 실행 전에 서버 상태를 확인하세요.');
      state.playbackFps = Number(state.upload.fps) || 24;
      rememberJob(String(data.id), { synthetic: $('synthetic').checked, fps: state.playbackFps });
      setText('jobId', `JOB ${data.id}`);
      pollJob(String(data.id), version);
      $('progressSection').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (error) {
      state.busy.job = false;
      setText('progressTitle', '작업 요청을 확인하지 못했습니다');
      setText('progressMessage', error.message);
      showError(error);
      updateUI();
    }
  }

  async function pollJob(id, version) {
    if (version !== state.jobVersion) return;
    const controller = new AbortController(); state.pollAbort = controller;
    let delay = 1500;
    let again = true;
    try {
      const job = await api(`/api/jobs/${encodeURIComponent(id)}`, { signal: controller.signal });
      if (version !== state.jobVersion) return;
      state.pollErrors = 0;
      const progress = Number.isFinite(job.progress) ? Math.max(0, Math.min(1, job.progress)) : 0;
      $('jobProgress').value = progress;
      setText('progressPercent', `${Math.round(progress * 100)}%`);
      setText('progressTitle', stages[job.stage] || stages[job.status] || '진행 상태 확인 중');
      setText('progressMessage', job.message || '서버에서 처리 중입니다. 페이지를 열어 두세요.');
      if (job.status === 'succeeded') {
        again = false; state.busy.job = false;
        await showResults(job);
      } else if (job.status === 'failed') {
        again = false; state.busy.job = false;
        const message = typeof job.error === 'string' ? job.error : job.message || '서버에서 작업이 실패했습니다.';
        setText('progressTitle', '작업을 완료하지 못했습니다');
        setText('progressMessage', message);
        showError(new Error(message));
      } else if (!['queued', 'running'].includes(job.status)) {
        throw new Error('서버가 알 수 없는 작업 상태를 반환했습니다.');
      }
    } catch (error) {
      if (version !== state.jobVersion || controller.signal.aborted) return;
      if (error.status === 404 || error.status === 410) {
        again = false;
        state.busy.job = false;
        rememberJob(null);
        setText('progressTitle', '이전 작업을 찾지 못했습니다');
        setText('progressMessage', '서버가 재시작되었거나 작업이 삭제되었을 수 있습니다. 새 영상을 올려 다시 시작할 수 있습니다.');
      } else if (!again) {
        setText('progressTitle', '작업은 끝났지만 결과를 열지 못했습니다');
        setText('progressMessage', error.message); showError(error);
      } else {
        state.pollErrors += 1;
        delay = Math.min(15000, 3000 * state.pollErrors);
        setText('progressMessage', `상태 확인이 지연되고 있습니다. ${Math.round(delay / 1000)}초 후 다시 확인합니다. ${error.message}`);
      }
    } finally {
      if (version === state.jobVersion) {
        state.pollAbort = null;
        updateUI();
        if (again) state.pollTimer = window.setTimeout(() => pollJob(id, version), delay);
      }
    }
  }

  function formatTime(value) {
    const t = Math.max(0, Number.isFinite(value) ? value : 0);
    return `${Math.floor(t / 60)}:${(t % 60).toFixed(2).padStart(5, '0')}`;
  }

  function refreshDuration() {
    const durations = videos.map((video) => video.duration);
    if (!durations.every((duration) => Number.isFinite(duration) && duration > 0)) return;
    state.duration = Math.min(...durations);
    $('scrubber').max = String(state.duration);
    $('scrubber').step = String(1 / state.playbackFps);
    $('scrubber').disabled = false;
    $('playButton').disabled = false;
    setText('totalTime', formatTime(state.duration));
  }

  function syncPosition() {
    if (state.seeking) return;
    const time = videos[0].currentTime;
    const tolerance = state.playing ? Math.max(0.06, 1.5 / state.playbackFps) : 0.01;
    videos.slice(1).forEach((video) => {
      if (video.readyState >= 1 && Math.abs(video.currentTime - time) > tolerance) video.currentTime = time;
    });
    $('scrubber').value = String(time);
    $('scrubber').setAttribute('aria-valuetext', `${formatTime(time)} / ${formatTime(state.duration)}`);
    setText('currentTime', formatTime(time));
    if (state.playing && state.duration && time >= state.duration - 0.025) pauseVideos();
  }

  function finishSeeking() {
    if (!state.seeking || videos.some(v => v.seeking || Math.abs(v.currentTime - state.seekTarget) > 0.002)) return;
    requestAnimationFrame(() => {
      if (videos.some(v => v.seeking || Math.abs(v.currentTime - state.seekTarget) > 0.002)) return;
      state.seeking = false;
      $('playButton').disabled = false;
      setText('playerStatus', '같은 프레임으로 맞췄습니다.');
      syncPosition();
    });
  }

  function seekToFrame(value) {
    pauseVideos();
    state.seeking = true;
    state.seekTarget = Math.max(0, Math.min(state.duration - 1 / state.playbackFps,
      Math.round(value * state.playbackFps) / state.playbackFps));
    $('playButton').disabled = true;
    setText('playerStatus', '세 영상의 프레임을 맞추는 중…');
    videos.forEach(video => { if (video.readyState >= 1) video.currentTime = state.seekTarget; });
    setText('currentTime', formatTime(state.seekTarget));
    finishSeeking();
  }

  async function playVideos() {
    if (!state.duration) return;
    hideError();
    if (videos[0].currentTime >= state.duration - 0.05) videos.forEach((video) => { video.currentTime = 0; });
    videos.slice(1).forEach((video) => { video.currentTime = videos[0].currentTime; });
    try {
      await Promise.all(videos.map((video) => video.play()));
      state.playing = true;
      setText('playButton', '일시정지');
      $('playButton').setAttribute('aria-label', '세 영상을 함께 일시정지');
    } catch {
      pauseVideos();
      setText('playerStatus', '브라우저에서 동시에 재생하지 못했습니다. 다시 재생하거나 비교 MP4를 다운로드하세요.');
    }
  }

  function switchView(view) {
    const isThree = view === 'three';
    if (isThree) $('wipeVideo').pause(); else pauseVideos();
    $('threeWayPanel').hidden = !isThree;
    $('wipePanel').hidden = isThree;
    $('threeWayTab').setAttribute('aria-selected', String(isThree));
    $('wipeTab').setAttribute('aria-selected', String(!isThree));
    $('threeWayTab').tabIndex = isThree ? 0 : -1;
    $('wipeTab').tabIndex = isThree ? -1 : 0;
  }

  async function showResults(job) {
    const outputs = job.outputs || {};
    const urls = {};
    for (const key of ['original', 'without', 'with', 'side_by_side', 'wipe', 'manifest']) urls[key] = safeUrl(outputs[key]);
    state.resultMode = job.mode || state.config?.mode;
    if (!['mock', 'comfy'].includes(state.resultMode)) throw new Error('결과의 실행 모드를 확인하지 못했습니다.');
    const mock = state.resultMode === 'mock';
    $('resultMockBadge').hidden = !mock;
    $('syntheticBadge').hidden = !$('synthetic').checked;
    setText('resultNotice', mock ? 'MOCK 결과입니다. 세 영상은 입력 복사본이며, 사진으로 닮음이 개선되었다는 증거가 아닙니다.' : '복원 결과는 생성된 추정입니다. 얼굴과 원본 영상의 세부를 함께 확인하세요.');
    if (state.photoImage && state.photoBox) {
      const crop = document.createElement('canvas');
      const b = state.photoBox;
      const scale = 160 / Math.max(b.width, b.height);
      crop.width = Math.max(1, Math.round(b.width * scale));
      crop.height = Math.max(1, Math.round(b.height * scale));
      crop.getContext('2d').drawImage(state.photoImage, b.x, b.y, b.width, b.height, 0, 0, crop.width, crop.height);
      $('resultReferencePhoto').src = crop.toDataURL('image/png');
      $('resultReference').hidden = false;
    } else $('resultReference').hidden = true;
    ['original', 'without', 'with'].forEach((key, index) => { videos[index].src = urls[key]; videos[index].load(); });
    $('wipeVideo').src = urls.wipe;
    $('wipeVideo').load();
    $('downloadSideBySide').href = urls.side_by_side;
    $('downloadWipe').href = urls.wipe;
    $('downloadManifest').href = urls.manifest;
    $('scrubber').value = '0';
    setText('currentTime', '0:00.00');
    setText('totalTime', '0:00.00');
    setText('playerStatus', '');
    switchView('three');
    $('resultsSection').hidden = false;
    $('jobProgress').value = 1;
    setText('progressPercent', '100%');
    setText('progressTitle', mock ? 'MOCK 비교 파일 준비 완료' : '비교 파일 준비 완료');
    setText('progressMessage', mock ? '입력 복사본을 생성했습니다. 실제 AI 복원은 실행하지 않았습니다.' : '결과를 재생하고 참조 사진의 효과를 확인하세요.');
    $('resultsSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function dropZone(id, handler) {
    const element = $(id);
    let entered = 0;
    element.addEventListener('dragenter', (event) => { event.preventDefault(); entered += 1; element.classList.add('dragging'); });
    element.addEventListener('dragover', (event) => { event.preventDefault(); if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'; });
    element.addEventListener('dragleave', () => { entered = Math.max(0, entered - 1); if (!entered) element.classList.remove('dragging'); });
    element.addEventListener('drop', (event) => {
      event.preventDefault(); entered = 0; element.classList.remove('dragging');
      const files = event.dataTransfer?.files;
      if (files?.length) handler(files[0]);
    });
  }

  async function initialize() {
    try {
      const config = await api('/api/config');
      if (!['mock', 'comfy'].includes(config.mode)) throw new Error('앱 실행 모드를 확인하지 못했습니다.');
      state.config = config;
      const mock = config.mode === 'mock';
      setText('modeBadge', mock ? 'MOCK MODE' : 'LTX · LOCAL');
      $('modeBadge').classList.toggle('mock', mock);
      $('modeBadge').classList.toggle('live', !mock);
      $('mockNotice').hidden = !mock;
      updateUI();
      const id = rememberedJob();
      if (id && /^[A-Za-z0-9_-]{1,120}$/.test(id)) {
        try {
          const metadata = JSON.parse(sessionStorage.getItem('facetrue-last-job-meta') || '{}');
          $('synthetic').checked = metadata.synthetic === true;
          if (Number.isFinite(metadata.fps) && metadata.fps >= 1 && metadata.fps <= 120) state.playbackFps = metadata.fps;
        } catch { /* Missing metadata does not fabricate a synthetic-source claim. */ }
        state.busy.job = true;
        $('progressSection').hidden = false;
        setText('jobId', `JOB ${id}`);
        setText('progressTitle', '이전 작업 확인 중');
        updateUI();
        pollJob(id, ++state.jobVersion);
      }
    } catch (error) {
      setText('modeBadge', '연결 확인 필요');
      showError(error);
      updateUI();
    }
  }

  $('dismissError').addEventListener('click', hideError);
  ['chooseVideo', 'replaceVideo'].forEach((id) => $(id).addEventListener('click', () => $('videoInput').click()));
  ['choosePhoto', 'replacePhoto'].forEach((id) => $(id).addEventListener('click', () => $('photoInput').click()));
  $('videoInput').addEventListener('change', (event) => uploadVideo(event.target.files[0]));
  $('photoInput').addEventListener('change', (event) => uploadPhoto(event.target.files[0]));
  $('deinterlace').addEventListener('change', () => { if (state.videoFile && state.upload) uploadVideo(state.videoFile); });
  dropZone('videoDrop', uploadVideo); dropZone('photoDrop', uploadPhoto);
  $('frameCanvas').addEventListener('click', (event) => clickCanvas('frame', event));
  $('photoCanvas').addEventListener('click', (event) => clickCanvas('photo', event));
  $('frameCanvas').addEventListener('keydown', (event) => canvasKeys('frame', event));
  $('photoCanvas').addEventListener('keydown', (event) => canvasKeys('photo', event));
  ['bboxX', 'bboxY', 'bboxWidth', 'bboxHeight'].forEach((id) => $(id).addEventListener('change', () => {
    if (!state.box || state.busy.job) return;
    const values = ['bboxX', 'bboxY', 'bboxWidth', 'bboxHeight'].map((name) => Number($(name).value));
    if (!values.every(Number.isFinite)) { syncBoxFields(); return; }
    state.box = clampBox({ x: values[0], y: values[1], width: values[2], height: values[3] }, state.upload);
    selectionChanged('frame');
  }));
  $('retryCanvas').addEventListener('click', scheduleCanvas);
  $('runButton').addEventListener('click', runJob);
  videos.forEach((video) => {
    video.addEventListener('loadedmetadata', refreshDuration);
    video.addEventListener('error', () => {
      if (!video.getAttribute('src')) return;
      pauseVideos(); setText('playerStatus', '영상을 브라우저에서 읽지 못했습니다. MP4 다운로드로 확인하세요.');
    });
  });
  videos[0].addEventListener('timeupdate', syncPosition);
  videos[0].addEventListener('seeked', syncPosition);
  videos.forEach(video => video.addEventListener('seeked', finishSeeking));
  videos[0].addEventListener('ended', pauseVideos);
  $('playButton').addEventListener('click', () => { if (state.playing) seekToFrame(videos[0].currentTime); else playVideos(); });
  $('scrubber').addEventListener('input', () => {
    seekToFrame(Number($('scrubber').value));
  });
  $('muteButton').addEventListener('click', () => {
    videos[0].muted = !videos[0].muted;
    setText('muteButton', videos[0].muted ? '음소거 해제' : '음소거');
  });
  $('threeWayTab').addEventListener('click', () => switchView('three'));
  $('wipeTab').addEventListener('click', () => switchView('wipe'));
  [$('threeWayTab'), $('wipeTab')].forEach((tab) => tab.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault(); const target = tab.id === 'threeWayTab' ? $('wipeTab') : $('threeWayTab');
    switchView(target.id === 'threeWayTab' ? 'three' : 'wipe'); target.focus();
  }));
  window.addEventListener('beforeunload', () => { stopPolling(); state.canvasAbort?.abort(); window.clearTimeout(state.canvasTimer); });
  updateUI();
  initialize();
})();
