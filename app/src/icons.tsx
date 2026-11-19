// Line icons, 20 px grid, drawn with currentColor.
const P: Record<string, JSX.Element> = {
  setups: <><path d="M7 5h10M7 10h10M7 15h10" /><circle cx="3.5" cy="5" r="1" /><circle cx="3.5" cy="10" r="1" /><circle cx="3.5" cy="15" r="1" /></>,
  render: <path d="M6 4l10 6-10 6z" />,
  camera: <><rect x="2.5" y="6" width="11" height="8.5" rx="2" /><path d="M13.5 9l4-2.2v6.9l-4-2.2" /><circle cx="8" cy="10.2" r="2" /></>,
  light: <><circle cx="10" cy="10" r="3.2" /><path d="M10 2.5v2M10 15.5v2M2.5 10h2M15.5 10h2M4.7 4.7l1.4 1.4M13.9 13.9l1.4 1.4M4.7 15.3l1.4-1.4M13.9 6.1l1.4-1.4" /></>,
  scene: <><path d="M10 3l7 3.5-7 3.5-7-3.5z" /><path d="M3 10l7 3.5 7-3.5M3 13.5L10 17l7-3.5" /></>,
  rendersettings: <><path d="M5 3v14M10 3v14M15 3v14" /><circle cx="5" cy="7" r="1.8" fill="currentColor" /><circle cx="10" cy="13" r="1.8" fill="currentColor" /><circle cx="15" cy="8" r="1.8" fill="currentColor" /></>,
  script: <path d="M7 6l-4 4 4 4M13 6l4 4-4 4M11.5 4l-3 12" />,
  note: <><rect x="4" y="3" width="12" height="14" rx="2" /><path d="M7 7h6M7 10h6M7 13h4" /></>,
  claude: <path d="M10 2.5l1.8 5.7 5.7 1.8-5.7 1.8-1.8 5.7-1.8-5.7-5.7-1.8 5.7-1.8z" />,
  settings: <><circle cx="10" cy="10" r="2.6" /><path d="M10 2.5v2.2M10 15.3v2.2M2.5 10h2.2M15.3 10h2.2M4.7 4.7l1.6 1.6M13.7 13.7l1.6 1.6M4.7 15.3l1.6-1.6M13.7 6.3l1.6-1.6" /></>,
  plus: <path d="M10 4v12M4 10h12" />,
  search: <><circle cx="9" cy="9" r="5" /><path d="M13 13l4 4" /></>,
  folder: <path d="M2.5 6a1.5 1.5 0 011.5-1.5h3.5l2 2H16A1.5 1.5 0 0117.5 8v6.5A1.5 1.5 0 0116 16H4a1.5 1.5 0 01-1.5-1.5z" />,
  gear: <><circle cx="10" cy="10" r="2.4" /><path d="M10 3l1 2.2 2.4-.6.6 2.4L16.2 8l-1 2 1 2-2.2 1-.6 2.4-2.4-.6L10 17l-1-2.2-2.4.6-.6-2.4L3.8 12l1-2-1-2L6 7l.6-2.4 2.4.6z" /></>,
  more: <><circle cx="4.5" cy="10" r="1.2" fill="currentColor" /><circle cx="10" cy="10" r="1.2" fill="currentColor" /><circle cx="15.5" cy="10" r="1.2" fill="currentColor" /></>,
  chevron: <path d="M7 5l5 5-5 5" />,
  minimize: <path d="M5 10h10" />,
  maximize: <rect x="5" y="5" width="10" height="10" rx="1.5" />,
  close: <path d="M5.5 5.5l9 9M14.5 5.5l-9 9" />,
  photo: <><rect x="3" y="4.5" width="14" height="11" rx="2" /><circle cx="7.5" cy="8.5" r="1.3" /><path d="M3.5 14l4-3.5 3 2.5 2.5-2 3.5 3" /></>,
  library: <><rect x="3" y="4.5" width="14" height="11" rx="2" /><path d="M3 11.5c3-2.6 5.5-2.6 7 0s4-2.6 7 0" /><circle cx="13" cy="7.8" r="1.1" /></>,
  team: <><circle cx="7.5" cy="7.5" r="2.3" /><circle cx="13.5" cy="8.5" r="1.8" /><path d="M3.5 15.5c.6-2.6 2.2-4 4-4s3.4 1.4 4 4M12 12.2c1.9-.6 3.8.5 4.5 3.3" /></>,
  clock: <><circle cx="10" cy="10" r="6.5" /><path d="M10 6.5V10l2.5 1.8" /></>,
  pin: <path d="M7 3h6l-1 5 3 3H5l3-3zM10 11v6" />,
};

export function Icon({ name, size = 18, color }: { name: string; size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"
      strokeLinecap="round" strokeLinejoin="round" style={{ color, flex: "none" }} aria-hidden>
      {P[name] ?? P.scene}
    </svg>
  );
}
