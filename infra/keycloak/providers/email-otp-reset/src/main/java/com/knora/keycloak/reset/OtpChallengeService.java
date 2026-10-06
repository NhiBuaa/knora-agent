package com.knora.keycloak.reset;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.time.Clock;
import java.util.HexFormat;
import java.util.Locale;
import java.util.Objects;
import java.util.function.Supplier;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/** Recovery policy and mail ordering; the native Authenticator only translates its protocol. */
public final class OtpChallengeService {
    public record Recipient(String id, String email, boolean enabled) { }
    public record RenderResult(String messageKey, OtpChallengeStore.ChallengeReference reference,
                               int retryAfterSeconds, long displayExpiresAt, String verifiedUserId) { }
    public interface AccountLookup {
        Recipient byEmail(String email);
        Recipient byId(String id);
    }
    @FunctionalInterface public interface CodeGenerator { String generate(); }
    @FunctionalInterface public interface MailSender { void send(Recipient recipient, String code); }
    @FunctionalInterface public interface KeyedDigest {
        String code(OtpChallengeStore.ChallengeScope scope, OtpChallengeStore.ChallengeReference reference,
                    String account, String code);
        default String account(String realm, String identity) {
            return code(new OtpChallengeStore.ChallengeScope(realm, "account-budget", "", "", ""),
                    new OtpChallengeStore.ChallengeReference("account-budget", 0), identity, "");
        }
        default String email(String realm, String email) {
            return code(new OtpChallengeStore.ChallengeScope(realm, "email-scope", "", "", ""),
                    new OtpChallengeStore.ChallengeReference("email-scope", 0), normalize(email), "");
        }
    }

    private final OtpChallengeStore store;
    private final AccountLookup accounts;
    private final CodeGenerator generator;
    private final KeyedDigest digest;
    private final MailSender mail;
    private final Clock clock;
    private final Supplier<String> ids;
    private final String trustedIpDigest;
    private final String currentEmail;

    public OtpChallengeService(OtpChallengeStore store, AccountLookup accounts, CodeGenerator generator,
            KeyedDigest digest, MailSender mail, Clock clock, Supplier<String> ids,
            String trustedIpDigest, String currentEmail) {
        this.store = Objects.requireNonNull(store);
        this.accounts = Objects.requireNonNull(accounts);
        this.generator = Objects.requireNonNull(generator);
        this.digest = Objects.requireNonNull(digest);
        this.mail = Objects.requireNonNull(mail);
        this.clock = Objects.requireNonNull(clock);
        this.ids = Objects.requireNonNull(ids);
        this.trustedIpDigest = Objects.requireNonNull(trustedIpDigest);
        this.currentEmail = normalize(currentEmail);
    }

    public RenderResult request(OtpChallengeStore.ChallengeScope scope, String email) {
        return send(scope, normalize(email), new OtpChallengeStore.ChallengeReference(ids.get(), 1), null);
    }

    public RenderResult resend(OtpChallengeStore.ChallengeScope scope, OtpChallengeStore.ChallengeReference previous) {
        if (previous == null || previous.generation() < 1 || previous.generation() == Long.MAX_VALUE)
            return generic(previous, 30);
        return send(scope, currentEmail,
                new OtpChallengeStore.ChallengeReference(previous.id(), previous.generation() + 1), previous);
    }

    private RenderResult send(OtpChallengeStore.ChallengeScope scope, String email,
            OtpChallengeStore.ChallengeReference reference, OtpChallengeStore.ChallengeReference previous) {
        try {
            Recipient recipient = accounts.byEmail(email);
            if (recipient != null && !normalize(recipient.email()).equals(email)) recipient = null;
            // Budget identity for an existing account is stable even when its email or enabled state changes.
            String identity = recipient == null ? "decoy:" + email : "user:" + recipient.id();
            String accountDigest = digest.account(scope.realmId(), identity);
            String code = generator.generate();
            if (code == null || !code.matches("[0-9]{6}")) return generic(reference, 30);
            boolean deliverable = recipient != null && recipient.enabled();
            var request = new OtpChallengeStore.SendRequest(scope, reference, previous, accountDigest,
                    trustedIpDigest, deliverable ? recipient.id() : null, digest.code(scope, reference, identity, code));
            var reserved = store.reserve(request);
            if (reserved.outcome() == OtpChallengeStore.SendOutcome.SENT && deliverable) {
                try { mail.send(recipient, code); }
                catch (RuntimeException deliveryFailure) { store.deliveryFailed(scope, reference); }
            }
            // No reserve success is inferred from delivery, exception, timeout or an ambiguous outcome.
            return generic(reserved.outcome() == OtpChallengeStore.SendOutcome.SENT ? reference : previous,
                    reserved.retryAfterSeconds() > 0 ? reserved.retryAfterSeconds() : 30);
        } catch (RuntimeException unavailable) { return generic(previous, 30); }
    }

    public RenderResult verify(OtpChallengeStore.ChallengeScope scope,
            OtpChallengeStore.ChallengeReference reference, String code) {
        try {
            Recipient current = accounts.byEmail(currentEmail);
            String identity = current == null ? "decoy:" + currentEmail : "user:" + current.id();
            String submitted = code != null && code.matches("[0-9]{6}")
                    ? digest.code(scope, reference, identity, code) : "invalid-format";
            var verified = store.verify(scope, reference, submitted);
            if (verified.outcome() == OtpChallengeStore.VerifyOutcome.VERIFIED && verified.verifiedUserId() != null) {
                Recipient user = accounts.byId(verified.verifiedUserId());
                if (user != null && user.enabled() && currentEmail.equals(normalize(user.email())))
                    return new RenderResult("knoraOtpVerified", reference, 0, 0, user.id());
            }
        } catch (RuntimeException unavailable) { /* Uniform fail-closed render; no sensitive logging. */ }
        return new RenderResult("knoraOtpInvalid", reference, 0, 0, null);
    }

    private RenderResult generic(OtpChallengeStore.ChallengeReference reference, int retry) {
        return new RenderResult("knoraOtpGenericSent", reference, retry, clock.millis() + 300_000, null);
    }

    public static CodeGenerator secureGenerator(SecureRandom random) {
        Objects.requireNonNull(random);
        return () -> String.format(Locale.ROOT, "%06d", random.nextInt(1_000_000));
    }

    public static KeyedDigest hmacSha256(byte[] secret) {
        if (secret == null || secret.length < 32) throw new IllegalArgumentException("Recovery digest key must have32bytes");
        byte[] key = secret.clone();
        return (scope, reference, account, code) -> {
            try {
                Mac mac = Mac.getInstance("HmacSHA256");
                mac.init(new SecretKeySpec(key, "HmacSHA256"));
                for (String value : new String[] {"knora-email-otp-v1", scope.realmId(), scope.clientId(),
                        scope.authSessionId(), scope.tabId(), scope.emailDigest(), reference.id(),
                        Long.toString(reference.generation()), account, code}) {
                    byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
                    mac.update(ByteBuffer.allocate(4).putInt(bytes.length).array());
                    mac.update(bytes);
                }
                return HexFormat.of().formatHex(mac.doFinal());
            } catch (java.security.GeneralSecurityException failed) {
                throw new IllegalStateException("Recovery keyed digest unavailable", failed);
            }
        };
    }

    private static String normalize(String email) {
        return email == null ? "" : email.strip().toLowerCase(Locale.ROOT);
    }
}
