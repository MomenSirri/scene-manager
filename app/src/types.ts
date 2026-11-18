export interface PropSchema {
  key: string; label: string; kind: string; options: string[]; tip: string; suffix: string;
  decimals: number; step: number; min?: number; max?: number; columns?: PropSchema[];
  installed?: boolean; labels?: Record<string, string>;
}
export interface ModuleSchema {
  key: string; label: string; group: string; column: string | null; available: boolean; installed?: boolean;
  touches_scene: boolean; props: PropSchema[];
}
export interface Group { key: string; label: string; icon: string; tint: string }
export interface Schema { groups: Group[]; modules: ModuleSchema[] }
export interface Item {
  id: string; type: "setup" | "folder"; name: string; parent: string | null; color: string | null;
  tags: string[]; description: string; thumb: boolean; summary?: Record<string, string>;
}
export interface State {
  file: string; renderer: string; active: string | null; baseline: boolean; items: Item[];
  last_apply_ms: number | null; notice: string; columns: { key: string; label: string }[]; log: string[];
}
export interface Row {
  key: string; value: any; own: boolean; inherited: boolean; differs: boolean; from: string;
  scene?: any; effective?: any; own_value?: any;
}
export interface CardData { key: string; enabled: boolean; origin: string; rows: Row[]; actions: string[] }
export interface Detail {
  id: string; type: "setup" | "folder"; name: string; path: string; folder: string; description: string;
  tags: string[]; color: string | null; active: boolean; setups_inside: number; cards: CardData[];
  nodes: Record<string, string[]>;
}
/** Per-user look of a card, keyed by module: place and size are in dots of the board grid. */
export interface CardPref { gx?: number; w?: number; h?: number; color?: string; title?: string; folded?: boolean }
