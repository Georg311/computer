/**
 * A Svelte action that detects horizontal swipe gestures.
 */
export function swipe(node: HTMLElement, options: { onSwipeLeft?: () => void; onSwipeRight?: () => void }) {
	let startX = 0;
	let endX = 0;

	const handleTouchStart = (e: TouchEvent) => {
		startX = e.changedTouches[0].clientX;
	};

	const handleTouchEnd = (e: TouchEvent) => {
		endX = e.changedTouches[0].clientX;
		const threshold = 50; // Minimum distance for a swipe

		if (startX - endX > threshold) {
			// Swipe Left
			options.onSwipeLeft?.();
		} else if (endX - startX > threshold) {
			// Swipe Right
			options.onSwipeRight?.();
		}
	};

	node.addEventListener('touchstart', handleTouchStart, { passive: true });
	node.addEventListener('touchend', handleTouchEnd, { passive: true });

	return {
		destroy() {
			node.removeEventListener('touchstart', handleTouchStart);
			node.removeEventListener('touchend', handleTouchEnd);
		}
	};
}
