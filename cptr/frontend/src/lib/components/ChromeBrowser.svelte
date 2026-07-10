<script lang="ts">
	import { onDestroy, onMount } from 'svelte';

	interface BrowserState {
		url: string;
		title: string;
		can_go_back: boolean;
		can_go_forward: boolean;
	}

	interface Props {
		sessionId: string;
		active: boolean;
		onstate: (state: BrowserState) => void;
		onstatus: (status: string, message?: string, mode?: 'proxy') => void;
	}

	let { sessionId, active, onstate, onstatus }: Props = $props();
	let canvas: HTMLCanvasElement;
	let container: HTMLDivElement;
	let socket: WebSocket | undefined;
	let decoder: VideoDecoder | undefined;
	let observer: ResizeObserver | undefined;
	let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
	let reconnectAttempt = 0;
	let disposed = false;
	let viewport = { width: 1280, height: 720 };
	let pendingPointer: Record<string, unknown> | undefined;
	let pointerFrame = 0;
	let controller = false;
	let hasFrame = false;
	const pressedKeys = new Map<string, Record<string, unknown>>();

	function send(message: Record<string, unknown>) {
		if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message));
	}

	function connect() {
		if (disposed) return;
		hasFrame = false;
		onstatus('connecting');
		const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
		socket = new WebSocket(`${scheme}://${location.host}/api/browser/sessions/${sessionId}/stream`);
		socket.binaryType = 'arraybuffer';
		socket.onopen = () => {
			reconnectAttempt = 0;
			send({ type: 'visibility', visible: active });
			resize();
		};
		socket.onmessage = receive;
		socket.onclose = () => {
			if (disposed) return;
			onstatus('lost', 'Chrome connection lost');
			const delays = [1000, 2000, 5000];
			reconnectTimer = setTimeout(connect, delays[Math.min(reconnectAttempt++, delays.length - 1)]);
		};
	}

	function receive(event: MessageEvent) {
		if (typeof event.data === 'string') {
			const message = JSON.parse(event.data);
			if (message.type === 'ready') controller = message.controller === true;
			if (message.type === 'state') onstate(message);
			if (message.type === 'status' && (message.status !== 'playing' || hasFrame))
				onstatus(message.status, message.message, message.mode);
			if (message.type === 'config') configureDecoder(message);
			return;
		}
		if (!(event.data instanceof ArrayBuffer) || event.data.byteLength < 14 || !decoder) return;
		const view = new DataView(event.data);
		if (view.getUint8(0) !== 1 || decoder.state !== 'configured') return;
		try {
			decoder.decode(
				new EncodedVideoChunk({
					type: view.getUint8(1) & 1 ? 'key' : 'delta',
					timestamp: Number(view.getBigUint64(6)),
					data: new Uint8Array(event.data, 14)
				})
			);
		} catch {
			send({ type: 'request_keyframe' });
		}
	}

	function configureDecoder(config: { codec: string; width: number; height: number }) {
		decoder?.close();
		decoder = new VideoDecoder({
			output(frame) {
				if (!canvas) return frame.close();
				canvas.width = frame.displayWidth;
				canvas.height = frame.displayHeight;
				canvas.getContext('2d', { alpha: false })?.drawImage(frame, 0, 0);
				frame.close();
				if (!hasFrame) {
					hasFrame = true;
					onstatus(controller ? 'playing' : 'view_only');
				}
			},
			error() {
				send({ type: 'request_keyframe' });
			}
		});
		decoder.configure({ codec: config.codec, optimizeForLatency: true });
	}

	function resize() {
		if (!container) return;
		const rect = container.getBoundingClientRect();
		viewport = {
			width: Math.max(320, Math.min(1920, Math.round(rect.width))),
			height: Math.max(240, Math.min(1080, Math.round(rect.height)))
		};
		send({ type: 'viewport', ...viewport });
	}

	function modifiers(event: MouseEvent | KeyboardEvent | WheelEvent) {
		return (
			(event.altKey ? 1 : 0) |
			(event.ctrlKey ? 2 : 0) |
			(event.metaKey ? 4 : 0) |
			(event.shiftKey ? 8 : 0)
		);
	}

	function coordinates(event: MouseEvent | PointerEvent | WheelEvent) {
		const rect = canvas.getBoundingClientRect();
		return {
			x: (event.clientX - rect.left) / rect.width,
			y: (event.clientY - rect.top) / rect.height,
			normalized: true
		};
	}

	function button(value: number) {
		return value === 0 ? 'left' : value === 1 ? 'middle' : value === 2 ? 'right' : 'none';
	}

	function pointer(event: PointerEvent, type: 'move' | 'down' | 'up') {
		if (type === 'down') {
			canvas.focus();
			canvas.setPointerCapture(event.pointerId);
		}
		const message = {
			type: 'pointer',
			event: type,
			...coordinates(event),
			button: type === 'move' ? 'none' : button(event.button),
			buttons: event.buttons,
			click_count: event.detail || 1,
			modifiers: modifiers(event)
		};
		if (type !== 'move') return send(message);
		pendingPointer = message;
		if (!pointerFrame) {
			pointerFrame = requestAnimationFrame(() => {
				if (pendingPointer) send(pendingPointer);
				pendingPointer = undefined;
				pointerFrame = 0;
			});
		}
	}

	function wheel(event: WheelEvent) {
		event.preventDefault();
		send({
			type: 'wheel',
			...coordinates(event),
			delta_x: event.deltaX,
			delta_y: event.deltaY,
			modifiers: modifiers(event)
		});
	}

	function key(event: KeyboardEvent, type: 'keyDown' | 'keyUp') {
		event.preventDefault();
		event.stopPropagation();
		const message = {
			type: 'key',
			event: type,
			key: event.key,
			code: event.code,
			text:
				type === 'keyDown' &&
				event.key.length === 1 &&
				!event.altKey &&
				!event.ctrlKey &&
				!event.metaKey
					? event.key
					: '',
			modifiers: modifiers(event),
			auto_repeat: event.repeat,
			location: event.location,
			is_keypad: event.location === KeyboardEvent.DOM_KEY_LOCATION_NUMPAD,
			windows_virtual_key_code: event.keyCode
		};
		if (type === 'keyDown') pressedKeys.set(event.code, message);
		else pressedKeys.delete(event.code);
		send(message);
	}

	function releaseKeys() {
		for (const message of pressedKeys.values()) send({ ...message, event: 'keyUp', text: '' });
		pressedKeys.clear();
	}

	export function navigate(url: string) {
		send({ type: 'navigate', url });
	}
	export function back() {
		send({ type: 'back' });
	}
	export function forward() {
		send({ type: 'forward' });
	}
	export function reload() {
		send({ type: 'reload' });
	}

	$effect(() => {
		if (socket?.readyState === WebSocket.OPEN) {
			send({ type: 'visibility', visible: active });
			if (active) send({ type: 'request_keyframe' });
		}
	});

	onMount(() => {
		observer = new ResizeObserver(resize);
		observer.observe(container);
		connect();
	});

	onDestroy(() => {
		disposed = true;
		releaseKeys();
		observer?.disconnect();
		if (reconnectTimer) clearTimeout(reconnectTimer);
		if (pointerFrame) cancelAnimationFrame(pointerFrame);
		socket?.close();
		decoder?.close();
	});
</script>

<div class="chrome-container" bind:this={container}>
	<canvas
		bind:this={canvas}
		tabindex="0"
		onpointermove={(event) => pointer(event, 'move')}
		onpointerdown={(event) => pointer(event, 'down')}
		onpointerup={(event) => pointer(event, 'up')}
		onwheel={wheel}
		onkeydown={(event) => key(event, 'keyDown')}
		onkeyup={(event) => key(event, 'keyUp')}
		onblur={releaseKeys}
		onpaste={(event) => {
			event.preventDefault();
			event.stopPropagation();
			send({ type: 'paste', text: event.clipboardData?.getData('text/plain') || '' });
		}}
		oncontextmenu={(event) => event.preventDefault()}
	></canvas>
</div>

<style>
	.chrome-container,
	canvas {
		width: 100%;
		height: 100%;
		display: block;
		background: white;
	}
	canvas {
		outline: none;
		object-fit: fill;
		touch-action: none;
	}
</style>
