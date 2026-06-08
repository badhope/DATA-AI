"use client";

/**
 * "AI 帮填" 按钮：调 LLM 流式生成内容并写到目标字段
 */

import { Button } from "@/components/ui/button";
import { useAIGenerate, type AIGenerateOptions } from "@/hooks/use-ai-generate";
import { cn } from "@/lib/utils";
import { Loader2, Sparkles, Square } from "lucide-react";
import * as React from "react";

export interface AIGenerateButtonProps {
	/** 提示词：要 LLM 生成什么 */
	prompt: string;
	/** 系统提示（角色/格式约束）*/
	systemHint?: string;
	/** 指定模型 */
	model?: string;
	/** 温度 */
	temperature?: number;
	/** 最大 token */
	maxTokens?: number;
	/** 生成时流式回调 (fullText) => void */
	onStream: (text: string) => void;
	/** 完成后回调 */
	onComplete?: (text: string) => void;
	/** 按钮文字 */
	label?: string;
	/** 是否禁用 */
	disabled?: boolean;
	/** 按钮变体 */
	variant?: "default" | "outline" | "ghost" | "secondary";
	/** 尺寸 */
	size?: "default" | "sm" | "lg" | "icon";
	/** 额外 className */
	className?: string;
}

export function AIGenerateButton({
	prompt,
	systemHint,
	model,
	temperature,
	maxTokens,
	onStream,
	onComplete,
	label = "AI 帮填",
	disabled = false,
	variant = "outline",
	size = "sm",
	className,
}: AIGenerateButtonProps) {
	const { generate, isGenerating, abort } = useAIGenerate();

	const handleClick = async () => {
		const opts: AIGenerateOptions = {
			prompt,
			systemHint,
			model,
			temperature,
			maxTokens,
		};
		const final = await generate(opts, onStream);
		if (final) onComplete?.(final);
	};

	return (
		<Button
			type="button"
			variant={isGenerating ? "outline" : variant}
			size={size}
			disabled={disabled && !isGenerating}
			onClick={isGenerating ? abort : handleClick}
			className={cn("gap-1.5", className)}
		>
			{isGenerating ? (
				<>
					<Loader2 className="h-3.5 w-3.5 animate-spin" />
					生成中…
					<Square className="h-3 w-3" />
				</>
			) : (
				<>
					<Sparkles className="h-3.5 w-3.5" />
					{label}
				</>
			)}
		</Button>
	);
}
