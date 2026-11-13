// Kurven eines Shots als übereinanderliegende Teil-Diagramme mit gemeinsamer Zeitachse.
// Bewusst keine zweite y-Achse: Gewicht, Fluss, Druck und Temperatur haben je ein
// eigenes Diagramm mit eigener Einheit. Fadenkreuz und Zoom sind gekoppelt.

import { LineChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { css, html, LitElement, type PropertyValues } from "lit";

import type { TextKey, Translate } from "./i18n";
import type { CurveName, Curves } from "./types";

echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  DataZoomComponent,
  TitleComponent,
  CanvasRenderer,
]);

/** Senkrechte Markierung auf der Zeitachse, z. B. erster Tropfen. */
export interface ChartMarker {
  time: number;
  label: string;
}

// Kategoriale Farben (Dataviz-Referenzpalette, Slot 1 und 2), geprüft gegen die
// HASS-Kartenhintergründe #ffffff und #1c1c1c: Waage 1 blau, Waage 2 orange.
const COLORS = {
  light: ["#2a78d6", "#eb6834"],
  dark: ["#3987e5", "#d95926"],
};

interface PanelSpec {
  title: TextKey;
  unit: string;
  curves: [CurveName, CurveName?];
  /** Achse am Messbereich ausrichten statt bei 0 beginnen (z. B. Temperatur um 93 °C). */
  scale?: boolean;
}

const PANELS: PanelSpec[] = [
  { title: "chart_weight", unit: "g", curves: ["weight", "weight2"] },
  { title: "chart_flow", unit: "g/s", curves: ["flow", "flow2"] },
  { title: "chart_pressure", unit: "bar", curves: ["pressure"] },
  { title: "chart_temperature", unit: "°C", curves: ["temperature"], scale: true },
];

const PANEL_HEIGHT = 120;
const PANEL_GAP = 48; // Platz für Titel und x-Achsenbeschriftung
const LEGEND_HEIGHT = 28;
const ZOOM_HEIGHT = 56;

export class ShotChart extends LitElement {
  static properties = {
    curves: { attribute: false },
    markers: { attribute: false },
    dark: { type: Boolean },
    language: { type: String },
    t: { attribute: false },
  };

  declare curves: Curves;
  declare markers: ChartMarker[];
  declare dark: boolean;
  declare language: string;
  declare t: Translate;

  private chart?: echarts.ECharts;
  private resizeObserver?: ResizeObserver;

  static styles = css`
    :host {
      display: block;
    }
    .chart {
      width: 100%;
    }
  `;

  render() {
    return html`<div class="chart" role="img" aria-label=${this.ariaSummary()}></div>`;
  }

  protected firstUpdated(): void {
    const container = this.renderRoot.querySelector<HTMLDivElement>(".chart")!;
    this.chart = echarts.init(container, undefined, { renderer: "canvas" });
    this.resizeObserver = new ResizeObserver(() => this.chart?.resize());
    this.resizeObserver.observe(container);
    this.draw();
  }

  protected updated(changed: PropertyValues): void {
    if (
      this.chart &&
      (changed.has("curves") || changed.has("markers") || changed.has("dark") || changed.has("t"))
    ) {
      this.draw();
    }
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.resizeObserver?.disconnect();
    this.chart?.dispose();
    this.chart = undefined;
  }

  private visiblePanels(): PanelSpec[] {
    return PANELS.filter((panel) => panel.curves.some((name) => name && this.curves[name]?.length));
  }

  private ariaSummary(): string {
    return this.visiblePanels()
      .map((panel) => `${this.t(panel.title)} (${panel.unit})`)
      .join(", ");
  }

  private cssVar(name: string, fallback: string): string {
    return getComputedStyle(this).getPropertyValue(name).trim() || fallback;
  }

  private draw(): void {
    const chart = this.chart!;
    const panels = this.visiblePanels();
    const colors = this.dark ? COLORS.dark : COLORS.light;
    const text = this.cssVar("--primary-text-color", this.dark ? "#e1e1e1" : "#212121");
    const muted = this.cssVar("--secondary-text-color", this.dark ? "#9b9b9b" : "#727272");
    const divider = this.cssVar("--divider-color", this.dark ? "#333333" : "#e0e0e0");
    const surface = this.cssVar("--card-background-color", this.dark ? "#1c1c1c" : "#ffffff");

    // Zwei Waagen → Legende „Waage 1/Waage 2“. Sonst trägt jede Reihe den Namen
    // ihres Diagramms, und der Titel reicht als Beschriftung.
    const twoScales = Boolean(this.curves.weight2?.length || this.curves.flow2?.length);
    const legendSpace = twoScales ? LEGEND_HEIGHT : 0;
    const maxTime = Math.max(
      1,
      ...Object.values(this.curves).flatMap((points) => points?.map(([time]) => time) ?? []),
    );

    const grids = panels.map((_, index) => ({
      left: 56,
      right: 16,
      top: legendSpace + index * (PANEL_HEIGHT + PANEL_GAP) + 28,
      height: PANEL_HEIGHT,
    }));
    const axisIndexes = panels.map((_, index) => index);

    const markers = this.markers ?? [];
    const series = panels.flatMap((panel, index) =>
      panel.curves
        .filter((name): name is CurveName => Boolean(name && this.curves[name]?.length))
        .map((name, seriesIndex) => {
          const second = name.endsWith("2");
          return {
            type: "line" as const,
            name: twoScales ? this.t(second ? "scale_2" : "scale_1") : this.t(panel.title),
            xAxisIndex: index,
            yAxisIndex: index,
            data: this.curves[name],
            showSymbol: false,
            lineStyle: { width: 2 },
            itemStyle: { color: colors[second ? 1 : 0] },
            emphasis: { disabled: true },
            // Markierungen einmal pro Diagramm, beschriftet nur im obersten.
            markLine:
              seriesIndex === 0 && markers.length
                ? {
                    silent: true,
                    symbol: "none",
                    animation: false,
                    lineStyle: { color: muted, type: "dashed", width: 1 },
                    label: index === 0
                      ? { show: true, position: "end", color: muted, formatter: "{b}" }
                      : { show: false },
                    data: markers.map((marker) => ({ name: marker.label, xAxis: marker.time })),
                  }
                : undefined,
            tooltip: {
              valueFormatter: (value: unknown) =>
                `${new Intl.NumberFormat(this.language, { maximumFractionDigits: 2 }).format(
                  Number(value),
                )} ${panel.unit}`,
            },
          };
        }),
    );

    chart.getDom().style.height = `${
      legendSpace + panels.length * (PANEL_HEIGHT + PANEL_GAP) + ZOOM_HEIGHT
    }px`;
    chart.resize();
    chart.setOption(
      {
        animation: false,
        textStyle: { color: text },
        title: panels.map((panel, index) => ({
          text: `${this.t(panel.title)} · ${panel.unit}`,
          left: 8,
          top: grids[index].top - 26,
          textStyle: { color: text, fontSize: 13, fontWeight: 500 },
        })),
        legend: twoScales
          ? { top: 0, right: 16, textStyle: { color: text }, icon: "roundRect" }
          : undefined,
        grid: grids,
        xAxis: panels.map((_, index) => ({
          type: "value",
          gridIndex: index,
          min: 0,
          max: Math.ceil(maxTime),
          axisLabel: { color: muted, formatter: "{value} s" },
          axisLine: { lineStyle: { color: divider } },
          splitLine: { show: false },
        })),
        yAxis: panels.map((panel, index) => ({
          type: "value",
          gridIndex: index,
          scale: Boolean(panel.scale),
          axisLabel: { color: muted },
          splitLine: { lineStyle: { color: divider } },
        })),
        axisPointer: { link: [{ xAxisIndex: "all" }] },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "line", lineStyle: { color: muted } },
          backgroundColor: surface,
          borderColor: divider,
          textStyle: { color: text },
        },
        dataZoom: [
          { type: "inside", xAxisIndex: axisIndexes },
          {
            type: "slider",
            xAxisIndex: axisIndexes,
            bottom: 8,
            height: 24,
            borderColor: divider,
            textStyle: { color: muted },
            labelFormatter: (value: number) => `${Math.round(value)} s`,
          },
        ],
        series,
      },
      { notMerge: true },
    );
  }
}

customElements.define("coffeenord-shot-chart", ShotChart);
