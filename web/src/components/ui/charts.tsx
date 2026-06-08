"use client";

/**
 * 数据可视化组件集 — 纯 SVG 印刷风, 1px stroke + 直角,
 * 与整体 "工程笔记" 设计语言保持一致.
 * - Sparkline: 极简折线
 * - BarRow: 水平柱条
 * - Gauge: 仪表盘 (半圆)
 * - Donut: 环形比例
 * - AreaChart: 面积图
 * - Heatmap: 1px cell 网格
 */

import { cn } from "@/lib/utils";
import * as React from "react";

/* ============================================================
   Sparkline — 极简折线
   ============================================================ */

export interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  stroke?: string;
  fill?: string;
  className?: string;
  showDots?: boolean;
}

export function Sparkline({
  data,
  width = 120,
  height = 32,
  stroke = "var(--color-primary)",
  fill,
  className,
  showDots = false,
}: SparklineProps) {
  if (data.length === 0) {
    return <div className={cn("text-[10px] text-muted-foreground/50", className)}>—</div>;
  }
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = data.length > 1 ? width / (data.length - 1) : width;
  const points = data.map((v, i) => {
    const x = i * stepX;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return [x, y] as const;
  });
  const path = points.map(([x, y], i) => (i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`)).join(" ");
  const areaPath = `${path} L ${width} ${height} L 0 ${height} Z`;
  const last = points[points.length - 1];

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={cn("overflow-visible", className)}
      style={{ width, height }}
    >
      {fill && <path d={areaPath} fill={fill} opacity={0.15} />}
      <path d={path} fill="none" stroke={stroke} strokeWidth={1.25} strokeLinecap="square" />
      {showDots &&
        points.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={1.2} fill={stroke} />
        ))}
      {last && (
        <circle
          cx={last[0]}
          cy={last[1]}
          r={2.5}
          fill="var(--color-background)"
          stroke={stroke}
          strokeWidth={1.5}
        />
      )}
    </svg>
  );
}

/* ============================================================
   BarRow — 单行柱条 (替代 recharts 的 90% 用例, 性能更好)
   ============================================================ */

export interface BarRowProps {
  label: string;
  value: number;
  max?: number;
  total?: number;
  unit?: string;
  index?: number;
  highlight?: boolean;
  variant?: "default" | "ok" | "warn" | "err";
}

export function BarRow({
  label,
  value,
  max,
  total,
  unit,
  index,
  highlight,
  variant = "default",
}: BarRowProps) {
  const denom = max ?? total ?? Math.max(value, 1);
  const pct = Math.min(100, Math.max(0, (value / denom) * 100));
  const palette: Record<typeof variant, string> = {
    default: "var(--color-foreground)",
    ok: "var(--color-success)",
    warn: "var(--color-warning)",
    err: "var(--color-destructive)",
  };
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <div className="flex min-w-0 items-baseline gap-2">
          {typeof index === "number" && (
            <span className="num text-[9px] font-medium text-muted-foreground/60">
              {String(index + 1).padStart(2, "0")}
            </span>
          )}
          <span
            className={cn(
              "truncate font-mono text-[12px]",
              highlight ? "text-foreground" : "text-foreground/80",
            )}
          >
            {label}
          </span>
        </div>
        <span className="num shrink-0 font-mono text-[12px] tabular-nums">
          {value}
          {unit && <span className="ml-0.5 text-muted-foreground/60">{unit}</span>}
        </span>
      </div>
      <div className="relative h-[3px] w-full bg-muted">
        <div
          className="absolute inset-y-0 left-0"
          style={{ width: `${pct}%`, background: palette[variant] }}
        />
      </div>
    </div>
  );
}

/* ============================================================
   Gauge — 半圆仪表盘
   ============================================================ */

export interface GaugeProps {
  value: number; // 0-100
  label?: string;
  size?: number;
  variant?: "ok" | "warn" | "err" | "default";
  showValue?: boolean;
}

export function Gauge({
  value,
  label,
  size = 96,
  variant = "default",
  showValue = true,
}: GaugeProps) {
  const clamped = Math.min(100, Math.max(0, value));
  const v =
    variant === "ok" || variant === "warn" || variant === "err"
      ? variant
      : clamped > 80
        ? "err"
        : clamped > 60
          ? "warn"
          : "ok";
  const stroke: Record<typeof v, string> = {
    ok: "var(--color-success)",
    warn: "var(--color-warning)",
    err: "var(--color-destructive)",
  };
  // 半圆: 0 -> 100 映射到 180 -> 0 度
  const radius = size / 2 - 6;
  const cx = size / 2;
  const cy = size / 2;
  const startAngle = 180;
  const endAngle = 180 - (clamped / 100) * 180;
  const polar = (a: number, r: number) => {
    const rad = (a * Math.PI) / 180;
    return [cx + r * Math.cos(rad), cy - r * Math.sin(rad)] as const;
  };
  const [x1, y1] = polar(startAngle, radius);
  const [x2, y2] = polar(endAngle, radius);
  const largeArc = Math.abs(endAngle - startAngle) > 180 ? 1 : 0;
  const arc = `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 0 ${x2} ${y2}`;
  return (
    <div className="inline-flex flex-col items-center">
      <svg
        viewBox={`0 0 ${size} ${size / 2 + 4}`}
        style={{ width: size, height: size / 2 + 4 }}
      >
        <path
          d={`M ${x1} ${y1} A ${radius} ${radius} 0 0 0 ${polar(0, radius)[0]} ${polar(0, radius)[1]}`}
          fill="none"
          stroke="var(--color-border)"
          strokeWidth={2}
        />
        <path
          d={arc}
          fill="none"
          stroke={stroke[v]}
          strokeWidth={2.5}
          strokeLinecap="square"
        />
        {showValue && (
          <text
            x={cx}
            y={cy - 4}
            textAnchor="middle"
            className="fill-foreground font-display"
            style={{ fontSize: size / 4.5, fontWeight: 600 }}
          >
            {Math.round(clamped)}
          </text>
        )}
      </svg>
      {label && (
        <span className="eyebrow mt-1 text-muted-foreground">{label}</span>
      )}
    </div>
  );
}

/* ============================================================
   Donut — 环形比例
   ============================================================ */

export interface DonutProps {
  value: number; // 0-100
  size?: number;
  stroke?: number;
  label?: string;
  sublabel?: string;
}

export function Donut({
  value,
  size = 96,
  stroke = 6,
  label,
  sublabel,
}: DonutProps) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const off = c - (Math.min(100, Math.max(0, value)) / 100) * c;
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--color-border)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--color-primary)"
          strokeWidth={stroke}
          strokeDasharray={c}
          strokeDashoffset={off}
          strokeLinecap="square"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display text-[22px] font-bold tabular-nums leading-none">
          {Math.round(value)}
          <span className="ml-0.5 text-[12px] text-muted-foreground">%</span>
        </span>
        {label && <span className="eyebrow mt-0.5">{label}</span>}
        {sublabel && (
          <span className="font-mono text-[9px] text-muted-foreground/60">
            {sublabel}
          </span>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   AreaChart — 纯 SVG 面积图 (零依赖, 体积小)
   ============================================================ */

export interface AreaChartProps {
  series: Array<{
    name: string;
    color?: string;
    data: number[];
  }>;
  labels: string[];
  width?: number;
  height?: number;
  showAxis?: boolean;
  className?: string;
}

export function AreaChart({
  series,
  labels,
  width = 480,
  height = 180,
  showAxis = true,
  className,
}: AreaChartProps) {
  if (series.length === 0 || series[0].data.length === 0) {
    return (
      <div className={cn("text-[10px] text-muted-foreground/50", className)}>暂无数据</div>
    );
  }
  const padL = showAxis ? 28 : 2;
  const padR = 4;
  const padT = 8;
  const padB = showAxis ? 18 : 4;
  const W = width - padL - padR;
  const H = height - padT - padB;
  const allValues = series.flatMap((s) => s.data);
  const min = Math.min(...allValues, 0);
  const max = Math.max(...allValues, 1);
  const range = max - min || 1;
  const n = series[0].data.length;
  const stepX = n > 1 ? W / (n - 1) : W;
  const y = (v: number) => padT + H - ((v - min) / range) * H;
  const x = (i: number) => padL + i * stepX;
  const ticks = showAxis
    ? [min, min + range * 0.25, min + range * 0.5, min + range * 0.75, max]
    : [];

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={cn("w-full", className)}
      preserveAspectRatio="none"
    >
      {showAxis &&
        ticks.map((t, i) => (
          <g key={i}>
            <line
              x1={padL}
              y1={y(t)}
              x2={padL + W}
              y2={y(t)}
              stroke="var(--color-border)"
              strokeWidth={0.5}
              strokeDasharray={i === 0 || i === ticks.length - 1 ? undefined : "1 3"}
              opacity={i === 0 || i === ticks.length - 1 ? 0.4 : 0.25}
            />
            <text
              x={padL - 4}
              y={y(t) + 3}
              textAnchor="end"
              className="fill-muted-foreground font-mono"
              style={{ fontSize: 8.5 }}
            >
              {Math.round(t)}
            </text>
          </g>
        ))}
      {series.map((s, si) => {
        const color = s.color ?? (si === 0 ? "var(--color-primary)" : "var(--color-info)");
        const points = s.data.map((v, i) => [x(i), y(v)] as const);
        const line = points
          .map(([px, py], i) => (i === 0 ? `M ${px} ${py}` : `L ${px} ${py}`))
          .join(" ");
        const area = `${line} L ${x(points.length - 1)} ${padT + H} L ${x(0)} ${padT + H} Z`;
        return (
          <g key={si}>
            <path d={area} fill={color} opacity={0.1} />
            <path d={line} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="square" />
            {points.map(([px, py], i) => (
              <circle key={i} cx={px} cy={py} r={1.4} fill="var(--color-background)" stroke={color} strokeWidth={1} />
            ))}
          </g>
        );
      })}
      {showAxis &&
        labels.map((l, i) => {
          if (n > 12 && i % Math.ceil(n / 8) !== 0 && i !== n - 1) return null;
          return (
            <text
              key={i}
              x={x(i)}
              y={padT + H + 12}
              textAnchor="middle"
              className="fill-muted-foreground font-mono"
              style={{ fontSize: 8.5 }}
            >
              {l}
            </text>
          );
        })}
    </svg>
  );
}

/* ============================================================
   BarChart — 纯 SVG 柱状图
   ============================================================ */

export interface BarChartProps {
  data: Array<{ label: string; value: number }>;
  width?: number;
  height?: number;
  showValues?: boolean;
  highlightLast?: boolean;
  className?: string;
}

export function BarChart({
  data,
  width = 480,
  height = 160,
  showValues = true,
  highlightLast = false,
  className,
}: BarChartProps) {
  if (data.length === 0) {
    return <div className={cn("text-[10px] text-muted-foreground/50", className)}>暂无数据</div>;
  }
  const padL = 4;
  const padR = 4;
  const padT = 8;
  const padB = 22;
  const W = width - padL - padR;
  const H = height - padT - padB;
  const max = Math.max(...data.map((d) => d.value), 1);
  const barW = (W / data.length) * 0.7;
  const gap = (W / data.length) * 0.3;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className={cn("w-full", className)}>
      {data.map((d, i) => {
        const h = (d.value / max) * H;
        const x = padL + i * (barW + gap) + gap / 2;
        const y = padT + H - h;
        const isLast = i === data.length - 1;
        const fill =
          highlightLast && isLast
            ? "var(--color-primary)"
            : "var(--color-foreground)";
        return (
          <g key={i}>
            <rect x={x} y={y} width={barW} height={h} fill={fill} opacity={highlightLast && isLast ? 1 : 0.75} />
            {showValues && d.value > 0 && (
              <text
                x={x + barW / 2}
                y={y - 3}
                textAnchor="middle"
                className="fill-foreground font-mono"
                style={{ fontSize: 8.5, fontWeight: 600 }}
              >
                {d.value}
              </text>
            )}
            <text
              x={x + barW / 2}
              y={padT + H + 12}
              textAnchor="middle"
              className="fill-muted-foreground font-mono"
              style={{ fontSize: 8.5 }}
            >
              {d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/* ============================================================
   Heatmap — 1px cell 网格 (活跃度日历风格)
   ============================================================ */

export interface HeatmapProps {
  rows: number;
  cols: number;
  values: number[]; // 长度 = rows * cols
  className?: string;
  cellSize?: number;
  legend?: boolean;
}

export function Heatmap({
  rows,
  cols,
  values,
  className,
  cellSize = 14,
  legend = true,
}: HeatmapProps) {
  const max = Math.max(...values, 1);
  const cell = (v: number) => {
    const t = v / max;
    if (v === 0) return "var(--color-muted)";
    if (t > 0.75) return "var(--color-primary)";
    if (t > 0.5) return "color-mix(in srgb, var(--color-primary) 65%, transparent)";
    if (t > 0.25) return "color-mix(in srgb, var(--color-primary) 35%, transparent)";
    return "color-mix(in srgb, var(--color-primary) 15%, transparent)";
  };
  return (
    <div className={cn("inline-block", className)}>
      <svg
        viewBox={`0 0 ${cols * (cellSize + 1)} ${rows * (cellSize + 1)}`}
        style={{ width: cols * (cellSize + 1), height: rows * (cellSize + 1) }}
      >
        {Array.from({ length: rows }).map((_, r) =>
          Array.from({ length: cols }).map((_, c) => {
            const idx = r * cols + c;
            const v = values[idx] ?? 0;
            return (
              <rect
                key={`${r}-${c}`}
                x={c * (cellSize + 1)}
                y={r * (cellSize + 1)}
                width={cellSize}
                height={cellSize}
                fill={cell(v)}
              />
            );
          }),
        )}
      </svg>
      {legend && (
        <div className="mt-2 flex items-center gap-1.5 font-mono text-[9px] text-muted-foreground/70">
          <span>少</span>
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <span
              key={t}
              className="h-2.5 w-2.5"
              style={{ background: cell(t * max) }}
            />
          ))}
          <span>多</span>
        </div>
      )}
    </div>
  );
}
