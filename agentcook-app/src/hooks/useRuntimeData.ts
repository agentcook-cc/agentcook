import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { runtimeApi } from "@/api/runtime";

/** Runtime info (auth mode, mock model, default agent). Cached for the session. */
export function useRuntimeInfo() {
  return useQuery({
    queryKey: ["runtime"],
    queryFn: runtimeApi.getRuntime,
    staleTime: 5 * 60_000,
    retry: 1,
  });
}

export function useAgents(enabled = true) {
  return useQuery({
    queryKey: ["agents"],
    queryFn: runtimeApi.listAgents,
    staleTime: 5 * 60_000,
    enabled,
  });
}

export function useToolkits(enabled = true) {
  return useQuery({
    queryKey: ["toolkits"],
    queryFn: runtimeApi.listToolkits,
    staleTime: 5 * 60_000,
    enabled,
  });
}

/** The caller's conversations, newest first, plus delete / rename. */
export function useConversations(enabled = true) {
  const client = useQueryClient();
  const list = useQuery({
    queryKey: ["conversations"],
    queryFn: () => runtimeApi.listConversations(100),
    enabled,
    staleTime: 10_000,
  });
  const invalidate = () => client.invalidateQueries({ queryKey: ["conversations"] });
  const remove = useMutation({
    mutationFn: runtimeApi.deleteConversation,
    onSuccess: invalidate,
  });
  const rename = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => runtimeApi.renameConversation(id, title),
    onSuccess: invalidate,
  });
  return {
    conversations: list.data?.items ?? [],
    loading: list.isLoading,
    error: list.error,
    refresh: invalidate,
    remove: remove.mutateAsync,
    rename: rename.mutateAsync,
  };
}
