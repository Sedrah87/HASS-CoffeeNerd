// Datenformen der WebSocket-Commands (siehe custom_components/coffeenord/websocket.py).

export type CurveName = "weight" | "weight2" | "flow" | "flow2" | "pressure" | "temperature";
export type Curves = Partial<Record<CurveName, [number, number][]>>;

export interface ShotSummary {
  id: string;
  brewed_at: number;
  updated_at: number;
  bean_name: string | null;
  bean_roaster: string | null;
  bean2_name: string | null;
  mill_name: string | null;
  preparation_name: string | null;
  preparation_style: string | null;
  grind_size: string | null;
  dose_g: number | null;
  yield_g: number | null;
  brew_time_s: number | null;
  ratio: number | null;
  tds: number | null;
  ey: number | null;
  rating: number | null;
  peak_pressure: number | null;
  has_curves: boolean;
}

export interface ShotDetail extends ShotSummary {
  curves: Curves;
}

export interface ShotList {
  shots: ShotSummary[];
  total: number;
}

export interface FilterValues {
  beans: string[];
  mills: string[];
  preparations: string[];
}

// Nur der Teil des hass-Objekts, den das Panel nutzt.
export interface HomeAssistant {
  language: string;
  locale?: { language: string };
  themes?: { darkMode?: boolean };
  user?: { is_admin: boolean };
  callWS<T>(message: Record<string, unknown>): Promise<T>;
}
