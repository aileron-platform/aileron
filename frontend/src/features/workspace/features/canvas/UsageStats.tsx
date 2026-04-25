/**
 * UsageStats - 使用統計組件
 *
 * 簡化顯示，只顯示總Token、輸入、輸出，並提供詳細資訊 Dialog
 */

import React from 'react';
import { BarChart3, Coins, Gauge, HardDrive, Layers, Clock, Cpu } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { Badge } from '@/shared/components/ui/badge';

// 模型使用數據
interface ModelUsageData {
  costUSD?: number;
  inputTokens?: number;
  outputTokens?: number;
}

interface UsageData {
  cache_read_input_tokens?: number;
  cache_creation_input_tokens?: number;
  service_tier?: string;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
}

interface TokenUsageSummary {
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  cache_creation_tokens?: number;
  cache_read_tokens?: number;
  cost_usd?: number;
  service_tier?: string;
}

interface UsageDataSummary {
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
  cacheCreationTokens?: number;
  cacheReadTokens?: number;
  costUsd?: number;
  serviceTier?: string;
}

interface MetadataSummary {
  model?: string | null;
  source?: string | null;
  tokens?: {
    input?: number | null;
    output?: number | null;
    cache_read?: number | null;
    cache_creation?: number | null;
  } | null;
}

interface RawContent {
  usage?: UsageData;
  usageData?: UsageDataSummary;
  token_usage?: TokenUsageSummary;
  modelUsage?: Record<string, ModelUsageData>;
  metadata?: MetadataSummary;
  duration_ms?: number;
  duration_api_ms?: number;
  total_cost_usd?: number;
  costUSD?: number;
  cost_usd?: number;
  service_tier?: string;
  model?: string;
  response?: Record<string, any>;
}

export interface UsageStatsProps {
  rawContent?: RawContent;
}

export const UsageStats: React.FC<UsageStatsProps> = ({ rawContent }) => {
  const { t } = useI18n();

  if (!rawContent) {
    return null;
  }

  const usage = rawContent.usage || {};
  const usageData = rawContent.usageData || {};
  const tokenUsage = rawContent.token_usage || {};
  const metadata = rawContent.metadata || {};
  const modelUsage = rawContent.modelUsage || {};
  const modelUsageEntries = Object.values(modelUsage);
  const modelHasInput = modelUsageEntries.some((model) => typeof model.inputTokens === 'number');
  const modelHasOutput = modelUsageEntries.some((model) => typeof model.outputTokens === 'number');
  const modelHasCost = modelUsageEntries.some((model) => typeof model.costUSD === 'number');
  const modelInputSum = modelUsageEntries.reduce((sum, model) => sum + (model.inputTokens || 0), 0);
  const modelOutputSum = modelUsageEntries.reduce((sum, model) => sum + (model.outputTokens || 0), 0);
  const modelCostSum = modelUsageEntries.reduce((sum, model) => sum + (model.costUSD || 0), 0);

  const pickNumber = (...values: Array<number | null | undefined>) => {
    return values.find((value) => typeof value === 'number' && !Number.isNaN(value));
  };

  const pickString = (...values: Array<string | null | undefined>) => {
    return values.find((value) => typeof value === 'string' && value.trim().length > 0);
  };

  const inputTokens = pickNumber(
    usageData.inputTokens,
    usage.input_tokens,
    tokenUsage.input_tokens,
    metadata.tokens?.input ?? undefined,
    modelHasInput ? modelInputSum : undefined,
  );

  const outputTokens = pickNumber(
    usageData.outputTokens,
    usage.output_tokens,
    tokenUsage.output_tokens,
    metadata.tokens?.output ?? undefined,
    modelHasOutput ? modelOutputSum : undefined,
  );

  const totalTokens = pickNumber(
    usageData.totalTokens,
    usage.total_tokens,
    tokenUsage.total_tokens,
  );

  const cacheReads = pickNumber(
    usageData.cacheReadTokens,
    usage.cache_read_input_tokens,
    tokenUsage.cache_read_tokens,
    metadata.tokens?.cache_read ?? undefined,
  );

  const cacheWrites = pickNumber(
    usageData.cacheCreationTokens,
    usage.cache_creation_input_tokens,
    tokenUsage.cache_creation_tokens,
    metadata.tokens?.cache_creation ?? undefined,
  );

  const resolvedTotalTokens = typeof totalTokens === 'number'
    ? totalTokens
    : (typeof inputTokens === 'number' || typeof outputTokens === 'number')
      ? (inputTokens || 0) + (outputTokens || 0)
      : undefined;

  const totalCacheTokens = (cacheReads || 0) + (cacheWrites || 0);

  const totalCostUsd = pickNumber(
    usageData.costUsd,
    rawContent.total_cost_usd,
    rawContent.costUSD,
    rawContent.cost_usd,
    tokenUsage.cost_usd,
    rawContent.response?.turn?.costs?.total_cost,
    rawContent.response?.turn?.costs?.total_cost_usd,
    modelHasCost ? modelCostSum : undefined,
  );

  const hasTokenData = [inputTokens, outputTokens, totalTokens, cacheReads, cacheWrites]
    .some((value) => typeof value === 'number');
  const hasCostData = typeof totalCostUsd === 'number';

  if (!hasTokenData && !hasCostData) {
    return null;
  }

  const modelName = pickString(rawContent.model, metadata.model || undefined);
  const serviceTier = pickString(
    usageData.serviceTier,
    usage.service_tier,
    tokenUsage.service_tier,
    rawContent.service_tier,
  );

  const durationMs = pickNumber(rawContent.duration_ms, rawContent.duration_api_ms);

  const statsLabel = t('workspace.canvas.usage.stats');
  const totalTokensLabel = t('workspace.canvas.usage.totalTokens');
  const inputLabel = t('workspace.canvas.usage.input');
  const outputLabel = t('workspace.canvas.usage.output');
  const costLabel = t('workspace.canvas.usage.cost');
  const cacheLabel = t('workspace.canvas.usage.cache');
  const tierLabel = t('workspace.canvas.usage.tier');
  const cacheReadLabel = t('workspace.canvas.usage.cacheRead');
  const cacheWriteLabel = t('workspace.canvas.usage.cacheWrite');
  const costUnavailable = t('workspace.canvas.usage.costUnavailable');
  const notAvailable = t('workspace.canvas.usage.notAvailable');
  const durationLabel = t('workspace.canvas.usage.duration');
  const providerLabel = t('workspace.canvas.usage.provider');
  const modelLabel = t('workspace.canvas.usage.model');

  const formatCount = (value?: number) => {
    if (typeof value !== 'number') return notAvailable;
    return value.toLocaleString();
  };

  const formatCost = (value?: number) => {
    if (typeof value !== 'number') return costUnavailable;
    return `$${value.toFixed(4)}`;
  };

  const formatDuration = (value?: number) => {
    if (typeof value !== 'number') return notAvailable;
    if (value >= 1000) {
      return `${(value / 1000).toFixed(1)}s`;
    }
    return `${value}ms`;
  };

  const hasCacheData = [cacheReads, cacheWrites].some((value) => typeof value === 'number');

  const metaItems: Array<{ key: string; label: string; value: string; icon: React.ElementType }> = [
    {
      key: 'cost',
      label: costLabel,
      value: formatCost(totalCostUsd),
      icon: Coins,
    },
  ];

  if (hasCacheData) {
    metaItems.push({
      key: 'cache',
      label: cacheLabel,
      value: formatCount(totalCacheTokens),
      icon: HardDrive,
    });
  }

  if (modelName) {
    metaItems.push({
      key: 'model',
      label: modelLabel,
      value: modelName,
      icon: Cpu,
    });
  }

  if (serviceTier) {
    metaItems.push({
      key: 'tier',
      label: tierLabel,
      value: serviceTier,
      icon: Gauge,
    });
  }

  return (
    <>
      <section className="mb-3 border-b border-border bg-card">
        <div className="flex h-10 items-center gap-4 px-4">
          <div className="flex items-center gap-3 whitespace-nowrap">
            <BarChart3 className="h-5 w-5 text-primary" />
            <div className="text-sm font-medium text-foreground">{statsLabel}</div>
          </div>

          <div className="min-w-0 flex-1 overflow-x-auto">
            <div className="flex items-center gap-3 text-xs text-muted-foreground whitespace-nowrap">
              <span className="text-xs text-muted-foreground">{totalTokensLabel}</span>
              <Badge variant="secondary" className="text-[11px]">
                {formatCount(resolvedTotalTokens)}
              </Badge>
              <span>
                {inputLabel} {formatCount(inputTokens)} · {outputLabel} {formatCount(outputTokens)}
              </span>
              {metaItems.map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.key} className="flex items-center gap-2">
                    <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                    <span>{item.label}</span>
                    <span className="font-medium text-foreground">{item.value}</span>
                  </div>
                );
              })}
            </div>
          </div>

        </div>
      </section>
    </>
  );
};

export default UsageStats;
