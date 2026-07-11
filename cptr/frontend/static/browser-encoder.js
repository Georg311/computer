(() => {
  const params = new URLSearchParams(location.hash.slice(1));
  const windowCapture = params.get('window') === '1';
  const audioEnabled = params.get('audio') === '1';
  let socket;
  let encoder;
  let audioEncoder;
  let reader;
  let audioReader;
  let videoTrack;
  let paused = true;
  let forceKeyframe = true;
  let sequence = 0;
  let audioSequence = 0;
  let lastKeyframe = 0;
  let started = false;
  let configured = '';
  let resolveInitialQuality;
  const initialQuality = new Promise(resolve => { resolveInitialQuality = resolve; });
  let quality = { max_height: 1080, bitrate: 12_000_000, device_scale_factor: 1 };

  function sendError(error) {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'error', message: error?.message || String(error) }));
    }
  }

  function normalizedQuality(value) {
    const maxHeight = Math.max(240, Math.min(1080, Number(value?.max_height) || 1080));
    const bitrate = Math.max(1_000_000, Math.min(12_000_000, Number(value?.bitrate) || 12_000_000));
    return { max_height: Math.round(maxHeight), bitrate: Math.round(bitrate), device_scale_factor: value?.device_scale_factor === 2 ? 2 : 1 };
  }

  async function applyQuality() {
    if (!videoTrack) return;
    try {
      await videoTrack.applyConstraints({
        height: { ideal: quality.max_height, max: quality.max_height },
        frameRate: { ideal: 30, max: 30 }
      });
      configured = '';
      forceKeyframe = true;
    } catch {
      // Keep the last live capture constraints if a browser rejects a dynamic resize.
    }
  }

  function receiveControl(event) {
    if (typeof event.data !== 'string') return;
    const message = JSON.parse(event.data);
    if (message.type === 'pause') paused = true;
    if (message.type === 'resume') { paused = false; forceKeyframe = true; }
    if (message.type === 'keyframe') forceKeyframe = true;
    if (message.type === 'resize') forceKeyframe = true;
    if (message.type === 'quality') {
      quality = normalizedQuality(message);
      resolveInitialQuality?.();
      resolveInitialQuality = undefined;
      void applyQuality();
    }
  }

  function crop(frame) {
    if (!windowCapture) return { x: 0, y: 0, width: frame.codedWidth, height: frame.codedHeight };
    const scaleX = frame.codedWidth / Math.max(1, outerWidth);
    const scaleY = frame.codedHeight / Math.max(1, outerHeight);
    const width = Math.max(2, Math.min(frame.codedWidth, Math.floor(innerWidth * scaleX / 2) * 2));
    const height = Math.max(2, Math.min(frame.codedHeight, Math.floor(innerHeight * scaleY / 2) * 2));
    return {
      x: Math.max(0, Math.floor((frame.codedWidth - width) / 2)),
      y: Math.max(0, frame.codedHeight - height),
      width,
      height
    };
  }

  async function configure(width, height) {
    const key = `${width}x${height}:${quality.bitrate}`;
    if (configured === key) return;
    const config = {
      codec: 'avc1.42E028',
      width,
      height,
      bitrate: quality.bitrate,
      framerate: 30,
      hardwareAcceleration: 'prefer-hardware',
      latencyMode: 'realtime',
      avc: { format: 'annexb' }
    };
    const support = await VideoEncoder.isConfigSupported(config);
    if (!support.supported) throw new Error(`H.264 WebCodecs encoding is unavailable at ${width}×${height}`);
    encoder?.close();
    encoder = new VideoEncoder({
      error: sendError,
      output(chunk) {
        if (socket.readyState !== WebSocket.OPEN) return;
        const payload = new ArrayBuffer(14 + chunk.byteLength);
        const view = new DataView(payload);
        view.setUint8(0, 1);
        view.setUint8(1, chunk.type === 'key' ? 1 : 0);
        view.setUint32(2, sequence++);
        view.setBigUint64(6, BigInt(Math.max(0, chunk.timestamp)));
        chunk.copyTo(new Uint8Array(payload, 14));
        socket.send(payload);
      }
    });
    encoder.configure(config);
    configured = key;
    socket.send(JSON.stringify({ type: 'config', codec: config.codec, width, height }));
    forceKeyframe = true;
  }

  async function startAudio(stream) {
    const track = stream.getAudioTracks()[0];
    if (!track || !window.AudioEncoder) return;
    const settings = track.getSettings();
    const config = {
      codec: 'opus',
      sampleRate: settings.sampleRate || 48000,
      numberOfChannels: settings.channelCount || 1,
      bitrate: (settings.channelCount || 1) > 1 ? 128000 : 64000
    };
    const support = await AudioEncoder.isConfigSupported(config);
    if (!support.supported) return;
    audioEncoder = new AudioEncoder({
      error() {},
      output(chunk) {
        if (!paused && socket.readyState === WebSocket.OPEN) {
          const payload = new ArrayBuffer(14 + chunk.byteLength);
          const view = new DataView(payload);
          view.setUint8(0, 2);
          view.setUint8(1, 0);
          view.setUint32(2, audioSequence++);
          view.setBigUint64(6, BigInt(Math.max(0, chunk.timestamp)));
          chunk.copyTo(new Uint8Array(payload, 14));
          socket.send(payload);
        }
      }
    });
    audioEncoder.configure(config);
    socket.send(JSON.stringify({ type: 'audio_config', codec: config.codec, sampleRate: config.sampleRate, numberOfChannels: config.numberOfChannels }));
    audioReader = new MediaStreamTrackProcessor({ track }).readable.getReader();
    while (true) {
      const next = await audioReader.read();
      if (next.done || !next.value) break;
      if (!paused && audioEncoder.encodeQueueSize <= 8) audioEncoder.encode(next.value);
      next.value.close();
    }
  }

  window.startCapture = async () => {
    if (started) return;
    started = true;
    try {
      socket = new WebSocket(`${params.get('ws')}?token=${encodeURIComponent(params.get('token') || '')}`);
      socket.binaryType = 'arraybuffer';
      socket.addEventListener('message', receiveControl);
      const opened = new Promise((resolve, reject) => {
        socket.addEventListener('open', resolve, { once: true });
        socket.addEventListener('error', reject, { once: true });
      });
      await opened;
      if (!window.VideoEncoder || !window.MediaStreamTrackProcessor) {
        throw new Error('This Chrome version does not support WebCodecs tab encoding');
      }
      await Promise.race([initialQuality, new Promise(resolve => setTimeout(resolve, 250))]);
      const stream = await navigator.mediaDevices.getDisplayMedia({
        audio: audioEnabled ? { suppressLocalAudioPlayback: true } : false,
        video: {
          ...(windowCapture ? { displaySurface: 'window' } : {}),
          height: { ideal: quality.max_height, max: quality.max_height },
          frameRate: { ideal: 30, max: 30 }
        },
        preferCurrentTab: false,
        ...(windowCapture ? { selfBrowserSurface: 'include', surfaceSwitching: 'exclude' } : {})
      });
      videoTrack = stream.getVideoTracks()[0];
      if (windowCapture && videoTrack.getSettings().displaySurface !== 'window') {
        videoTrack.stop();
        throw new Error('Select the Open WebUI Computer Browser window');
      }
      await applyQuality();
      reader = new MediaStreamTrackProcessor({ track: videoTrack }).readable.getReader();
      const first = await reader.read();
      if (first.done || !first.value) throw new Error('Chrome tab capture returned no video');
      let rect = crop(first.value);
      await configure(rect.width, rect.height);
      paused = false;
      if (audioEnabled) void startAudio(stream);

      let frame = first.value;
      while (frame) {
        const nextRect = crop(frame);
        if (nextRect.width !== rect.width || nextRect.height !== rect.height) rect = nextRect;
        if (!paused && encoder.encodeQueueSize <= 2) {
          const now = performance.now();
          const keyFrame = forceKeyframe || now - lastKeyframe >= 2000;
          const encoded = windowCapture
            ? new VideoFrame(frame, { visibleRect: rect, displayWidth: rect.width, displayHeight: rect.height })
            : frame;
          await configure(rect.width, rect.height);
          encoder.encode(encoded, { keyFrame });
          if (encoded !== frame) encoded.close();
          if (keyFrame) { forceKeyframe = false; lastKeyframe = now; }
        }
        frame.close();
        const next = await reader.read();
        frame = next.done ? null : next.value;
      }
    } catch (error) {
      sendError(error);
      throw error;
    }
  };

  addEventListener('beforeunload', () => {
    reader?.cancel();
    audioReader?.cancel();
    encoder?.close();
    audioEncoder?.close();
  });
})();
