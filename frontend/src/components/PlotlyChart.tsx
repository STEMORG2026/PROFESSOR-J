"use client";

import dynamic from "next/dynamic";

// plotly.js is large; load it client-side only via dynamic import.
const Plot = dynamic(() => import("react-plotly.js"), {
  ssr: false,
  loading: () => <div className="plotly-loading">Loading chart…</div>,
});

export interface PlotlyChartProps {
  /** Plotly figure config: { data: [...], layout?: {...}, config?: {...} } */
  figure: {
    data: unknown[];
    layout?: Record<string, unknown>;
    config?: Record<string, unknown>;
  };
}

/**
 * Renders an interactive Plotly chart from a figure config. Used to display
 * chart JSON blocks the model emits (e.g. wrapped in a ```plotly fenced block).
 */
export default function PlotlyChart({ figure }: PlotlyChartProps) {
  const data = Array.isArray(figure.data) ? figure.data : [];
  return (
    <div className="plotly-chart my-3 rounded-lg border border-slate-700/60 bg-slate-900/40 p-2">
      <Plot
        data={data as never}
        layout={figure.layout ?? ({} as never)}
        config={{
          responsive: true,
          displaylogo: false,
          ...(figure.config ?? {}),
        }}
        useResizeHandler
        style={{ width: "100%", height: "420px" }}
      />
    </div>
  );
}