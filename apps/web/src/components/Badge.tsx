import type { ReactNode } from 'react'

const TONES: Record<string, string> = {
  PENDING: 'neutral',
  QUEUED: 'neutral',
  PROCESSING: 'amber',
  COMPLETED: 'green',
  FAILED: 'red',
  DRAFT: 'neutral',
  AI_RECONSTRUCTED: 'blue',
  AWAITING_REVIEW: 'amber',
  APPROVED: 'green',
  REJECTED: 'red',
  DISPUTED: 'red',
  ARCHIVED: 'neutral',
  RESTRICTED: 'red',
  DELETED: 'neutral',
}

export function statusTone(status: string): string {
  return TONES[status] ?? 'neutral'
}

export function Badge({ children, tone }: { children: ReactNode; tone?: string }) {
  return <span className={`badge badge-${tone ?? 'neutral'}`}>{children}</span>
}
