"use client";

/**
 * 全局键盘快捷键 hook
 *
 * 用法：
 *   useKeyboardShortcuts({
 *     "Enter+ctrl": () => submit(),
 *     "Escape": () => close(),
 *   });
 */

import * as React from "react";

export type Shortcut = string; // e.g. "Enter+ctrl", "Escape", "k+meta"

function parse(s: string) {
	const parts = s.split("+").map((p) => p.trim().toLowerCase());
	const key = parts[parts.length - 1];
	const mods = new Set(parts.slice(0, -1));
	return {
		key,
		ctrl: mods.has("ctrl") || mods.has("control"),
		meta: mods.has("meta") || mods.has("cmd") || mods.has("command"),
		shift: mods.has("shift"),
		alt: mods.has("alt") || mods.has("option"),
	};
}

function match(e: KeyboardEvent, sc: ReturnType<typeof parse>) {
	if (e.key.toLowerCase() !== sc.key) return false;
	if (sc.ctrl !== e.ctrlKey) return false;
	if (sc.meta !== e.metaKey) return false;
	if (sc.shift !== e.shiftKey) return false;
	if (sc.alt !== e.altKey) return false;
	return true;
}

export function useKeyboardShortcuts(
	bindings: Partial<Record<Shortcut, (e: KeyboardEvent) => void>>,
	options: { enabled?: boolean; target?: HTMLElement | Window | Document } = {},
) {
	const enabled = options.enabled !== false;
	const target = (options.target as Window) ?? (typeof window !== "undefined" ? window : null);

	React.useEffect(() => {
		if (!enabled || !target) return;
		const handler = (e: KeyboardEvent) => {
			for (const [sc, cb] of Object.entries(bindings)) {
				if (!cb) continue;
				if (match(e, parse(sc))) {
					cb(e);
					break;
				}
			}
		};
		target.addEventListener("keydown", handler as EventListener);
		return () => target.removeEventListener("keydown", handler as EventListener);
	}, [bindings, enabled, target]);
}
