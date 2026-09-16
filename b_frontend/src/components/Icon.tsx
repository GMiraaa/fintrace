import type { ReactNode } from 'react'

export type IconName = 'upload' | 'file' | 'check' | 'alert' | 'close' | 'eye' | 'download' | 'shield' | 'database'

interface IconProps {
  name: IconName
  size?: number
}

export function Icon({ name, size = 20 }: IconProps) {
  const paths: Record<IconName, ReactNode> = {
    upload: <path d="M12 16V4m0 0L7 9m5-5 5 5M5 15v4h14v-4" />,
    file: <path d="M6 2h8l4 4v16H6V2Zm8 0v5h5M9 12h6M9 16h6" />,
    check: <path d="m5 12 4 4L19 6" />,
    alert: <path d="M12 3 2.5 20h19L12 3Zm0 6v5m0 3v.01" />,
    close: <path d="m6 6 12 12M18 6 6 18" />,
    eye: <><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" /><circle cx="12" cy="12" r="2.5" /></>,
    download: <path d="M12 3v12m0 0 4-4m-4 4-4-4M5 19h14" />,
    shield: <path d="M12 3 5 6v5c0 4.6 2.8 8 7 10 4.2-2 7-5.4 7-10V6l-7-3Zm-3 9 2 2 4-4" />,
    database: <><ellipse cx="12" cy="5" rx="7" ry="3" /><path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" /></>,
  }
  return (
    <svg
      aria-hidden="true"
      className="icon"
      fill="none"
      height={size}
      viewBox="0 0 24 24"
      width={size}
    >
      <g stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8">
        {paths[name]}
      </g>
    </svg>
  )
}
