import type { FiboModule, FiboEdgeType } from '../types';

export const ALL_MODULES: FiboModule[] = ['BusinessEntities', 'Securities', 'Regulatory', 'Indicators'];

export const MODULE_LABELS: Record<FiboModule, string> = {
  BusinessEntities: 'Business Entities',
  Securities: 'Securities',
  Regulatory: 'Regulatory',
  Indicators: 'Indicators',
};

export const MODULE_COLORS: Record<FiboModule, string> = {
  BusinessEntities: 'bg-amber-400',
  Securities: 'bg-emerald-400',
  Regulatory: 'bg-rose-400',
  Indicators: 'bg-sky-400',
};

export const MODULE_TEXT_COLORS: Record<FiboModule, string> = {
  BusinessEntities: 'text-amber-400',
  Securities: 'text-emerald-400',
  Regulatory: 'text-rose-400',
  Indicators: 'text-sky-400',
};

export const MODULE_BORDER_COLORS: Record<FiboModule, string> = {
  BusinessEntities: 'border-amber-400',
  Securities: 'border-emerald-400',
  Regulatory: 'border-rose-400',
  Indicators: 'border-sky-400',
};

export const MODULE_HEX: Record<FiboModule, string> = {
  BusinessEntities: '#fbbf24',
  Securities: '#34d399',
  Regulatory: '#fb7185',
  Indicators: '#38bdf8',
};

export const EDGE_OPTIONS: { value: FiboEdgeType; label: string }[] = [
  { value: 'issuedBy', label: 'issued by' },
  { value: 'denominatedIn', label: 'denominated in' },
  { value: 'hasDomicile', label: 'has domicile' },
  { value: 'regulates', label: 'regulates' },
  { value: 'hasBenchmark', label: 'has benchmark' },
  { value: 'tracks', label: 'tracks' },
];

export const FIBO_CLASSES: Record<FiboModule, string[]> = {
  BusinessEntities: ['fibo-be-ge-ge:BusinessCenter', 'fibo-be-ge-ge:Bank', 'fibo-be-le-lp:LegalEntity'],
  Securities: ['fibo-sec-sec-dbt:BondInstrument', 'fibo-sec-sec-cls:Currency', 'fibo-sec-sec-cls:Security'],
  Regulatory: ['fibo-fbc-fct-fct:RegulatoryAgency', 'fibo-fbc-fct-fct:Regulation'],
  Indicators: ['fibo-ind-ind-ind:MarketIndex', 'fibo-ind-ei-ei:EconomicIndicator'],
};

export const PROPERTY_KEYS: string[] = ['isin', 'lei', 'jurisdiction', 'rating', 'maturity', 'currency', 'sector'];