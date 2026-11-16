export type AuthProvider = "keycloak" | "supabase";

export function getAuthProvider(): AuthProvider {
  return process.env.KNORA_AUTH_PROVIDER === "supabase"
    ? "supabase"
    : "keycloak";
}
