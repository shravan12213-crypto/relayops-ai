import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiGet, apiPost, type ApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/api/query-keys";

export type Role = "lead" | "outgoing" | "successor" | "contractor" | "auditor";

export interface User {
  id: string;
  email: string;
  name: string;
  role: Role;
  clearance: number; // 0, 1, 2, 3
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  user: User;
}

export function useCurrentUser() {
  return useQuery({
    queryKey: queryKeys.auth.me(),
    queryFn: ({ signal }) => apiGet<User>("/api/v1/auth/me", signal),
    staleTime: 60_000,
    retry: false,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (credentials: LoginCredentials) =>
      apiPost<LoginResponse>("/api/v1/auth/login", credentials),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.auth.me(), data.user);
      toast.success(`Welcome back, ${data.user.name}`);
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to sign in");
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => apiPost<{ ok: boolean }>("/api/v1/auth/logout"),
    onSuccess: () => {
      queryClient.setQueryData(queryKeys.auth.me(), null);
      queryClient.clear();
      toast.success("Signed out successfully");
    },
    onError: (error: ApiError) => {
      toast.error(error.message || "Failed to sign out");
    },
  });
}

export function useAuth() {
  const { data: user, isLoading, isError, error, refetch } = useCurrentUser();
  const loginMutation = useLogin();
  const logoutMutation = useLogout();

  return {
    user: user ?? null,
    isLoading,
    isAuthenticated: Boolean(user),
    isError,
    error,
    refetch,
    login: loginMutation.mutateAsync,
    logout: logoutMutation.mutateAsync,
    isLoggingIn: loginMutation.isPending,
    isLoggingOut: logoutMutation.isPending,
  };
}
