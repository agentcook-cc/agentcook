import { useCallback, useEffect, useRef, useState } from "react";
import { javaClient } from "@/api/client";

interface QuotaApiResponse {
  free_questions_used: number;
  free_questions_quota: number;
}

export interface QuotaState {
  used: number;
  quota: number;
  remaining: number;
  isExhausted: boolean;
  loading: boolean;
  error: string | null;
}

export interface QuotaHook extends QuotaState {
  refetch: () => Promise<void>;
}

const DEFAULT_QUOTA = 2;
const POLL_INTERVAL_MS = 30_000;

export function useQuota(enabled = true): QuotaHook {
  const [state, setState] = useState<QuotaState>({
    used: 0,
    quota: DEFAULT_QUOTA,
    remaining: DEFAULT_QUOTA,
    isExhausted: false,
    loading: enabled,
    error: null,
  });
  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;

  const refetch = useCallback(async () => {
    if (!enabledRef.current) return;
    try {
      const data = await javaClient.get<QuotaApiResponse>("/api/v1/quota");
      const remaining = Math.max(
        0,
        data.free_questions_quota - data.free_questions_used,
      );
      setState({
        used: data.free_questions_used,
        quota: data.free_questions_quota,
        remaining,
        isExhausted: remaining === 0,
        loading: false,
        error: null,
      });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : "Failed to fetch quota",
      }));
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    refetch();
    const id = setInterval(refetch, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [enabled, refetch]);

  return { ...state, refetch };
}
