package com.knora.keycloak.reset.persistence;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** Private digest-only challenge; changes serialize with its stable account window. */
@Entity
@Table(name = "KNORA_OTP_CHALLENGE")
public class OtpChallengeEntity {
    @Id @Column(name = "ID", length = 160) private String id;
    @Column(name = "REALM_ID", nullable = false, length = 64) private String realmId;
    @Column(name = "CLIENT_ID", nullable = false, length = 160) private String clientId;
    @Column(name = "AUTH_SESSION_ID", nullable = false, length = 160) private String authSessionId;
    @Column(name = "TAB_ID", nullable = false, length = 160) private String tabId;
    @Column(name = "EMAIL_DIGEST", nullable = false, length = 160) private String emailDigest;
    @Column(name = "ACCOUNT_ID", nullable = false, length = 160) private String accountId;
    @Column(name = "IP_ID", nullable = false, length = 160) private String ipId;
    @Column(name = "USER_ID", length = 64) private String userId;
    @Column(name = "CODE_DIGEST", nullable = false, length = 160) private String codeDigest;
    @Column(name = "GENERATION", nullable = false) private long generation;
    @Column(name = "EXPIRES_MS", nullable = false) private long expiresMs;
    @Column(name = "CONSUMED", nullable = false) private boolean consumed;
    @Column(name = "DELIVERY_FAILED", nullable = false) private boolean deliveryFailed;
}
