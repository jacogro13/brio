// The signed-in user's profile (`GET /auth/me`): the source of truth for the
// UI language across devices.
import { useQuery } from "@tanstack/react-query";
import type { components } from "../api/schema";
import { useApi } from "./useApi";

export type Profile = components["schemas"]["ProfileResponse"];

export const profileKey = ["profile"] as const;

export function useProfile() {
  const api = useApi();
  return useQuery({
    queryKey: profileKey,
    queryFn: async (): Promise<Profile> => (await api.GET("/auth/me")).data!,
  });
}
