package com.knora.keycloak.reset.persistence;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** Private durable fixed-window projection; rows are reset under lock, never leased/reused. */
@Entity
@Table(name = "KNORA_OTP_RECOVERY_WINDOW")
public class OtpRecoveryWindowEntity {
    @Id @Column(name = "ID", length = 160)
    private String id;
    @Column(name = "REALM_ID", nullable = false, length = 64)
    private String realmId;
    @Column(name = "KIND", nullable = false, length = 16)
    private String kind;
    @Column(name = "ANCHOR_MS", nullable = false)
    private long anchorMs;
    @Column(name = "ATTEMPTS", nullable = false)
    private int attempts;
    @Column(name = "SENDS", nullable = false)
    private int sends;
    @Column(name = "LAST_SEND_MS", nullable = false)
    private long lastSendMs;
}
