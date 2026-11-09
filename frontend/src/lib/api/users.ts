import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api/client";
import { type User } from "@/lib/api/auth";

export function useUsers() {
  return useQuery({
    queryKey: ["users", "list"],
    queryFn: ({ signal }) => apiGet<User[]>("/api/v1/users", signal),
  });
}
