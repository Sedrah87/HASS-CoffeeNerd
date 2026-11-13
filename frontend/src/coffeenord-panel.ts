// Seitenleisten-Panel „Shots“: Liste mit Filtern und Detailansicht mit Kurven.
// Home Assistant setzt hass, narrow und panel als Properties.

import { css, html, LitElement, nothing, type PropertyValues } from "lit";

import { dateInputToUnix, formatDateTime, formatNumber } from "./format";
import { shapeLabel, translator, type Translate } from "./i18n";
import "./shot-chart";
import type { CurveName, FilterValues, HomeAssistant, ShotDetail, ShotList, ShotSummary } from "./types";

const PAGE_SIZE = 50;

interface Filters {
  bean: string;
  mill: string;
  preparation: string;
  shape: string;
  from: string;
  to: string;
}

const NO_FILTERS: Filters = { bean: "", mill: "", preparation: "", shape: "", from: "", to: "" };

const TABLE_COLUMNS: { curve: CurveName; label: "chart_weight" | "chart_flow" | "chart_pressure" | "chart_temperature"; unit: string; second?: boolean }[] = [
  { curve: "weight", label: "chart_weight", unit: "g" },
  { curve: "weight2", label: "chart_weight", unit: "g", second: true },
  { curve: "flow", label: "chart_flow", unit: "g/s" },
  { curve: "flow2", label: "chart_flow", unit: "g/s", second: true },
  { curve: "pressure", label: "chart_pressure", unit: "bar" },
  { curve: "temperature", label: "chart_temperature", unit: "°C" },
];

class CoffeeNordPanel extends LitElement {
  static properties = {
    hass: { attribute: false },
    narrow: { type: Boolean },
    filterValues: { state: true },
    filters: { state: true },
    shots: { state: true },
    total: { state: true },
    loading: { state: true },
    error: { state: true },
    detail: { state: true },
  };

  declare hass: HomeAssistant;
  declare narrow: boolean;
  declare filterValues: FilterValues;
  declare filters: Filters;
  declare shots: ShotSummary[];
  declare total: number;
  declare loading: boolean;
  declare error: string;
  declare detail: ShotDetail | null;

  private loaded = false;

  constructor() {
    super();
    this.filterValues = { beans: [], mills: [], preparations: [], shapes: [] };
    this.filters = { ...NO_FILTERS };
    this.shots = [];
    this.total = 0;
    this.loading = false;
    this.error = "";
    this.detail = null;
  }

  private get language(): string {
    return this.hass?.locale?.language ?? this.hass?.language ?? "en";
  }

  private get t(): Translate {
    return translator(this.language);
  }

  protected willUpdate(changed: PropertyValues): void {
    if (changed.has("hass") && this.hass && !this.loaded) {
      this.loaded = true;
      void this.reload();
    }
  }

  private async reload(): Promise<void> {
    this.shots = [];
    this.total = 0;
    await Promise.all([this.loadFilterValues(), this.loadPage()]);
  }

  private async loadFilterValues(): Promise<void> {
    try {
      const values = await this.hass.callWS<FilterValues>({ type: "coffeenord/filters" });
      // Ältere Integrationen ohne Profile liefern kein "shapes".
      this.filterValues = { ...values, shapes: values.shapes ?? [] };
    } catch (err) {
      this.showError(err);
    }
  }

  private async loadPage(): Promise<void> {
    this.loading = true;
    try {
      const message: Record<string, unknown> = {
        type: "coffeenord/shots/list",
        limit: PAGE_SIZE,
        offset: this.shots.length,
      };
      if (this.filters.bean) message.bean = this.filters.bean;
      if (this.filters.mill) message.mill = this.filters.mill;
      if (this.filters.preparation) message.preparation = this.filters.preparation;
      if (this.filters.shape) message.shape = this.filters.shape;
      const from = dateInputToUnix(this.filters.from, false);
      const to = dateInputToUnix(this.filters.to, true);
      if (from !== undefined) message.from = from;
      if (to !== undefined) message.to = to;

      const result = await this.hass.callWS<ShotList>(message);
      this.shots = [...this.shots, ...result.shots];
      this.total = result.total;
      this.error = "";
    } catch (err) {
      this.showError(err);
    } finally {
      this.loading = false;
    }
  }

  private async openShot(id: string): Promise<void> {
    try {
      this.detail = await this.hass.callWS<ShotDetail>({ type: "coffeenord/shots/get", shot_id: id });
      this.error = "";
      window.scrollTo({ top: 0 });
    } catch (err) {
      this.showError(err);
    }
  }

  private async deleteShot(): Promise<void> {
    if (!this.detail || !confirm(this.t("delete_confirm"))) return;
    try {
      await this.hass.callWS({ type: "coffeenord/shots/delete", shot_id: this.detail.id });
      this.detail = null;
      await this.reload();
    } catch (err) {
      this.showError(err);
    }
  }

  private showError(err: unknown): void {
    const message = (err as { message?: string })?.message ?? String(err);
    this.error = this.t("error", { message });
  }

  private setFilter(key: keyof Filters, value: string): void {
    this.filters = { ...this.filters, [key]: value };
    void this.reload();
  }

  private resetFilters(): void {
    this.filters = { ...NO_FILTERS };
    void this.reload();
  }

  render() {
    return html`
      <div class="toolbar">
        <ha-menu-button .hass=${this.hass} .narrow=${this.narrow}></ha-menu-button>
        <h1>${this.t("title")}</h1>
      </div>
      <main>
        ${this.error ? html`<p class="error" role="alert">${this.error}</p>` : nothing}
        ${this.detail ? this.renderDetail(this.detail) : this.renderList()}
      </main>
    `;
  }

  private renderSelect(
    key: "bean" | "mill" | "preparation" | "shape",
    label: string,
    options: string[],
    optionLabel: (option: string) => string = (option) => option,
  ) {
    return html`
      <label>
        <span>${label}</span>
        <select @change=${(e: Event) => this.setFilter(key, (e.target as HTMLSelectElement).value)}>
          <option value="" ?selected=${!this.filters[key]}>${this.t("filter_all")}</option>
          ${options.map(
            (option) =>
              html`<option .value=${option} ?selected=${this.filters[key] === option}>${optionLabel(option)}</option>`,
          )}
        </select>
      </label>
    `;
  }

  private renderDate(key: "from" | "to", label: string) {
    return html`
      <label>
        <span>${label}</span>
        <input
          type="date"
          .value=${this.filters[key]}
          @change=${(e: Event) => this.setFilter(key, (e.target as HTMLInputElement).value)}
        />
      </label>
    `;
  }

  private renderList() {
    const t = this.t;
    const filtered = Object.values(this.filters).some(Boolean);
    return html`
      <div class="filters">
        ${this.renderSelect("bean", t("filter_bean"), this.filterValues.beans)}
        ${this.renderSelect("mill", t("filter_mill"), this.filterValues.mills)}
        ${this.renderSelect("preparation", t("filter_preparation"), this.filterValues.preparations)}
        ${this.filterValues.shapes.length
          ? this.renderSelect("shape", t("filter_shape"), this.filterValues.shapes, (shape) => shapeLabel(t, shape))
          : nothing}
        ${this.renderDate("from", t("filter_from"))} ${this.renderDate("to", t("filter_to"))}
        ${filtered ? html`<button class="link" @click=${this.resetFilters}>${t("filter_reset")}</button>` : nothing}
      </div>

      ${!this.loading && this.shots.length === 0
        ? html`<p class="empty">${filtered ? t("empty_filtered") : t("empty")}</p>`
        : html`
            <ul class="shots">
              ${this.shots.map((shot) => this.renderRow(shot))}
            </ul>
            <div class="more">
              <span>${t("count", { shown: this.shots.length, total: this.total })}</span>
              ${this.shots.length < this.total
                ? html`<button ?disabled=${this.loading} @click=${() => this.loadPage()}>${t("load_more")}</button>`
                : nothing}
            </div>
          `}
    `;
  }

  private renderRow(shot: ShotSummary) {
    const language = this.language;
    const bean = [shot.bean_name, shot.bean2_name].filter(Boolean).join(" + ") || "–";
    const meta = [
      shot.preparation_name,
      shot.mill_name,
      shot.grind_size,
      shot.shape ? shapeLabel(this.t, shot.shape) : null,
    ]
      .filter(Boolean)
      .join(" · ");
    return html`
      <li>
        <button class="row" @click=${() => this.openShot(shot.id)}>
          <span class="when">${formatDateTime(language, shot.brewed_at)}</span>
          <span class="bean">${bean}</span>
          <span class="meta">${meta}</span>
          <span class="numbers">
            ${formatNumber(language, shot.dose_g)} g → ${formatNumber(language, shot.yield_g)} g ·
            ${formatNumber(language, shot.brew_time_s)} s
            ${shot.ratio !== null ? html` · 1:${formatNumber(language, shot.ratio, 2)}` : nothing}
          </span>
        </button>
      </li>
    `;
  }

  private renderDetail(shot: ShotDetail) {
    const t = this.t;
    const language = this.language;
    const bean = [shot.bean_name, shot.bean2_name].filter(Boolean).join(" + ") || "–";
    const facts: [string, string][] = [
      [t("dose"), `${formatNumber(language, shot.dose_g)} g`],
      [t("yield"), `${formatNumber(language, shot.yield_g)} g`],
      [t("ratio"), shot.ratio !== null ? `1:${formatNumber(language, shot.ratio, 2)}` : "–"],
      [t("time"), `${formatNumber(language, shot.brew_time_s)} s`],
      [t("grind"), shot.grind_size ?? "–"],
      [t("filter_mill"), shot.mill_name ?? "–"],
      [t("filter_preparation"), shot.preparation_name ?? "–"],
      [t("roaster"), shot.bean_roaster ?? "–"],
      [t("rating"), formatNumber(language, shot.rating)],
      [t("peak_pressure"), shot.peak_pressure !== null ? `${formatNumber(language, shot.peak_pressure)} bar` : "–"],
      [t("tds"), shot.tds !== null ? `${formatNumber(language, shot.tds, 2)} %` : "–"],
      [t("ey"), shot.ey !== null ? `${formatNumber(language, shot.ey, 2)} %` : "–"],
    ];
    return html`
      <div class="detail-head">
        <button class="link" @click=${() => (this.detail = null)}>← ${t("back")}</button>
        ${this.hass.user?.is_admin
          ? html`<button class="link danger" @click=${this.deleteShot}>${t("delete")}</button>`
          : nothing}
      </div>
      <section class="card">
        <h2>${bean}</h2>
        <p class="when">${formatDateTime(language, shot.brewed_at)}</p>
        <dl class="facts">
          ${facts.map(([label, value]) => html`<div><dt>${label}</dt><dd>${value}</dd></div>`)}
        </dl>
      </section>
      ${this.renderAnalysis(shot)}
      <section class="card">
        ${shot.has_curves
          ? html`
              <coffeenord-shot-chart
                .curves=${shot.curves}
                .markers=${this.markers(shot)}
                .dark=${Boolean(this.hass.themes?.darkMode)}
                .language=${language}
                .t=${t}
              ></coffeenord-shot-chart>
              ${this.renderTable(shot)}
            `
          : html`<p class="empty">${t("no_curves")}</p>`}
      </section>
    `;
  }

  /** Erster Tropfen und Pumpenende als senkrechte Linien: dazwischen liegt die Hauptphase. */
  private markers(shot: ShotDetail): { time: number; label: string }[] {
    const analysis = shot.analysis ?? {};
    const markers: { time: number; label: string }[] = [];
    if (analysis.first_drip_s !== undefined) markers.push({ time: analysis.first_drip_s, label: this.t("first_drip") });
    if (analysis.end_s !== undefined) markers.push({ time: analysis.end_s, label: this.t("pump_end") });
    return markers;
  }

  /** Auswertung der App (Profil, Fluss, Mahlgrad-Hinweis). Fehlt sie, entfällt die Karte. */
  private renderAnalysis(shot: ShotDetail) {
    const t = this.t;
    const language = this.language;
    const analysis = shot.analysis ?? {};
    const flow = (value: number | undefined) =>
      value !== undefined ? `${formatNumber(language, value, 2)} g/s` : "–";
    const seconds = (value: number | undefined) =>
      value !== undefined ? `${formatNumber(language, value)} s` : "–";
    const facts: [string, string][] = [
      [t("shape"), shapeLabel(t, analysis.shape)],
      [t("main_flow"), flow(analysis.main_flow)],
      [t("first_third_flow"), flow(analysis.first_third_flow)],
      [t("last_third_flow"), flow(analysis.last_third_flow)],
      [t("peak_flow"), flow(analysis.peak_flow)],
      [t("first_drip"), seconds(analysis.first_drip_s)],
      [t("pump_end"), seconds(analysis.end_s)],
    ];
    const hasNumbers = facts.some(([, value]) => value !== "–");
    if (!hasNumbers && !analysis.grind_hint && !analysis.anomaly_reason) return nothing;
    return html`
      <section class="card">
        <h3>${t("analysis_title")}</h3>
        ${analysis.grind_hint
          ? html`<p class="hint"><strong>${t("grind_hint")}:</strong> ${analysis.grind_hint}</p>`
          : nothing}
        ${analysis.anomaly_reason
          ? html`<p class="hint"><strong>${t("anomaly_reason")}:</strong> ${analysis.anomaly_reason}</p>`
          : nothing}
        ${hasNumbers
          ? html`<dl class="facts">
              ${facts.map(([label, value]) => html`<div><dt>${label}</dt><dd>${value}</dd></div>`)}
            </dl>`
          : nothing}
      </section>
    `;
  }

  /** Tabellenansicht der Kurven, ein Wert pro Sekunde (letzter Messwert bis dahin). */
  private renderTable(shot: ShotDetail) {
    const t = this.t;
    const language = this.language;
    const columns = TABLE_COLUMNS.filter((column) => shot.curves[column.curve]?.length);
    const maxTime = Math.max(...columns.flatMap((c) => shot.curves[c.curve]!.map(([time]) => time)));
    const rows: (number | null)[][] = [];
    for (let second = 0; second <= Math.ceil(maxTime); second++) {
      rows.push([
        second,
        ...columns.map((column) => {
          let value: number | null = null;
          for (const [time, point] of shot.curves[column.curve]!) {
            if (time > second) break;
            value = point;
          }
          return value;
        }),
      ]);
    }
    return html`
      <details>
        <summary>${t("table_toggle")}</summary>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>${t("table_time")}</th>
                ${columns.map(
                  (c) => html`<th>${t(c.label)}${c.second ? ` (${t("scale_2")})` : ""} (${c.unit})</th>`,
                )}
              </tr>
            </thead>
            <tbody>
              ${rows.map(
                (row) => html`<tr>${row.map((value) => html`<td>${formatNumber(language, value, 2)}</td>`)}</tr>`,
              )}
            </tbody>
          </table>
        </div>
      </details>
    `;
  }

  static styles = css`
    :host {
      display: block;
      min-height: 100vh;
      background: var(--primary-background-color);
      color: var(--primary-text-color);
      font-family: var(--paper-font-body1_-_font-family, inherit);
    }
    .toolbar {
      display: flex;
      align-items: center;
      gap: 8px;
      height: var(--header-height, 56px);
      padding: 0 12px;
      background: var(--app-header-background-color, var(--primary-color));
      color: var(--app-header-text-color, #fff);
    }
    h1 {
      margin: 0;
      font-size: 20px;
      font-weight: 400;
    }
    main {
      max-width: 1000px;
      margin: 0 auto;
      padding: 16px;
    }
    .filters {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: end;
      margin-bottom: 16px;
    }
    label {
      display: flex;
      flex-direction: column;
      gap: 4px;
      font-size: 12px;
      color: var(--secondary-text-color);
    }
    select,
    input {
      box-sizing: border-box;
      width: 100%;
      min-width: 140px;
      padding: 8px;
      border: 1px solid var(--divider-color);
      border-radius: 6px;
      background: var(--card-background-color);
      color: var(--primary-text-color);
      font: inherit;
      font-size: 14px;
    }
    button {
      font: inherit;
      cursor: pointer;
    }
    .more button {
      padding: 8px 16px;
      border: 1px solid var(--divider-color);
      border-radius: 6px;
      background: var(--card-background-color);
      color: var(--primary-color);
    }
    .link {
      border: none;
      background: none;
      padding: 8px 0;
      color: var(--primary-color);
    }
    .danger {
      color: var(--error-color, #db4437);
    }
    .shots {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 8px;
    }
    .row {
      width: 100%;
      display: grid;
      grid-template-columns: 11em 1fr auto;
      grid-template-areas: "when bean numbers" "when meta numbers";
      gap: 2px 16px;
      padding: 12px 16px;
      text-align: left;
      border: none;
      border-radius: var(--ha-card-border-radius, 12px);
      background: var(--card-background-color);
      color: var(--primary-text-color);
      box-shadow: var(--ha-card-box-shadow, none);
    }
    .row:hover,
    .row:focus-visible {
      outline: 2px solid var(--primary-color);
    }
    .when {
      grid-area: when;
      color: var(--secondary-text-color);
      font-size: 14px;
    }
    .bean {
      grid-area: bean;
      font-weight: 500;
    }
    .meta {
      grid-area: meta;
      color: var(--secondary-text-color);
      font-size: 14px;
    }
    .numbers {
      grid-area: numbers;
      align-self: center;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }
    :host([narrow]) .filters label {
      flex: 1 1 calc(50% - 6px);
      min-width: 0;
    }
    :host([narrow]) select,
    :host([narrow]) input {
      min-width: 0;
    }
    :host([narrow]) main {
      padding: 12px;
    }
    :host([narrow]) .row {
      grid-template-columns: 1fr;
      grid-template-areas: "bean" "when" "meta" "numbers";
    }
    .more {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin: 16px 0;
      color: var(--secondary-text-color);
    }
    .empty,
    .error {
      padding: 24px 0;
      color: var(--secondary-text-color);
    }
    .error {
      color: var(--error-color, #db4437);
    }
    .detail-head {
      display: flex;
      justify-content: space-between;
    }
    .card {
      margin-bottom: 16px;
      padding: 16px;
      border-radius: var(--ha-card-border-radius, 12px);
      background: var(--card-background-color);
      box-shadow: var(--ha-card-box-shadow, none);
    }
    h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 500;
    }
    h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 500;
    }
    .hint {
      margin: 12px 0 0;
      line-height: 1.4;
    }
    .facts {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
      gap: 12px;
      margin: 16px 0 0;
    }
    dt {
      font-size: 12px;
      color: var(--secondary-text-color);
    }
    dd {
      margin: 2px 0 0;
      font-variant-numeric: tabular-nums;
    }
    details {
      margin-top: 8px;
    }
    summary {
      cursor: pointer;
      color: var(--primary-color);
      padding: 8px 0;
    }
    .table-wrap {
      max-height: 360px;
      overflow: auto;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      font-variant-numeric: tabular-nums;
      font-size: 14px;
    }
    th,
    td {
      padding: 4px 8px;
      text-align: right;
      border-bottom: 1px solid var(--divider-color);
    }
    th {
      position: sticky;
      top: 0;
      background: var(--card-background-color);
      color: var(--secondary-text-color);
      font-weight: 500;
    }
  `;
}

customElements.define("coffeenord-panel", CoffeeNordPanel);
