import type { ReactNode } from 'react'

const PATHS: Record<string, ReactNode> = {
  timeline: (
    <>
      <path d="M4 19V9" />
      <path d="M10 19V5" />
      <path d="M16 19v-7" />
      <path d="M22 19H2" />
    </>
  ),
  decades: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7v5l3 3" />
    </>
  ),
  places: (
    <>
      <path d="M12 21c4-4.5 7-8 7-11.5a7 7 0 1 0-14 0C5 13 8 16.5 12 21z" />
      <circle cx="12" cy="9.5" r="2.5" />
    </>
  ),
  chat: (
    <>
      <path d="M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9l-4 4v-4H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z" />
    </>
  ),
  people: (
    <>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M3.5 20c.8-3.5 3-5 5.5-5s4.7 1.5 5.5 5" />
      <circle cx="17" cy="9" r="2.8" />
      <path d="M16 15.5c2.3.2 3.9 1.6 4.5 4.5" />
    </>
  ),
  graph: (
    <>
      <circle cx="12" cy="5" r="2.2" />
      <circle cx="5" cy="18" r="2.2" />
      <circle cx="19" cy="18" r="2.2" />
      <path d="M11.2 7 5.7 16.2" />
      <path d="M12.8 7l5.5 9.2" />
      <path d="M7.2 18h9.6" />
    </>
  ),
  dashboard: (
    <>
      <path d="M5 20V10" />
      <path d="M12 20V4" />
      <path d="M19 20v-7" />
    </>
  ),
  sources: (
    <>
      <path d="M12 16V4" />
      <path d="m7.5 8.5 4.5-4.5 4.5 4.5" />
      <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
    </>
  ),
  review: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="3" />
      <path d="m8.5 12.5 2.5 2.5 4.5-5.5" />
    </>
  ),
  consent: (
    <>
      <path d="M12 3 4.5 6v5.5c0 5 3.2 8 7.5 9.5 4.3-1.5 7.5-4.5 7.5-9.5V6z" />
      <path d="m9 12 2.2 2.2L15.5 9.5" />
    </>
  ),
  safety: (
    <>
      <path d="M12 4 5 7v5c0 4.5 3 7.7 7 9 4-1.3 7-4.5 7-9V7z" />
      <path d="M12 9v3.5" />
      <path d="M12 15.8h.01" />
    </>
  ),
  admin: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1" />
    </>
  ),
  bell: (
    <>
      <path d="M18 9a6 6 0 1 0-12 0c0 5-2 6-2 6h16s-2-1-2-6" />
      <path d="M10 19a2 2 0 0 0 4 0" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  x: <path d="m6 6 12 12M18 6 6 18" />,
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  arrowLeft: <path d="M19 12H5M11 6l-6 6 6 6" />,
  chevronDown: <path d="m6 9.5 6 6 6-6" />,
  download: (
    <>
      <path d="M12 4v11" />
      <path d="m7.5 11.5 4.5 4.5 4.5-4.5" />
      <path d="M4 20h16" />
    </>
  ),
  upload: (
    <>
      <path d="M12 16V5" />
      <path d="m7.5 9.5 4.5-4.5 4.5 4.5" />
      <path d="M4 15v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
    </>
  ),
  send: <path d="M4 12 20 4l-6 16-2.5-6.5z" />,
  stop: <rect x="7" y="7" width="10" height="10" rx="2" />,
  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m20 20-3.8-3.8" />
    </>
  ),
  file: (
    <>
      <path d="M6 3h8l4 4v14H6z" />
      <path d="M14 3v4h4" />
      <path d="M9 12h6M9 16h6" />
    </>
  ),
  image: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="3" />
      <circle cx="9" cy="9" r="1.6" />
      <path d="m5 17 4.5-4.5L13 16l2.5-2.5L19 17" />
    </>
  ),
  film: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="3" />
      <path d="M4 9h16M4 15h16M9 4v16M15 4v16" />
    </>
  ),
  mic: (
    <>
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0" />
      <path d="M12 18v3" />
    </>
  ),
  edit: (
    <>
      <path d="M4 20h4.5L19.5 9a2 2 0 0 0-3-3L5.5 16.5z" />
      <path d="m14.5 7 3 3" />
    </>
  ),
  trash: (
    <>
      <path d="M4 7h16" />
      <path d="M9 7V4.5A1.5 1.5 0 0 1 10.5 3h3A1.5 1.5 0 0 1 15 4.5V7" />
      <path d="M6 7v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7" />
      <path d="M10 11v6M14 11v6" />
    </>
  ),
  link: (
    <>
      <path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1.6 1.6" />
      <path d="M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1.6-1.6" />
    </>
  ),
  heart: (
    <path d="M12 20.5s-7.5-4.8-9-9.3C1.9 7.2 4.4 4.5 7.4 4.5c1.9 0 3.3 1 4.6 2.7 1.3-1.7 2.7-2.7 4.6-2.7 3 0 5.5 2.7 4.4 6.7-1.5 4.5-9 9.3-9 9.3z" />
  ),
}

export function Icon({
  name,
  size = 20,
  className,
}: {
  name: keyof typeof PATHS | string
  size?: number
  className?: string
}) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  )
}
