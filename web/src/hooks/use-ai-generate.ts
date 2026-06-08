"use client";

/**
 * AI 自动生成 hook：调 chatCompletion 让 LLM 帮填表单字段
 *
 * 用法：
 *   const { generate, isGenerating } = useAIGenerate();
 *   await generate({ prompt, systemHint, model }, onChunk);
 */

import { getClient } from "@/lib/api/client";
import { reportError } from "@/lib/errors";
import { getActiveProfile, useSettings } from "@/lib/stores/settings";
import * as React from "react";

export interface AIGenerateOptions {
	/** 用户 prompt（要 LLM 生成什么）*/
	prompt: string;
	/** 系统提示（角色/格式约束，可选）*/
	systemHint?: string;
	/** 指定模型（默认从 settings 读 defaultModel）*/
	model?: string;
	/** 温度（默认 0.7）*/
	temperature?: number;
	/** 最大 token（默认 1024）*/
	maxTokens?: number;
}

export interface AIGenerateReturn {
	generate: (opts: AIGenerateOptions, onChunk: (text: string) => void) => Promise<string>;
	isGenerating: boolean;
	abort: () => void;
}

export function useAIGenerate(): AIGenerateReturn {
	const [isGenerating, setIsGenerating] = React.useState(false);
	const abortRef = React.useRef<AbortController | null>(null);

	const generate = React.useCallback(
		async (opts: AIGenerateOptions, onChunk: (text: string) => void): Promise<string> => {
			const activeProfile = getActiveProfile();
			const defaultModel = activeProfile?.defaultModel || "gpt-4";
			const model = opts.model || defaultModel;
			const ac = new AbortController();
			abortRef.current = ac;
			setIsGenerating(true);
			let full = "";
			try {
				const messages: { role: "system" | "user"; content: string }[] = [];
				if (opts.systemHint) {
					messages.push({ role: "system", content: opts.systemHint });
				}
				messages.push({ role: "user", content: opts.prompt });
				const stream = getClient().chatCompletionStream(
					{
						model,
						messages,
						temperature: opts.temperature ?? 0.7,
						max_tokens: opts.maxTokens ?? 1024,
						stream: true,
					},
					{ signal: ac.signal },
				);
				for await (const chunk of stream) {
					const piece = chunk?.choices?.[0]?.delta?.content;
					if (piece) {
						full += piece;
						onChunk(full);
					}
				}
				return full.trim();
			} catch (e) {
				if (!(e instanceof DOMException && e.name === "AbortError")) {
					reportError(e, "AI 生成");
				}
				return full;
			} finally {
				setIsGenerating(false);
				abortRef.current = null;
			}
		},
		[],
	);

	const abort = React.useCallback(() => {
		abortRef.current?.abort();
		setIsGenerating(false);
	}, []);

	return { generate, isGenerating, abort };
}
