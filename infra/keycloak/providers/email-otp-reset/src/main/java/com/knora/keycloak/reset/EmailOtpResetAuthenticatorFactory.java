package com.knora.keycloak.reset;

import java.util.List;
import org.keycloak.Config;
import org.keycloak.authentication.Authenticator;
import org.keycloak.authentication.AuthenticatorFactory;
import org.keycloak.models.AuthenticationExecutionModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.provider.ProviderConfigProperty;

/** REQUIRED execution only; no persistent user credential or configurable budget bypass. */
public final class EmailOtpResetAuthenticatorFactory implements AuthenticatorFactory {
    @Override public String getId() { return "knora-reset-email-otp"; }
    @Override public Authenticator create(KeycloakSession session) { return new EmailOtpResetAuthenticator(); }
    @Override public String getDisplayType() { return "Knora Email OTP Reset"; }
    @Override public String getReferenceCategory() { return null; }
    @Override public boolean isConfigurable() { return false; }
    @Override public AuthenticationExecutionModel.Requirement[] getRequirementChoices() {
        return new AuthenticationExecutionModel.Requirement[] {AuthenticationExecutionModel.Requirement.REQUIRED};
    }
    @Override public boolean isUserSetupAllowed() { return false; }
    @Override public String getHelpText() { return "Email recovery code with shared Keycloak Vault key and fixed recovery budgets."; }
    @Override public List<ProviderConfigProperty> getConfigProperties() { return List.of(); }
    @Override public void init(Config.Scope config) { }
    @Override public void postInit(KeycloakSessionFactory factory) { }
    @Override public void close() { }
}
