interface BallProps {
  value: number
  tone?: 'red' | 'blue'
  size?: number
  dim?: boolean
  highlight?: 'hot' | 'cold'
}

export function Ball({ value, tone = 'red', size = 34, dim = false, highlight }: BallProps) {
  return (
    <span
      className={`ball ball-${tone}${dim ? ' ball-dim' : ''}${highlight ? ` ball-${highlight}` : ''}`}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.4) }}
      title={highlight === 'hot' ? '近 30 期热号' : highlight === 'cold' ? '近 30 期冷号' : undefined}
    >
      {String(value).padStart(2, '0')}
    </span>
  )
}
