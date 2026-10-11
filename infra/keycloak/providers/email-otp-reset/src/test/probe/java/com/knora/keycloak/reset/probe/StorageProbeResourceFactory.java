package com.knora.keycloak.reset.probe;

import org.keycloak.Config;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.services.resource.RealmResourceProvider;
import org.keycloak.services.resource.RealmResourceProviderFactory;

/** Packaged only in the explicitly enabled test classifier, never the production artifact. */
public final class StorageProbeResourceFactory implements RealmResourceProviderFactory {
    @Override public RealmResourceProvider create(KeycloakSession session) {
        return new StorageProbeResource(session);
    }
    @Override public String getId() { return "knora-otp-storage-proof"; }
    @Override public void init(Config.Scope config) { }
    @Override public void postInit(KeycloakSessionFactory factory) { }
    @Override public void close() { }
}
