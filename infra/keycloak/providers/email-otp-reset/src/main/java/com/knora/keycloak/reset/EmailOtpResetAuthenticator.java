package com.knora.keycloak.reset;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Clock;
import java.util.Arrays;
import java.util.Base64;
import java.util.HexFormat;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.keycloak.authentication.AuthenticationFlowContext;
import org.keycloak.authentication.Authenticator;
import org.keycloak.email.EmailException;
import org.keycloak.email.EmailTemplateProvider;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.RealmModel;
import org.keycloak.models.UserModel;
import org.keycloak.services.managers.AuthenticationManager;
import org.keycloak.sessions.AuthenticationSessionModel;

/** Translates native reset POSTs. Policy, budgets, activation and consume belong to the service/store. */
public final class EmailOtpResetAuthenticator implements Authenticator {
    private static final String PREFIX = "knora.emailOtp.";
    private final Function<KeycloakSession, OtpChallengeStore> stores;
    private final OtpChallengeService.CodeGenerator codes;
    private final Clock clock;

    public EmailOtpResetAuthenticator() {
        this(KeycloakOtpChallengeStore::new, OtpChallengeService.secureGenerator(new SecureRandom()), Clock.systemUTC());
    }

    EmailOtpResetAuthenticator(Function<KeycloakSession, OtpChallengeStore> stores,
            OtpChallengeService.CodeGenerator codes, Clock clock) {
        this.stores = stores;
        this.codes = codes;
        this.clock = clock;
    }

    @Override
    public void authenticate(AuthenticationFlowContext context) {
        context.clearUser();
        context.getAuthenticationSession().removeAuthNote(AuthenticationManager.END_AFTER_REQUIRED_ACTIONS);
        render(context, false, false);
    }

    @Override
    public void action(AuthenticationFlowContext context) {
        var parameters = context.getHttpRequest().getDecodedFormParameters();
        String intent = single(parameters, "intent", 32);
        var auth = context.getAuthenticationSession();
        context.clearUser();
        auth.removeAuthNote(AuthenticationManager.END_AFTER_REQUIRED_ACTIONS);
        if ("change-email".equals(intent)) {
            clear(auth);
            render(context, false, false);
            return;
        }
        if (!"request".equals(intent) && !"resend".equals(intent) && !"verify".equals(intent)) {
            render(context, true, false);
            return;
        }
        var reference = reference(auth);
        String email = "request".equals(intent) ? normalize(single(parameters, "email", 254))
                : normalize(auth.getAuthNote(PREFIX + "email"));
        if (!validEmail(email) || (!"request".equals(intent) && reference == null)) {
            clear(auth);
            render(context, false, true);
            return;
        }
        // Repeated request POST cannot replace the current phase. Resend uses the committed generation fence.
        if ("request".equals(intent) && reference != null) {
            render(context, false, false);
            return;
        }
        try (var digest = digest(context.getSession(), context.getRealm().getId())) {
            var scope = scope(context, email, digest);
            String remote = context.getConnection().getRemoteAddr();
            if (remote == null || remote.isBlank()) throw new IllegalStateException("Trusted connection unavailable");
            String ip = digest.account(scope.realmId(), "ip:" + remote);
            var service = service(context, email, ip, digest);
            OtpChallengeService.RenderResult result;
            if ("verify".equals(intent)) {
                String code = single(parameters, "code", 64);
                result = service.verify(scope, reference, code);
                if (result.verifiedUserId() != null) {
                    UserModel user = context.getSession().users().getUserById(context.getRealm(), result.verifiedUserId());
                    if (user != null && user.isEnabled() && email.equals(normalize(user.getEmail()))) {
                        clear(auth);
                        context.setUser(user);
                        auth.setAuthNote(AuthenticationManager.END_AFTER_REQUIRED_ACTIONS, Boolean.TRUE.toString());
                        context.success();
                        return;
                    }
                }
                render(context, true, false);
                return;
            }
            result = "resend".equals(intent) ? service.resend(scope, reference) : service.request(scope, email);
            var renderedReference = result.reference() != null ? result.reference() : reference;
            if (renderedReference == null) renderedReference = new OtpChallengeStore.ChallengeReference(UUID.randomUUID().toString(), 1);
            remember(auth, email, renderedReference,
                    result.retryAfterSeconds(), result.displayExpiresAt());
            render(context, false, false);
        } catch (RuntimeException unavailable) {
            // Missing key/provider or transport failure never permits success or store/SMTP fallback.
            if ("request".equals(intent))
                remember(auth, email, new OtpChallengeStore.ChallengeReference(UUID.randomUUID().toString(), 1),
                        30, clock.millis() + 300_000);
            render(context, "verify".equals(intent), false);
        }
    }

    private OtpChallengeService service(AuthenticationFlowContext context, String email, String ip, RequestDigest digest) {
        var session = context.getSession();
        var realm = context.getRealm();
        var lookup = new OtpChallengeService.AccountLookup() {
            public OtpChallengeService.Recipient byEmail(String address) {
                return recipient(session.users().getUserByEmail(realm, address));
            }
            public OtpChallengeService.Recipient byId(String id) {
                return recipient(session.users().getUserById(realm, id));
            }
        };
        OtpChallengeService.MailSender sender = (recipient, code) -> {
            UserModel user = session.users().getUserById(realm, recipient.id());
            if (user == null || !user.isEnabled() || !email.equals(normalize(user.getEmail())))
                throw new IllegalStateException("Recovery recipient changed");
            try {
                session.getProvider(EmailTemplateProvider.class).setRealm(realm).setUser(user)
                        .setAuthenticationSession(context.getAuthenticationSession())
                        .send("knoraResetOtpSubject", "knora-reset-otp.ftl", Map.of("code", code, "expirationMinutes", 5));
            } catch (EmailException failure) { throw new IllegalStateException("Recovery delivery unavailable"); }
        };
        return new OtpChallengeService(stores.apply(session), lookup, codes, digest, sender, clock,
                () -> UUID.randomUUID().toString(), ip, email);
    }

    private static OtpChallengeService.Recipient recipient(UserModel user) {
        return user == null ? null : new OtpChallengeService.Recipient(user.getId(), user.getEmail(), user.isEnabled());
    }

    private static OtpChallengeStore.ChallengeScope scope(AuthenticationFlowContext context, String email,
            OtpChallengeService.KeyedDigest digest) {
        var auth = context.getAuthenticationSession();
        String realm = context.getRealm().getId();
        return new OtpChallengeStore.ChallengeScope(realm, auth.getClient().getId(), auth.getParentSession().getId(),
                auth.getTabId(), digest.email(realm, email));
    }

    private static RequestDigest digest(KeycloakSession session, String realm) {
        try {
            String entry = "knora-email-otp-hmac-" + HexFormat.of().formatHex(
                    MessageDigest.getInstance("SHA-256").digest(realm.getBytes(StandardCharsets.UTF_8)));
            try (var secret = session.vault().getStringSecret("${vault." + entry + "}")) {
                String encoded = secret.get().orElseThrow(() -> new IllegalStateException("Recovery key missing"));
                if (encoded.length() > 4096) throw new IllegalStateException("Recovery key malformed");
                byte[] bytes = Base64.getDecoder().decode(encoded.strip());
                try { return new RequestDigest(bytes); }
                finally { Arrays.fill(bytes, (byte) 0); }
            }
        } catch (java.security.GeneralSecurityException failed) {
            throw new IllegalStateException("Recovery digest unavailable");
        }
    }

    private static final class RequestDigest implements OtpChallengeService.KeyedDigest, AutoCloseable {
        private Mac mac;
        RequestDigest(byte[] bytes) throws java.security.GeneralSecurityException {
            if (bytes.length < 32) throw new IllegalArgumentException("Recovery key malformed");
            mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(bytes, "HmacSHA256"));
        }
        public String code(OtpChallengeStore.ChallengeScope scope, OtpChallengeStore.ChallengeReference reference,
                String account, String code) {
            if (mac == null) throw new IllegalStateException("Request digest closed");
            for (String value : new String[] {"knora-email-otp-v1", scope.realmId(), scope.clientId(),
                    scope.authSessionId(), scope.tabId(), scope.emailDigest(), reference.id(),
                    Long.toString(reference.generation()), account, code}) {
                byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
                mac.update(ByteBuffer.allocate(4).putInt(bytes.length).array());
                mac.update(bytes);
            }
            return HexFormat.of().formatHex(mac.doFinal());
        }
        public void close() { mac = null; } // Provider internals and immutable Strings are not guaranteed zeroizable.
    }

    private void remember(AuthenticationSessionModel auth, String email, OtpChallengeStore.ChallengeReference ref,
            int cooldown, long expiry) {
        auth.setAuthNote(PREFIX + "email", email);
        if (ref != null) {
            auth.setAuthNote(PREFIX + "id", ref.id());
            auth.setAuthNote(PREFIX + "generation", Long.toString(ref.generation()));
        }
        auth.setAuthNote(PREFIX + "retryAt", Long.toString(clock.millis() + Math.max(0, cooldown) * 1000L));
        auth.setAuthNote(PREFIX + "expiresAt", Long.toString(expiry));
    }

    private void render(AuthenticationFlowContext context, boolean invalid, boolean emailInvalid) {
        var auth = context.getAuthenticationSession();
        boolean otp = reference(auth) != null && validEmail(normalize(auth.getAuthNote(PREFIX + "email")));
        long retry = noteLong(auth, "retryAt");
        int seconds = (int) Math.max(0, Math.min(30, (retry - clock.millis() + 999) / 1000));
        var form = context.form().setAttribute("otpInvalid", otp && invalid).setAttribute("emailInvalid", emailInvalid)
                .setAttribute("maskedEmail", mask(auth.getAuthNote(PREFIX + "email")))
                .setAttribute("retryAfterSeconds", seconds);
        context.challenge(form.createForm(otp ? "knora-reset-otp.ftl" : "knora-reset-email.ftl"));
    }

    private static OtpChallengeStore.ChallengeReference reference(AuthenticationSessionModel auth) {
        String id = auth.getAuthNote(PREFIX + "id");
        long generation = noteLong(auth, "generation");
        return id != null && id.matches("[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}")
                && generation > 0 && generation < Long.MAX_VALUE ? new OtpChallengeStore.ChallengeReference(id, generation) : null;
    }

    private static long noteLong(AuthenticationSessionModel auth, String key) {
        try { return Long.parseLong(auth.getAuthNote(PREFIX + key)); }
        catch (RuntimeException malformed) { return 0; }
    }

    private static String single(jakarta.ws.rs.core.MultivaluedMap<String, String> parameters, String name, int max) {
        var values = parameters.get(name);
        return values != null && values.size() == 1 && values.get(0) != null && values.get(0).length() <= max
                ? values.get(0) : null;
    }

    private static String normalize(String email) { return email == null ? "" : email.strip().toLowerCase(Locale.ROOT); }
    private static boolean validEmail(String email) {
        return email.length() <= 254 && email.matches("[^\\s@\\p{Cntrl}]+@[^\\s@\\p{Cntrl}]+\\.[^\\s@\\p{Cntrl}]+");
    }
    private static String mask(String email) {
        String normalized = normalize(email);
        int at = normalized.lastIndexOf('@');
        return at > 0 ? normalized.substring(0, 1) + "***" + normalized.substring(at) : "";
    }
    private static void clear(AuthenticationSessionModel auth) {
        for (String key : new String[] {"email", "id", "generation", "retryAt", "expiresAt"}) auth.removeAuthNote(PREFIX + key);
    }
    @Override public boolean requiresUser() { return false; }
    @Override public boolean configuredFor(KeycloakSession session, RealmModel realm, UserModel user) { return true; }
    @Override public void setRequiredActions(KeycloakSession session, RealmModel realm, UserModel user) { }
    @Override public void close() { }
}
