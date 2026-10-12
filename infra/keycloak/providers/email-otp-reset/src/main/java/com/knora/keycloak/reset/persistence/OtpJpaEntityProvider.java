package com.knora.keycloak.reset.persistence;

import org.keycloak.connections.jpa.entityprovider.JpaEntityProvider;

import java.util.List;

/** Pinned Keycloak custom entity extension. Retest on every Keycloak upgrade. */
public final class OtpJpaEntityProvider implements JpaEntityProvider {
    @Override
    public List<Class<?>> getEntities() {
        return List.of(OtpRecoveryWindowEntity.class, OtpChallengeEntity.class);
    }

    @Override
    public String getChangelogLocation() {
        return "META-INF/knora-otp-changelog.xml";
    }

    @Override
    public String getFactoryId() {
        return "knora-email-otp";
    }

    @Override
    public void close() {}
}
