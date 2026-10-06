package com.knora.keycloak.reset.persistence;

import org.keycloak.Config;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.connections.jpa.entityprovider.JpaEntityProvider;
import org.keycloak.connections.jpa.entityprovider.JpaEntityProviderFactory;

public final class OtpJpaEntityProviderFactory implements JpaEntityProviderFactory {
    @Override public JpaEntityProvider create(KeycloakSession session) { return new OtpJpaEntityProvider(); }
    @Override public String getId() { return "knora-email-otp"; }
    @Override public void init(Config.Scope config) { }
    @Override public void postInit(KeycloakSessionFactory factory) { }
    @Override public void close() { }
}
