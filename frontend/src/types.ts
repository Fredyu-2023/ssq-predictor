export interface DrawOut {
  lottery_type: string
  issue: string
  draw_date: string
  reds: number[]
  blues: number[]
  sales_amount: number | null
  pool_balance: number | null
  prize1_count: number | null
}

export interface HistoryPageData {
  total: number
  page: number
  size: number
  items: DrawOut[]
}

export interface LotteryOut {
  type: string
  name: string
  red_count: number
  red_min: number
  red_max: number
  blue_count: number
  blue_min: number
  blue_max: number
  enabled: boolean
}

export interface SyncStatusItem {
  type: string
  name: string
  latest_issue: string | null
  latest_date: string | null
  total_count: number
  last_sync_at: string | null
  last_sync_status: string | null
  syncing: boolean
}

export interface SyncStatusResponse {
  lotteries: SyncStatusItem[]
}

export interface SyncRunResult {
  lottery_type: string
  status: string
  fetched_count: number
  inserted_count: number
  skipped_count: number
  latest_issue: string | null
  error_msg: string | null
  elapsed_ms: number
}

export interface SyncLogOut {
  id: number
  lottery_type: string
  started_at: string
  finished_at: string | null
  status: string
  fetched_count: number
  inserted_count: number
  error_msg: string | null
}

export interface NumberCount {
  number: number
  count: number
}

export interface NumberOmission {
  number: number
  omission: number
}

export interface PairCount {
  pair: string
  count: number
  parts: number[]
}

export interface DistributionItem {
  label: string
  count: number
  parts: number[] | null
}

export interface SumStats {
  min: number
  max: number
  mean: number
}

export interface StatsOut {
  lottery_type: string
  range: string
  window: number
  draws_total: number
  first_issue: string | null
  last_issue: string | null
  red_freq: NumberCount[]
  blue_freq: NumberCount[]
  red_omission: NumberOmission[]
  blue_omission: NumberOmission[]
  hot_red: NumberCount[]
  cold_red: NumberCount[]
  hot_blue: NumberCount[]
  cold_blue: NumberCount[]
  consecutive: PairCount[]
  odd_even: DistributionItem[]
  big_small: DistributionItem[]
  zone_ratio: DistributionItem[]
  sum_distribution: DistributionItem[]
  sum_stats: SumStats
  ac_distribution: DistributionItem[]
  ac_avg: number
}

export interface StrategyOut {
  name: string
  description: string
  source: string
}

export interface BetOut {
  red: number[]
  blue: number
}

export interface PredictOut {
  strategy: string
  count: number
  numbers: BetOut[]
  disclaimer: string
}

export interface RedHitItem {
  hits: number
  count: number
  ratio: number
}

export interface PrizeLevelItem {
  level: number
  name: string
  condition: string
  actual: number
  expected: number
  probability: number
}

export interface ChiSquareBucket {
  label: string
  observed: number
  expected: number
}

export interface ChiSquareOut {
  statistic: number
  df: number
  p_value: number
  buckets: ChiSquareBucket[]
  conclusion: string
}

export interface BacktestOut {
  strategy: string
  window: number
  periods: number
  samples: number
  from_issue: string
  to_issue: string
  red_hits: RedHitItem[]
  avg_red_hits: number
  blue_hits: number
  blue_hit_rate: number
  blue_expected_rate: number
  prize_levels: PrizeLevelItem[]
  chi_square: ChiSquareOut
  disclaimer: string
}

export interface VisualizerOut {
  code: string
  name: string
  title: string
  category: string
  dimension: string
  status: string
  description: string
  mapping: string
}

export interface HarmonicItem {
  order: number
  number: number
  amplitude: number
  weight: number
}

export interface SpiralFourierData {
  points: [number, number][]
  normalized: boolean
  scale: number
  turns: number
  tightness: number
  pitch: number
  gain: number
  inner_radius: number
  harmonics: HarmonicItem[]
  reds: number[]
  blue: number
  red_max: number
  blue_max: number
  issue: string
}

export interface VisualizationOut<T = Record<string, unknown>> {
  type: string
  data: T
  metadata: Record<string, unknown>
}

export interface VisualizerFeaturesOut {
  code: string
  name: string
  features: Record<string, number>
}
