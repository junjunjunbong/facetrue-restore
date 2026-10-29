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
    queued: 'Queued', running: 'Restoring', preprocessing: 'Preparing video',
    preprocess: 'Preparing video', without: 'Restoring without photo', with: 'Restoring with photo',
    without_reference: 'Restoring without photo', with_reference: 'Restoring with photo',
    stitch: 'Stitching windows', stitching: 'Stitching windows',
    export: 'Exporting comparison', exporting: 'Exporting comparison',
    succeeded: 'Done', failed: 'The job did not finish',
  };

  function safeUrl(value) {
    if (typeof value !== 'string' || !value) throw new Error('The server did not return a file URL.');
    const url = new URL(value, window.location.href);
    if (url.origin !== window.location.origin || !['http:', 'https:'].includes(url.protocol)) {
      throw new Error('Only file URLs from this app can be opened.');
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
      try { data = await response.json(); } catch { throw new Error(`Could not read the server response. (HTTP ${response.status})`); }
      if (!response.ok) {
        const detail = data.detail ?? data.error ?? data.message;
        const text = typeof detail === 'string' ? detail : Array.isArray(detail)
          ? detail.map((item) => item.msg || 'Please check the input.').join(' ') : '';
        const error = new Error(text || `The request failed. (HTTP ${response.status})`);
        error.status = response.status;
        throw error;
      }
      return data;
    } catch (error) {
      if (controller.signal.aborted && !signal?.aborted) throw new Error('The server timed out. Check the connection and whether it is running.');
      if (error instanceof TypeError) throw new Error('Could not reach the server. Check that the app server is running.');
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
    setText('runLabel', state.busy.job ? 'Restoring…' : state.busy.canvas ? 'Preparing canvas' : 'Create comparison');
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
    setText('playButton', 'Play');
    $('playButton').setAttribute('aria-label', 'Play all three videos');
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
    setText('canvasState', 'Photo + face position');
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
    setText('photoStatus', state.upload ? 'Choose a real photo taken at a different time than the video.' : 'Upload the source video first.');
  }

  function imageFrom(url) {
    const checked = safeUrl(url);
    return new Promise((resolve, reject) => {
      const img = new Image();
      const timer = window.setTimeout(() => reject(new Error('The image preview timed out. Please try again.')), 20000);
      img.onload = () => { window.clearTimeout(timer); resolve(img); };
      img.onerror = () => { window.clearTimeout(timer); reject(new Error('Could not load the image preview. Please upload again.')); };
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
    setText('frameHint', 'Face selected · adjust the region below');
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
      setText('photoStatus', detected ? 'Cropping the selected face from the reference photo.' : 'Cropping the position you set. Make sure the face fits.');
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
    if (file.size > MAX_UPLOAD) { showError(new Error('Videos must be 256 MB or smaller.')); return; }
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
    setText('videoStatus', 'Uploading the video and preparing the first frame…');
    updateUI();
    try {
      const form = new FormData();
      form.append('video', file);
      form.append('deinterlace', String($('deinterlace').checked));
      const data = await api('/api/uploads', { method: 'POST', body: form, timeout: 120000 });
      if (!data.upload_id || !Number.isFinite(data.width) || !Number.isFinite(data.height) || data.width < 8 || data.height < 8) {
        throw new Error('The upload response has no video info.');
      }
      const img = await imageFrom(data.frame_url);
      state.upload = { ...data, faces: faceList(data) };
      state.frameImage = img;
      $('videoPlaceholder').hidden = true;
      $('frameView').hidden = false;
      $('replaceVideo').hidden = false;
      $('videoMetadata').hidden = false;
      setText('videoFilename', file.name);
      setText('videoStats', `${data.width} × ${data.height} · ${data.fps} fps · ${Number(data.duration).toFixed(2)} s`);
      setText('videoStatus', state.upload.faces.length ? `${state.upload.faces.length} face(s) detected. Click the one person to restore.` : 'No face found automatically. Click the face, then fit the region by hand.');
      setText('frameHint', 'Click the face to restore');
      setText('photoStatus', 'Choose a real photo taken at a different time than the video.');
      renderSelection('frame');
    } catch (error) {
      setText('videoStatus', 'Could not prepare the video. Check the file and the connection.');
      showError(error);
    } finally {
      state.busy.video = false;
      $('videoInput').value = '';
      updateUI();
    }
  }

  async function uploadPhoto(file) {
    if (!file || state.busy.photo || state.busy.job || state.busy.video) return;
    if (!state.upload) { showError(new Error('Upload the source video first.')); return; }
    if (file.size > 25 * 1024 * 1024) { showError(new Error('Photos must be 25 MB or smaller.')); return; }
    hideError();
    clearPhoto();
    resetResults();
    state.busy.photo = true;
    const uploadId = state.upload.upload_id;
    setText('photoStatus', 'Uploading the photo and finding the face…');
    updateUI();
    try {
      const form = new FormData(); form.append('photo', file);
      const data = await api(`/api/uploads/${encodeURIComponent(uploadId)}/photo`, { method: 'POST', body: form, timeout: 60000 });
      if (!data.photo_id || !Number.isFinite(data.width) || !Number.isFinite(data.height) || data.width < 8 || data.height < 8) {
        throw new Error('The upload response has no photo info.');
      }
      const img = await imageFrom(data.photo_url);
      if (state.upload?.upload_id !== uploadId) return;
      state.photo = { ...data, faces: faceList(data) };
      state.photoImage = img;
      state.photoBox = state.photo.faces.length === 1 ? { ...state.photo.faces[0] }
        : state.photo.faces.length > 1 ? null : defaultBox(data.width / 2, data.height / 2, data, true);
      setText('photoStatus', state.photo.faces.length === 1 ? 'Selected 1 face automatically. Click to adjust the crop.'
        : state.photo.faces.length > 1 ? `Found ${state.photo.faces.length} faces. Click the one to use.`
        : 'Using a center crop. Click the face to use to adjust it.');
      $('photoPlaceholder').hidden = true;
      $('photoView').hidden = false;
      $('replacePhoto').hidden = false;
      renderSelection('photo');
      scheduleCanvas();
    } catch (error) {
      setText('photoStatus', 'Could not prepare the photo. Try a different photo.');
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
      if (state.photo && !state.box) setText('canvasState', 'Select a face in the video');
      else if (state.photo && !state.photoBox) setText('canvasState', 'Select the face to use in the photo');
      updateUI();
      return;
    }
    const version = state.canvasVersion;
    state.busy.canvas = true;
    setText('canvasState', 'Preparing canvas…');
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
      if (!data.reference_id) throw new Error('The server could not build the reference canvas.');
      const previewUrl = safeUrl(data.canvas_url);
      await imageFrom(previewUrl);
      if (version !== state.canvasVersion) return;
      state.reference = data;
      $('referencePreview').src = previewUrl;
      $('referencePreview').hidden = false;
      $('canvasPlaceholder').hidden = true;
      setText('canvasState', 'Ready');
      $('retryCanvas').hidden = true;
    } catch (error) {
      if (version !== state.canvasVersion || controller.signal.aborted) return;
      setText('canvasState', 'Failed');
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
      showError(new Error('Seed must be an integer from 0 to 4294967295.')); $('seed').focus(); return;
    }
    hideError(); resetResults(); stopPolling();
    state.busy.job = true;
    state.pollErrors = 0;
    const version = ++state.jobVersion;
    $('progressSection').hidden = false;
    $('jobProgress').value = 0;
    setText('progressPercent', '0%');
    setText('progressTitle', 'Submitting job');
    setText('progressMessage', 'Requesting a restoration without the photo and one with it.');
    setText('jobId', '');
    updateUI();
    try {
      const data = await api('/api/jobs', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ upload_id: state.upload.upload_id, reference_id: state.reference.reference_id, seed,
          preset: $('preset').value, synthetic: $('synthetic').checked }),
      });
      if (!data.id) throw new Error('The server returned no job ID. Check the server before running again.');
      state.playbackFps = Number(state.upload.fps) || 24;
      rememberJob(String(data.id), { synthetic: $('synthetic').checked, fps: state.playbackFps });
      setText('jobId', `JOB ${data.id}`);
      pollJob(String(data.id), version);
      $('progressSection').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (error) {
      state.busy.job = false;
      setText('progressTitle', 'Could not confirm the job request');
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
      setText('progressTitle', stages[job.stage] || stages[job.status] || 'Checking progress');
      setText('progressMessage', job.message || 'Processing on the server. Keep this page open.');
      if (job.status === 'succeeded') {
        again = false; state.busy.job = false;
        await showResults(job);
      } else if (job.status === 'failed') {
        again = false; state.busy.job = false;
        const message = typeof job.error === 'string' ? job.error : job.message || 'The job failed on the server.';
        setText('progressTitle', 'The job did not finish');
        setText('progressMessage', message);
        showError(new Error(message));
      } else if (!['queued', 'running'].includes(job.status)) {
        throw new Error('The server returned an unknown job status.');
      }
    } catch (error) {
      if (version !== state.jobVersion || controller.signal.aborted) return;
      if (error.status === 404 || error.status === 410) {
        again = false;
        state.busy.job = false;
        rememberJob(null);
        setText('progressTitle', 'Previous job not found');
        setText('progressMessage', 'The server may have restarted or the job was deleted. Upload a video to start again.');
      } else if (!again) {
        setText('progressTitle', 'The job finished but the results could not be opened');
        setText('progressMessage', error.message); showError(error);
      } else {
        state.pollErrors += 1;
        delay = Math.min(15000, 3000 * state.pollErrors);
        setText('progressMessage', `Status check delayed. Retrying in ${Math.round(delay / 1000)} s. ${error.message}`);
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
      setText('playerStatus', 'Synced to the same frame.');
      syncPosition();
    });
  }

  function seekToFrame(value) {
    pauseVideos();
    state.seeking = true;
    state.seekTarget = Math.max(0, Math.min(state.duration - 1 / state.playbackFps,
      Math.round(value * state.playbackFps) / state.playbackFps));
    $('playButton').disabled = true;
    setText('playerStatus', 'Syncing the three videos…');
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
      setText('playButton', 'Pause');
      $('playButton').setAttribute('aria-label', 'Pause all three videos');
    } catch {
      pauseVideos();
      setText('playerStatus', 'The browser could not play them together. Play again or download the comparison MP4.');
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
    if (!['mock', 'comfy'].includes(state.resultMode)) throw new Error('Could not confirm the run mode of the results.');
    const mock = state.resultMode === 'mock';
    $('resultMockBadge').hidden = !mock;
    $('syntheticBadge').hidden = !$('synthetic').checked;
    setText('resultNotice', mock ? 'MOCK result. All three videos are input copies, not evidence that the photo improved likeness.' : 'Restorations are generated estimates. Check the face against the original\'s detail.');
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
    setText('progressTitle', mock ? 'MOCK comparison files ready' : 'Comparison files ready');
    setText('progressMessage', mock ? 'Created input copies. No AI restoration was run.' : 'Play the results and judge the reference photo\'s effect.');
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
      if (!['mock', 'comfy'].includes(config.mode)) throw new Error('Could not confirm the app mode.');
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
        setText('progressTitle', 'Checking previous job');
        updateUI();
        pollJob(id, ++state.jobVersion);
      }
    } catch (error) {
      setText('modeBadge', 'Check connection');
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
      pauseVideos(); setText('playerStatus', 'The browser could not read the videos. Download the MP4 to view them.');
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
    setText('muteButton', videos[0].muted ? 'Unmute' : 'Mute');
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
