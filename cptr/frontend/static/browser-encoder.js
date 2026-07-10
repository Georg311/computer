(() => {
  const params = new URLSearchParams(location.hash.slice(1));
  let socket;
  let encoder;
  let reader;
  let paused = true;
  let forceKeyframe = true;
  let sequence = 0;
  let lastKeyframe = 0;
  let started = false;

  function sendError(error) {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'error', message: error?.message || String(error) }));
    }
  }

  function receiveControl(event) {
    if (typeof event.data !== 'string') return;
    const message = JSON.parse(event.data);
    if (message.type === 'pause') paused = true;
    if (message.type === 'resume') { paused = false; forceKeyframe = true; }
    if (message.type === 'keyframe') forceKeyframe = true;
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
      const stream = await navigator.mediaDevices.getDisplayMedia({
        audio: false,
        video: {
          width: { ideal: 1280, max: 1920 },
          height: { ideal: 720, max: 1080 },
          frameRate: { ideal: 30, max: 30 }
        },
        preferCurrentTab: false
      });
      const track = stream.getVideoTracks()[0];
      await track.applyConstraints({
        width: { ideal: 1280, max: 1920 },
        height: { ideal: 720, max: 1080 },
        frameRate: { ideal: 30, max: 30 }
      });
      reader = new MediaStreamTrackProcessor({ track }).readable.getReader();
      const first = await reader.read();
      if (first.done || !first.value) throw new Error('Chrome tab capture returned no video');
      const width = first.value.codedWidth;
      const height = first.value.codedHeight;
      const config = {
        codec: 'avc1.42E028',
        width,
        height,
        bitrate: Math.max(1_000_000, Math.min(6_000_000, Math.round(width * height * 4.5))),
        framerate: 30,
        hardwareAcceleration: 'prefer-hardware',
        latencyMode: 'realtime',
        avc: { format: 'annexb' }
      };
      const support = await VideoEncoder.isConfigSupported(config);
      if (!support.supported) throw new Error(`H.264 WebCodecs encoding is unavailable at ${width}×${height}`);
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
      socket.send(JSON.stringify({ type: 'config', codec: config.codec, width, height }));
      paused = false;

      let frame = first.value;
      while (frame) {
        if (!paused && encoder.encodeQueueSize <= 2) {
          const now = performance.now();
          const keyFrame = forceKeyframe || now - lastKeyframe >= 2000;
          encoder.encode(frame, { keyFrame });
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
    encoder?.close();
  });
})();
