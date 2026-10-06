package com.knora.keycloak.reset;

import jakarta.persistence.EntityManager;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Objects;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Function;
import org.keycloak.connections.jpa.JpaConnectionProvider;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.utils.KeycloakModelUtils;

/** PostgreSQL adapter inside Keycloak ownership, pinned to Keycloak26.3.3's custom JPA SPI. */
public final class KeycloakOtpChallengeStore implements OtpChallengeStore {
    private static final long WINDOW_MS = 900_000;
    private static final long CODE_MS = 300_000;
    private static final long COOLDOWN_MS = 30_000;
    private static final long RETENTION_MS = 86_400_000;
    private final KeycloakSession caller;

    public KeycloakOtpChallengeStore(KeycloakSession caller) { this.caller = Objects.requireNonNull(caller); }

    @Override
    public SendResult reserve(SendRequest request) {
        if (!validScope(request.scope()) || request.reference().generation() < 1) return send(SendOutcome.INVALID, request, 0);
        try {
            cleanupExpired();
            return independent(em -> {
                String ipId = windowId(request.scope().realmId(), "ip", request.ipDigest());
                String accountId = windowId(request.scope().realmId(), "account", request.accountDigest());
                // All sends lock IP then account, including first-row admission.
                WindowRow ip = lockWindow(em, ipId, request.scope().realmId(), "ip");
                WindowRow account = lockWindow(em, accountId, request.scope().realmId(), "account");
                long now = now(em);
                ip = resetWindow(em, ip, now);
                account = resetWindow(em, account, now);
                ChallengeRow previous = challenge(em, request.reference().id(), true);
                if (request.previous() == null) {
                    if (previous != null || request.reference().generation() != 1) return send(SendOutcome.INVALID, request, 0);
                } else if (previous == null || !matches(previous, request.scope()) || previous.consumed()
                        || previous.failed() || previous.generation() != request.previous().generation()
                        || !request.reference().id().equals(request.previous().id())
                        || request.reference().generation() != request.previous().generation() + 1
                        || !previous.accountId().equals(accountId)) {
                    return send(SendOutcome.INVALID, request, 0);
                }
                if (account.attempts() >= 5 || account.sends() >= 3 || ip.sends() >= 20)
                    return send(SendOutcome.EXHAUSTED, request, 0);
                long remaining = account.lastSendMs() + COOLDOWN_MS - now;
                if (remaining > 0) return send(SendOutcome.COOLDOWN, request, (int) ((remaining + 999) / 1000));
                em.createNativeQuery("update KNORA_OTP_RECOVERY_WINDOW set SENDS=SENDS+1,LAST_SEND_MS=:now where ID=:id")
                        .setParameter("now", now).setParameter("id", accountId).executeUpdate();
                em.createNativeQuery("update KNORA_OTP_RECOVERY_WINDOW set SENDS=SENDS+1 where ID=:id")
                        .setParameter("id", ipId).executeUpdate();
                if (previous == null) {
                    em.createNativeQuery("insert into KNORA_OTP_CHALLENGE "
                            + "(ID,REALM_ID,CLIENT_ID,AUTH_SESSION_ID,TAB_ID,EMAIL_DIGEST,ACCOUNT_ID,IP_ID,USER_ID,"
                            + "CODE_DIGEST,GENERATION,EXPIRES_MS,CONSUMED,DELIVERY_FAILED,DELIVERY_STATE) "
                            + "values (:id,:realm,:client,:auth,:tab,:email,:account,:ip,:user,:digest,:generation,:expires,false,false,'PENDING')")
                            .setParameter("id", request.reference().id()).setParameter("realm", request.scope().realmId())
                            .setParameter("client", request.scope().clientId()).setParameter("auth", request.scope().authSessionId())
                            .setParameter("tab", request.scope().tabId()).setParameter("email", request.scope().emailDigest())
                            .setParameter("account", accountId).setParameter("ip", ipId).setParameter("user", request.userId())
                            .setParameter("digest", request.codeDigest()).setParameter("generation", request.reference().generation())
                            .setParameter("expires", now + CODE_MS).executeUpdate();
                } else {
                    em.createNativeQuery("update KNORA_OTP_CHALLENGE set CODE_DIGEST=:digest,GENERATION=:generation,"
                            + "EXPIRES_MS=:expires,IP_ID=:ip,USER_ID=:user,DELIVERY_STATE='PENDING',ACTIVATION_OP=null where ID=:id")
                            .setParameter("digest", request.codeDigest()).setParameter("generation", request.reference().generation())
                            .setParameter("expires", now + CODE_MS).setParameter("ip", ipId).setParameter("user", request.userId())
                            .setParameter("id", request.reference().id()).executeUpdate();
                }
                return send(SendOutcome.SENT, request, 0);
            });
        } catch (RuntimeException unavailable) {
            // Includes ambiguous commit/resume. No permission to mail is returned.
            return send(SendOutcome.UNAVAILABLE, request, 0);
        }
    }

    @Override
    public ActivationOutcome activate(ChallengeScope scope, ChallengeReference reference, String operationId) {
        return activation(scope, reference, operationId, true);
    }

    @Override
    public ActivationOutcome reconcileActivation(ChallengeScope scope, ChallengeReference reference, String operationId) {
        return activation(scope, reference, operationId, false);
    }

    private ActivationOutcome activation(ChallengeScope scope, ChallengeReference reference, String operationId, boolean write) {
        if (!validScope(scope) || reference == null || operationId == null
                || !operationId.matches("[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"))
            return ActivationOutcome.INVALID;
        try {
            return independent(em -> {
                ChallengeRow observed = challenge(em, reference.id(), false);
                if (observed == null || !matches(observed, scope)
                        || existingWindow(em, observed.accountId(), scope.realmId(), "account") == null)
                    return ActivationOutcome.INVALID;
                ChallengeRow current = challenge(em, reference.id(), true);
                if (current == null || !matches(current, scope) || current.generation() != reference.generation()
                        || current.consumed() || current.failed() || now(em) >= current.expiresMs())
                    return ActivationOutcome.INVALID;
                if ("ACTIVE".equals(current.state()))
                    return operationId.equals(current.activationOp()) ? ActivationOutcome.ACTIVE : ActivationOutcome.INVALID;
                if (!write || !"PENDING".equals(current.state())) return ActivationOutcome.INVALID;
                em.createNativeQuery("update KNORA_OTP_CHALLENGE set DELIVERY_STATE='ACTIVE',ACTIVATION_OP=:operation where ID=:id")
                        .setParameter("operation", operationId).setParameter("id", reference.id()).executeUpdate();
                return ActivationOutcome.ACTIVE;
            });
        } catch (RuntimeException unavailable) { return ActivationOutcome.UNAVAILABLE; }
    }

    @Override
    public VerifyResult verify(ChallengeScope scope, ChallengeReference reference, String submittedDigest) {
        if (!validScope(scope)) return verified(VerifyOutcome.INVALID, null);
        try {
            return independent(em -> {
                ChallengeRow observed = challenge(em, reference.id(), false);
                if (observed == null || !matches(observed, scope)) return verified(VerifyOutcome.INVALID, null);
                WindowRow account = existingWindow(em, observed.accountId(), scope.realmId(), "account");
                if (account == null) return verified(VerifyOutcome.INVALID, null);
                ChallengeRow current = challenge(em, reference.id(), true);
                long now = now(em);
                if (current == null) return verified(VerifyOutcome.INVALID, null);
                account = resetWindow(em, account, now);
                if (account.attempts() >= 5) return verified(VerifyOutcome.EXHAUSTED, null);
                em.createNativeQuery("update KNORA_OTP_RECOVERY_WINDOW set ATTEMPTS=ATTEMPTS+1 where ID=:id")
                        .setParameter("id", account.id()).executeUpdate();
                if (current == null || !matches(current, scope) || current.generation() != reference.generation()
                        || current.consumed() || current.failed() || !"ACTIVE".equals(current.state())) return verified(VerifyOutcome.INVALID, null);
                if (now >= current.expiresMs()) return verified(VerifyOutcome.EXPIRED, null);
                if (current.userId() == null || submittedDigest == null || !MessageDigest.isEqual(
                        current.digest().getBytes(StandardCharsets.UTF_8), submittedDigest.getBytes(StandardCharsets.UTF_8)))
                    return verified(VerifyOutcome.INVALID, null);
                em.createNativeQuery("update KNORA_OTP_CHALLENGE set CONSUMED=true,CODE_DIGEST='',DELIVERY_STATE='CONSUMED' where ID=:id")
                        .setParameter("id", reference.id()).executeUpdate();
                return verified(VerifyOutcome.VERIFIED, current.userId());
            });
        } catch (RuntimeException unavailable) {
            return verified(VerifyOutcome.UNAVAILABLE, null);
        }
    }

    @Override
    public boolean deliveryFailed(ChallengeScope scope, ChallengeReference reference) {
        if (!validScope(scope)) return false;
        try {
            return independent(em -> {
                ChallengeRow observed = challenge(em, reference.id(), false);
                if (observed == null || !matches(observed, scope)) return false;
                if (existingWindow(em, observed.accountId(), scope.realmId(), "account") == null) return false;
                ChallengeRow current = challenge(em, reference.id(), true);
                if (current == null || current.consumed() || current.generation() != reference.generation()) return false;
                em.createNativeQuery("update KNORA_OTP_CHALLENGE set DELIVERY_FAILED=true,CODE_DIGEST='',DELIVERY_STATE='CANCELLED' where ID=:id")
                        .setParameter("id", reference.id()).executeUpdate();
                return true;
            });
        } catch (RuntimeException unavailable) { return false; }
    }

    private boolean validScope(ChallengeScope scope) {
        return scope != null && caller.getContext().getRealm() != null
                && caller.getContext().getRealm().getId().equals(scope.realmId());
    }

    private void cleanupExpired() {
        // Two bounded independent batches per admission. Cleanup failure never authorizes mail.
        independent(em -> {
            long cutoff = now(em) - RETENTION_MS;
            em.createNativeQuery("with candidates as (select ID from KNORA_OTP_CHALLENGE "
                    + "where REALM_ID=:realm and EXPIRES_MS<:cutoff order by EXPIRES_MS,ID "
                    + "limit 100 for update skip locked) delete from KNORA_OTP_CHALLENGE "
                    + "where ID in (select ID from candidates)")
                    .setParameter("realm", caller.getContext().getRealm().getId()).setParameter("cutoff", cutoff).executeUpdate();
            return null;
        });
        independent(em -> {
            long cutoff = now(em) - RETENTION_MS;
            var candidates = em.createNativeQuery("select ID from KNORA_OTP_RECOVERY_WINDOW windows "
                    + "where REALM_ID=:realm and KIND in ('ip','account') and ANCHOR_MS<:anchorCutoff "
                    + "and LAST_SEND_MS<:cutoff and not exists (select 1 from KNORA_OTP_CHALLENGE challenges "
                    + "where challenges.ACCOUNT_ID=windows.ID or challenges.IP_ID=windows.ID) "
                    + "order by case KIND when 'ip' then 0 else 1 end,ID limit 100 for update skip locked")
                    .setParameter("realm", caller.getContext().getRealm().getId()).setParameter("cutoff", cutoff)
                    .setParameter("anchorCutoff", cutoff - WINDOW_MS).getResultList();
            for (Object id : candidates) {
                // A fresh statement after row locks observes committed references from an earlier snapshot.
                em.createNativeQuery("delete from KNORA_OTP_RECOVERY_WINDOW windows where ID=:id "
                        + "and ANCHOR_MS<:anchorCutoff and LAST_SEND_MS<:cutoff "
                        + "and not exists (select 1 from KNORA_OTP_CHALLENGE challenges "
                        + "where challenges.ACCOUNT_ID=windows.ID or challenges.IP_ID=windows.ID)")
                        .setParameter("id", id).setParameter("cutoff", cutoff)
                        .setParameter("anchorCutoff", cutoff - WINDOW_MS).executeUpdate();
            }
            return null;
        });
    }

    private <T> T independent(Function<EntityManager, T> work) {
        AtomicReference<T> result = new AtomicReference<>();
        var completion = new java.util.concurrent.atomic.AtomicInteger(jakarta.transaction.Status.STATUS_UNKNOWN);
        var factory = caller.getKeycloakSessionFactory();
        var outerSession = org.keycloak.utils.KeycloakSessionUtil.getKeycloakSession();
        var lookup = caller.getProvider(org.keycloak.transaction.JtaTransactionManagerLookup.class);
        var tm = lookup.getTransactionManager();
        jakarta.transaction.Transaction outer;
        try { outer = tm.getTransaction(); }
        catch (jakarta.transaction.SystemException failed) { throw new IllegalStateException("Transaction context unavailable", failed); }
        KeycloakModelUtils.suspendJtaTransaction(factory, () -> {
            KeycloakModelUtils.setTransactionLimit(factory, 5);
            try {
                KeycloakModelUtils.runJobInTransactionWithResult(factory, caller.getContext(), session -> {
                    try {
                        var transaction = session.getProvider(org.keycloak.transaction.JtaTransactionManagerLookup.class)
                                .getTransactionManager().getTransaction();
                        if (transaction == null || transaction == outer) throw new IllegalStateException("Independent transaction missing");
                        transaction.registerSynchronization(new jakarta.transaction.Synchronization() {
                            public void beforeCompletion() { }
                            public void afterCompletion(int status) { completion.set(status); }
                        });
                    } catch (jakarta.transaction.RollbackException | jakarta.transaction.SystemException failed) {
                        throw new IllegalStateException("Transaction completion observation unavailable", failed);
                    }
                    var em = session.getProvider(JpaConnectionProvider.class).getEntityManager();
                    em.createNativeQuery("set local lock_timeout='2s'").executeUpdate();
                    em.createNativeQuery("set local statement_timeout='4s'").executeUpdate();
                    result.set(work.apply(em));
                    return null;
                }, "knora-otp-recovery-transition");
            } finally { KeycloakModelUtils.setTransactionLimit(factory, 0); }
        });
        try {
            if (completion.get() != jakarta.transaction.Status.STATUS_COMMITTED || tm.getTransaction() != outer
                    || org.keycloak.utils.KeycloakSessionUtil.getKeycloakSession() != outerSession)
                throw new IllegalStateException("Independent transition completion not confirmed");
        } catch (jakarta.transaction.SystemException failed) {
            throw new IllegalStateException("Restored transaction context unavailable", failed);
        }
        return result.get();
    }

    private static WindowRow lockWindow(EntityManager em, String id, String realm, String kind) {
        em.createNativeQuery("insert into KNORA_OTP_RECOVERY_WINDOW "
                + "(ID,REALM_ID,KIND,ANCHOR_MS,ATTEMPTS,SENDS,LAST_SEND_MS) values (:id,:realm,:kind,0,0,0,0) on conflict (ID) do nothing")
                .setParameter("id", id).setParameter("realm", realm).setParameter("kind", kind).executeUpdate();
        return Objects.requireNonNull(existingWindow(em, id, realm, kind));
    }

    private static WindowRow existingWindow(EntityManager em, String id, String realm, String kind) {
        var rows = em.createNativeQuery("select ID,ANCHOR_MS,ATTEMPTS,SENDS,LAST_SEND_MS "
                + "from KNORA_OTP_RECOVERY_WINDOW where ID=:id and REALM_ID=:realm and KIND=:kind for update")
                .setParameter("id", id).setParameter("realm", realm).setParameter("kind", kind).getResultList();
        if (rows.isEmpty()) return null;
        Object[] row = (Object[]) rows.get(0);
        return new WindowRow((String) row[0], number(row[1]), ((Number) row[2]).intValue(),
                ((Number) row[3]).intValue(), number(row[4]));
    }

    private static WindowRow resetWindow(EntityManager em, WindowRow row, long now) {
        if (now < row.anchorMs() + WINDOW_MS) return row;
        em.createNativeQuery("update KNORA_OTP_RECOVERY_WINDOW set ANCHOR_MS=:now,ATTEMPTS=0,SENDS=0 where ID=:id")
                .setParameter("now", now).setParameter("id", row.id()).executeUpdate();
        return new WindowRow(row.id(), now, 0, 0, row.lastSendMs());
    }

    private static ChallengeRow challenge(EntityManager em, String id, boolean lock) {
        var rows = em.createNativeQuery("select REALM_ID,CLIENT_ID,AUTH_SESSION_ID,TAB_ID,EMAIL_DIGEST,ACCOUNT_ID,"
                + "CODE_DIGEST,USER_ID,GENERATION,EXPIRES_MS,CONSUMED,DELIVERY_FAILED,DELIVERY_STATE,ACTIVATION_OP from KNORA_OTP_CHALLENGE where ID=:id"
                + (lock ? " for update" : "")).setParameter("id", id).getResultList();
        if (rows.isEmpty()) return null;
        Object[] row = (Object[]) rows.get(0);
        return new ChallengeRow((String) row[0], (String) row[1], (String) row[2], (String) row[3],
                (String) row[4], (String) row[5], (String) row[6], (String) row[7], number(row[8]),
                number(row[9]), (Boolean) row[10], (Boolean) row[11], (String) row[12], (String) row[13]);
    }

    private static boolean matches(ChallengeRow row, ChallengeScope scope) {
        return row.realmId().equals(scope.realmId()) && row.clientId().equals(scope.clientId())
                && row.authSessionId().equals(scope.authSessionId()) && row.tabId().equals(scope.tabId())
                && row.emailDigest().equals(scope.emailDigest());
    }

    private static String windowId(String realm, String kind, String digest) {
        try {
            return kind + ":" + HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest((realm + "\u0000" + kind + "\u0000" + digest).getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException impossible) { throw new IllegalStateException("SHA-256 unavailable", impossible); }
    }

    private static long now(EntityManager em) {
        return number(em.createNativeQuery("select floor(extract(epoch from clock_timestamp())*1000)::bigint").getSingleResult());
    }
    private static long number(Object value) { return ((Number) value).longValue(); }
    private static SendResult send(SendOutcome outcome, SendRequest request, int retry) {
        return new SendResult(outcome, request.reference(), retry);
    }
    private static VerifyResult verified(VerifyOutcome outcome, String user) { return new VerifyResult(outcome, user); }
    private record WindowRow(String id, long anchorMs, int attempts, int sends, long lastSendMs) { }
    private record ChallengeRow(String realmId, String clientId, String authSessionId, String tabId,
            String emailDigest, String accountId, String digest, String userId, long generation,
            long expiresMs, boolean consumed, boolean failed, String state, String activationOp) { }
}
