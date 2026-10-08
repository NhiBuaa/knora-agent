package com.knora.keycloak.reset;

import jakarta.ws.rs.core.MultivaluedHashMap;
import java.lang.reflect.Proxy;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Base64;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;
import java.nio.file.Path;
import java.nio.file.Files;
import java.io.StringWriter;
import java.util.Properties;
import freemarker.cache.ClassTemplateLoader;
import freemarker.cache.FileTemplateLoader;
import freemarker.cache.MultiTemplateLoader;
import freemarker.core.HTMLOutputFormat;
import freemarker.template.Configuration;
import freemarker.template.TemplateMethodModelEx;
import org.junit.jupiter.api.Test;
import org.keycloak.authentication.Authenticator;
import org.keycloak.authentication.AuthenticationFlowContext;
import org.keycloak.common.ClientConnection;
import org.keycloak.email.EmailTemplateProvider;
import org.keycloak.email.EmailException;
import org.keycloak.email.freemarker.FreeMarkerEmailTemplateProvider;
import org.keycloak.theme.Theme;
import org.keycloak.theme.freemarker.FreeMarkerProvider;
import org.keycloak.forms.login.LoginFormsProvider;
import org.keycloak.http.HttpRequest;
import org.keycloak.models.ClientModel;
import org.keycloak.models.KeycloakContext;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.RealmModel;
import org.keycloak.models.UserModel;
import org.keycloak.models.UserProvider;
import org.keycloak.services.managers.AuthenticationManager;
import org.keycloak.sessions.AuthenticationSessionModel;
import org.keycloak.sessions.RootAuthenticationSessionModel;
import org.keycloak.vault.VaultStringSecret;
import org.keycloak.vault.VaultTranscriber;
import static org.junit.jupiter.api.Assertions.*;

/** Offline native protocol translation only. This is not a deployed password recovery flow. */
class EmailOtpResetFlowIT {
    @Test
    void offlineCompletedInfoReturnsOnlyToTrustedAppOriginWithFreshSignIn() throws Exception {
        for (var configuredOrigin : List.of(
                Map.entry("https://app.example", "https://app.example"),
                Map.entry("https://app.example/old/path?code=private#fragment", "https://app.example"),
                Map.entry("http://127.0.0.1:3300/", "http://127.0.0.1:3300"),
                Map.entry("https://app.example:65535/old/path?code=private#fragment", "https://app.example:65535"),
                Map.entry("https://app.example:0/old/path?code=private#fragment", "https://app.example:0"),
                Map.entry("http://[::1]:3300/old/path?code=private#fragment", "http://[::1]:3300"),
                Map.entry("https://[1:2:3:4:5:6:7:8]/old/path?code=private#fragment", "https://[1:2:3:4:5:6:7:8]"),
                Map.entry("https://[2001:db8::1]/old/path?code=private#fragment", "https://[2001:db8::1]"),
                Map.entry("https://[1::]/old/path?code=private#fragment", "https://[1::]"),
                Map.entry("https://[::]/old/path?code=private#fragment", "https://[::]"),
                Map.entry("https://[::1]:65535/old/path?code=private#fragment", "https://[::1]:65535"),
                Map.entry("https://[::1]:0/old/path?code=private#fragment", "https://[::1]:0"))) {
            var data = templateData();
            data.put("client", Map.of("baseUrl", configuredOrigin.getKey()));
            data.put("message", Map.of("type", "success", "summary", "accountUpdatedMessage"));
            data.put("pageRedirectUri", "https://untrusted.example/?code=private");
            data.put("actionUri", "/native/unfinished");
            String html = render("login", "info.ftl", data);
            assertTrue(html.contains("href=\"" + configuredOrigin.getValue() + "/api/auth/login?prompt=login\""),
                    "Fresh sign-in link must retain only configured origin: " + configuredOrigin.getKey());
            assertFalse(html.contains("untrusted.example"));
            assertFalse(html.contains("code=private"));
            assertFalse(html.contains("/old/path"));
            assertFalse(html.contains("#fragment"));
            assertFalse(html.contains("href=\"/native/unfinished\""));
        }
    }

    @Test
    void offlineCompletedInfoFailsClosedWithoutSafeConfiguredAppOrigin() throws Exception {
        var checks = new ArrayList<org.junit.jupiter.api.function.Executable>();
        for (String baseUrl : List.of("", "javascript:alert(1)", "//evil.example", "https://app.example@evil.example",
                "https://app.example:65536", "http://127.0.0.1:99999/", "https://[123]", "https://[1:2:3]",
                "https://[1::2::3]", "https://[1:2:3:4:5:6:7:8:9]", "https://[::1]:65536")) {
            checks.add(() -> {
                var data = templateData();
                data.put("client", Map.of("baseUrl", baseUrl));
                data.put("message", Map.of("type", "success", "summary", "accountUpdatedMessage"));
                data.put("pageRedirectUri", "https://untrusted.example");
                data.put("actionUri", "/native/unfinished");
                String html = render("login", "info.ftl", data);
                assertFalse(java.util.regex.Pattern.compile("<a\\s[^>]*href=").matcher(html).find(),
                        "Invalid configured origin must not emit a link: " + baseUrl);
                assertFalse(html.contains("untrusted.example"));
                assertFalse(html.contains("href=\"/native/unfinished\""));
            });
        }
        assertAll(checks);
    }

    @Test
    void offlineUnfinishedInfoKeepsNativeActionAndRedirectLinks() throws Exception {
        var data = templateData();
        data.put("client", Map.of("baseUrl", "https://app.example"));
        data.put("message", Map.of("type", "warning", "summary", "Required action"));
        data.put("actionUri", "/native/unfinished");
        String html = render("login", "info.ftl", data);
        assertTrue(html.contains("href=\"/native/unfinished\""));
        assertFalse(html.contains("prompt=login"));
        data.put("pageRedirectUri", "/native/continue");
        html = render("login", "info.ftl", data);
        assertTrue(html.contains("href=\"/native/continue\""));
    }

    @Test
    void offlineInfoSkipLinkSuppressesCompletionAndNativeLinks() throws Exception {
        for (var message : List.of(Map.of("type", "success", "summary", "accountUpdatedMessage"),
                Map.of("type", "warning", "summary", "Required action"))) {
            for (boolean skipLink : List.of(true, false)) {
                var data = templateData();
                data.put("client", Map.of("baseUrl", "https://app.example"));
                data.put("message", message);
                data.put("pageRedirectUri", "/native/continue");
                data.put("actionUri", "/native/unfinished");
                data.put("skipLink", skipLink);
                String html = render("login", "info.ftl", data);
                assertFalse(java.util.regex.Pattern.compile("<a\\s[^>]*href=").matcher(html).find(),
                        "Presence of skipLink must suppress links regardless of its value or message");
            }
        }
    }

    @Test
    void offlineSharedKeyKeepsBudgetIdentityAcrossRequestsButSeparatesRealmAndTrustedIp() throws Exception {
        var first = new Fixture();
        first.post("request", "email", "known@example.test");
        var restart = new Fixture();
        restart.post("request", "email", "known@example.test");
        assertEquals(first.sent.accountDigest(), restart.sent.accountDigest());
        assertEquals(first.sent.ipDigest(), restart.sent.ipDigest());
        assertEquals(first.sent.scope().emailDigest(), restart.sent.scope().emailDigest());
        var otherRealm = new Fixture();
        otherRealm.realmId = "other-realm-id";
        otherRealm.post("request", "email", "known@example.test");
        assertNotEquals(first.vaultExpression, otherRealm.vaultExpression);
        assertNotEquals(first.sent.accountDigest(), otherRealm.sent.accountDigest());
        var otherIp = new Fixture();
        otherIp.remoteAddress = "192.0.2.6";
        otherIp.post("request", "email", "known@example.test");
        assertEquals(first.sent.accountDigest(), otherIp.sent.accountDigest());
        assertNotEquals(first.sent.ipDigest(), otherIp.sent.ipDigest());
        var changedEmail = new Fixture();
        changedEmail.email = "changed@example.test";
        changedEmail.post("request", "email", changedEmail.email);
        assertEquals(first.sent.accountDigest(), changedEmail.sent.accountDigest());
        assertNotEquals(first.sent.scope().emailDigest(), changedEmail.sent.scope().emailDigest());
        var rotated = new Fixture();
        byte[] key = new byte[32];
        java.util.Arrays.fill(key, (byte) 1);
        rotated.vaultValue = Base64.getEncoder().encodeToString(key);
        rotated.post("request", "email", "known@example.test");
        assertNotEquals(first.sent.accountDigest(), rotated.sent.accountDigest(), "Hot key rotation changes budget identity");
    }

    @Test
    void offlinePackagedFactoryIsRequiredOnlyAndCannotConfigureBudgetBypass() {
        var factory = java.util.ServiceLoader.load(org.keycloak.authentication.AuthenticatorFactory.class).stream()
                .filter(provider -> provider.type() == EmailOtpResetAuthenticatorFactory.class).findFirst().orElseThrow().get();
        assertEquals("knora-reset-email-otp", factory.getId());
        assertArrayEquals(new org.keycloak.models.AuthenticationExecutionModel.Requirement[] {
                org.keycloak.models.AuthenticationExecutionModel.Requirement.REQUIRED}, factory.getRequirementChoices());
        assertFalse(factory.isConfigurable());
        assertFalse(factory.isUserSetupAllowed());
        assertTrue(factory.getConfigProperties().isEmpty());
        assertFalse(factory.create(null).requiresUser());
    }
    @Test
    void offlinePinnedParentFreeMarkerRendersAccessibleNativePostFormsAndEscapesAddress() throws Exception {
        for (boolean error : List.of(false, true)) {
            Map<String, Object> data = templateData();
            data.put("otpInvalid", error);
            data.put("emailInvalid", error);
            data.put("maskedEmail", "<script>alert(1)</script>@example.test");
            data.put("retryAfterSeconds", error ? 0 : 30);
            String request = render("login", "knora-reset-email.ftl", data);
            assertTrue(request.contains("action=\"/native/action\" method=\"post\""));
            assertTrue(request.contains("name=\"email\""));
            assertTrue(request.contains("value=\"request\""));
            String otp = render("login", "knora-reset-otp.ftl", data);
            assertTrue(otp.contains("action=\"/native/action\" method=\"post\""));
            assertTrue(otp.contains("name=\"code\""));
            assertTrue(otp.contains("autocomplete=\"one-time-code\""));
            assertTrue(otp.contains("inputmode=\"numeric\""));
            assertFalse(otp.contains("type=\"number\""));
            assertFalse(otp.contains("<script>alert(1)</script>"));
            assertTrue(otp.contains("&lt;script&gt;alert(1)&lt;/script&gt;"));
            assertEquals(error, otp.contains("id=\"otp-error\""));
            assertFalse(java.util.regex.Pattern.compile("id=\"otp-resend\"[^>]*\\sdisabled[ >]").matcher(otp).find());
            assertTrue(otp.contains("value=\"change-email\""));
            assertTrue(otp.contains("value=\"resend\""));
        }
    }

    @Test
    void offlineResetPresentationUsesSourceCopyAndEscapedRuntimeAddress() throws Exception {
        var data = templateData();
        data.put("maskedEmail", "<script>alert(1)</script>@example.test");
        String request = render("login", "knora-reset-email.ftl", data);
        String otp = render("login", "knora-reset-otp.ftl", data);
        assertAll(
                () -> assertTrue(request.contains("Forgot your password?")),
                () -> assertTrue(request.contains("Send verification code")),
                () -> assertTrue(request.contains("Enter the email for your account. If an account exists, we’ll send a 6-digit verification code.")),
                () -> assertTrue(request.contains("Remembered it?")),
                () -> assertTrue(request.contains("For privacy, Knora won’t confirm whether an account exists for this email.")),
                () -> assertTrue(otp.contains("Enter verification code")),
                () -> assertTrue(otp.contains("Use a different email")),
                () -> assertTrue(otp.contains("If an account exists, we sent a 6-digit verification code to &lt;script&gt;alert(1)&lt;/script&gt;@example.test.")),
                () -> assertFalse(otp.contains("<script>alert(1)</script>")),
                () -> assertTrue(otp.contains("The code expires after 5 minutes.")));
        data.put("otpInvalid", true);
        assertTrue(render("login", "knora-reset-otp.ftl", data)
                .contains("Check the code or request a new one, then try again."));
    }

    @Test
    void offlinePasswordPresentationScopesResetActionAndRetainsNativeMacros() throws Exception {
        var data = templateData();
        TemplateMethodModelEx empty = args -> "";
        data.put("messagesPerField", Map.of("get", empty));
        data.put("passwordPolicies", Map.of("length", 12));
        String ordinary = render("login", "login-update-password.ftl", data);
        assertAll(
                () -> assertTrue(ordinary.contains("Choose a new password")),
                () -> assertTrue(ordinary.contains("Set a new password for your Knora account.")),
                () -> assertTrue(ordinary.contains("Confirm new password")),
                () -> assertTrue(ordinary.contains("Reset password")),
                () -> assertTrue(ordinary.contains("After resetting your password, sign in again with the new password.")));
        for (boolean appInitiated : List.of(false, true)) {
            data.put("isAppInitiatedAction", appInitiated);
            String app = render("login", "login-update-password.ftl", data);
            assertTrue(app.contains("doSubmit"));
            assertTrue(app.contains("doCancel"));
            assertTrue(app.contains("name=\"cancel-aia\""));
            assertFalse(app.contains("After resetting your password"));
            for (String html : List.of(ordinary, app)) {
                assertTrue(html.contains("action=\"/native/action\" method=\"post\""));
                assertTrue(html.contains("name=\"password-new\""));
                assertTrue(html.contains("name=\"password-confirm\""));
                assertTrue(html.contains("name=\"logout-sessions\""));
                assertTrue(html.contains("name=\"login\""));
                assertTrue(html.contains("/js/password-policy.js"));
                assertTrue(html.contains("value: 12"));
            }
        }
    }

    @Test
    void offlineOtpResendRemainsUsableWithoutJavaScriptDuringAndAfterCooldown() throws Exception {
        for (int retry : List.of(30, 61, 0)) {
            var data = templateData();
            data.put("retryAfterSeconds", retry);
            String html = render("login", "knora-reset-otp.ftl", data);
            var resend = java.util.regex.Pattern.compile("<button\\s[^>]*id=\"otp-resend\"[^>]*>").matcher(html);
            assertTrue(resend.find(), "Native resend button is present");
            String button = resend.group();
            assertFalse(java.util.regex.Pattern.compile("\\sdisabled(?:[\\s=>])").matcher(button).find(),
                    "Native resend must remain enabled when JavaScript is blocked, including during cooldown");
            assertTrue(button.contains("type=\"submit\""));
            assertTrue(button.contains("name=\"intent\" value=\"resend\""));
            assertTrue(button.contains("formnovalidate"));
            assertTrue(html.contains("action=\"/native/action\" method=\"post\""));
            assertTrue(html.contains("name=\"code\""));
            assertTrue(html.contains("value=\"verify\""));
            assertTrue(html.contains("value=\"change-email\""));
            assertEquals(retry > 0, html.contains("id=\"otp-retry\""),
                    "Positive server cooldown remains visible without JavaScript");
            assertTrue(button.contains("data-ready-label=\"Resend code\""));
            if (retry > 0) {
                String display = retry == 30 ? "00:30" : "01:01";
                assertTrue(html.contains("<span id=\"otp-resend-label\">Resend code in</span>"));
                assertTrue(html.contains("<span id=\"otp-retry\" data-seconds=\"" + retry + "\">" + display + "</span>"));
            } else {
                assertTrue(html.contains("<span id=\"otp-resend-label\">Resend code</span>"));
                assertFalse(html.contains("Resend code in</span>"));
            }
            assertTrue(html.contains("id=\"otp-expiry\""));
            assertFalse(html.contains("000042"), "The login form must not disclose an OTP");
        }
    }

    @Test
    void offlineEmailThemesRenderCodeAndExpiryWithoutRecoveryLink() throws Exception {
        var data = templateData();
        data.put("code", "000042");
        data.put("expirationMinutes", 5);
        for (String type : List.of("html", "text")) {
            String mail = render("email", type + "/knora-reset-otp.ftl", data);
            assertTrue(mail.contains("000042"));
            assertTrue(mail.contains("5 minutes"));
            assertFalse(mail.contains("href="));
            assertFalse(mail.contains("/native/action"));
        }
    }

    private static Path repository() { return Path.of(System.getProperty("user.dir")).toAbsolutePath().resolve("../../../../").normalize(); }
    private static Map<String, Object> templateData() throws Exception {
        var properties = new Properties();
        try (var input = EmailOtpResetFlowIT.class.getResourceAsStream("/theme/keycloak.v2/login/theme.properties")) {
            assertNotNull(input, "Pinned26.3.3 parent theme JAR required");
            properties.load(input);
        }
        var messages = new Properties();
        for (String type : List.of("login", "email")) {
            Path file = repository().resolve("themes/knora/" + type + "/messages/messages_en.properties");
            if (Files.exists(file)) try (var input = Files.newBufferedReader(file)) { messages.load(input); }
        }
        var data = new HashMap<String, Object>();
        data.put("properties", properties);
        data.put("msg", (TemplateMethodModelEx) args -> {
            String key = args.get(0).toString();
            Object[] values = new Object[args.size() - 1];
            for (int index = 1; index < args.size(); index++) values[index - 1] = args.get(index).toString();
            return new java.text.MessageFormat(messages.getProperty(key, key), java.util.Locale.ENGLISH).format(values);
        });
        data.put("kcSanitize", (TemplateMethodModelEx) args -> args.get(0).toString());
        data.put("realm", Map.of("internationalizationEnabled", false, "displayName", "Knora"));
        data.put("url", Map.of("loginAction", "/native/action", "loginUrl", "/native/login", "resourcesPath", "/resources",
                "resourcesCommonPath", "/common", "ssoLoginInOtherTabsUrl", "/session"));
        data.put("lang", "en");
        data.put("pageId", "offline-reset");
        data.put("darkMode", false);
        return data;
    }
    private static String render(String type, String name, Map<String, Object> data) throws Exception {
        Path directory = repository().resolve("themes/knora/" + type);
        assertTrue(Files.exists(directory.resolve(name)), "Owned template is not implemented: " + name);
        var config = new Configuration(Configuration.VERSION_2_3_32);
        config.setOutputFormat(HTMLOutputFormat.INSTANCE);
        config.setLogTemplateExceptions(false);
        config.setTemplateExceptionHandler(freemarker.template.TemplateExceptionHandler.RETHROW_HANDLER);
        config.setTemplateLoader(new MultiTemplateLoader(new freemarker.cache.TemplateLoader[] {
                new FileTemplateLoader(directory.toFile()),
                new ClassTemplateLoader(EmailOtpResetFlowIT.class, "/theme/keycloak.v2/" + type),
                new ClassTemplateLoader(EmailOtpResetFlowIT.class, "/theme/base/" + type)}));
        var output = new StringWriter();
        config.getTemplate(name, "UTF-8").process(data, output);
        return output.toString();
    }
    @Test
    void nativeEmailRendererCanEnrichSenderAttributesBeforeActivation() throws Exception {
        var f = new Fixture();
        f.nativeRendererMutations = true;
        f.post("request", "email", "known@example.test");
        assertEquals(List.of("reserve", "mail", "activate"), f.events);
        assertNull(f.attachedUser);
        assertFalse(f.succeeded);
    }

    /** Execute the pinned renderer through its first mutation, then stop before theme I/O. */
    static final class NativeAttributeProbe extends FreeMarkerEmailTemplateProvider {
        NativeAttributeProbe(KeycloakSession session) { super(session); }
        @Override
        protected Theme getTheme() throws java.io.IOException {
            throw new java.io.IOException("NATIVE_ATTRIBUTE_ENRICHMENT_REACHED");
        }
        void accept(Map<String, Object> attributes) {
            try {
                processTemplate("knoraResetOtpSubject", List.of(), "knora-reset-otp.ftl", attributes);
                throw new IllegalStateException("Unexpected theme I/O");
            } catch (EmailException failure) {
                Throwable cause = failure;
                while (cause.getCause() != null) cause = cause.getCause();
                if (!(cause instanceof java.io.IOException)
                        || !"NATIVE_ATTRIBUTE_ENRICHMENT_REACHED".equals(cause.getMessage()))
                    throw new IllegalStateException("Native attribute enrichment failed");
            }
        }
    }

    @Test
    void offlineRequestBindsNativeScopeAndTrustedIpAndClosesVault() throws Exception {
        var f = new Fixture();
        f.post("request", "email", " Known@Example.test ");
        assertEquals("knora-reset-otp.ftl", f.template);
        assertEquals(new OtpChallengeStore.ChallengeScope("realm-id", "client-id", "root-id", "tab-id",
                f.sent.scope().emailDigest()), f.sent.scope());
        assertNotEquals("spoofed-ip", f.sent.ipDigest());
        assertEquals(1, f.vaultClosed);
        assertTrue(f.vaultExpression.matches("\\$\\{vault\\.knora-email-otp-hmac-[a-f0-9]{64}}"));
        assertEquals(List.of("reserve", "mail", "activate"), f.events);
        assertFalse(f.notes.values().contains("000042"));
        assertNull(f.attachedUser);
        assertFalse(f.succeeded);
    }

    @Test
    void offlineMissingMalformedAndShortVaultNeverAuthorizeStoreOrSmtp() throws Exception {
        for (String value : new String[] {null, "malformed", Base64.getEncoder().encodeToString(new byte[31])}) {
            var f = new Fixture();
            f.vaultValue = value;
            f.post("request", "email", "known@example.test");
            assertTrue(f.events.isEmpty());
            assertEquals(1, f.vaultClosed);
            assertFalse(f.succeeded);
            assertNull(f.attachedUser);
        }
    }

    @Test
    void offlineOnlyConfirmedVerifiedUserSetsNativeCompletionFlag() throws Exception {
        var f = new Fixture();
        f.post("request", "email", "known@example.test");
        f.post("verify", "code", "000042");
        assertSame(f.user, f.attachedUser);
        assertTrue(f.succeeded);
        assertEquals("true", f.notes.get(AuthenticationManager.END_AFTER_REQUIRED_ACTIONS));
        assertFalse(f.notes.values().contains("000042"));
    }

    @Test
    void offlineFailedConsumeDisabledAndChangedEmailNeverCompleteNativeFlow() throws Exception {
        for (var outcome : OtpChallengeStore.VerifyOutcome.values()) {
            if (outcome == OtpChallengeStore.VerifyOutcome.VERIFIED) continue;
            var f = new Fixture();
            f.post("request", "email", "known@example.test");
            f.outcome = outcome;
            f.post("verify", "code", "000042");
            assertFalse(f.succeeded);
            assertNull(f.attachedUser);
            assertFalse(f.notes.containsKey(AuthenticationManager.END_AFTER_REQUIRED_ACTIONS));
            assertEquals("knora-reset-otp.ftl", f.template);
            assertEquals(true, f.attributes.get("otpInvalid"));
        }
        for (String mode : List.of("disabled", "changed")) {
            var f = new Fixture();
            f.post("request", "email", "known@example.test");
            if (mode.equals("disabled")) f.enabled = false;
            else f.email = "changed@example.test";
            f.post("verify", "code", "000042");
            assertFalse(f.succeeded);
            assertNull(f.attachedUser);
        }
    }

    @Test
    void offlineUnknownDisabledSmtpAndStoreFailuresRenderSamePublicChallenge() throws Exception {
        Map<String, Object> expected = null;
        for (String mode : List.of("success", "unknown", "disabled", "smtp", "store", "missing-key")) {
            var f = new Fixture();
            if (mode.equals("unknown")) f.known = false;
            if (mode.equals("disabled")) f.enabled = false;
            if (mode.equals("smtp")) f.mailFails = true;
            if (mode.equals("store")) f.sendOutcome = OtpChallengeStore.SendOutcome.UNAVAILABLE;
            if (mode.equals("missing-key")) f.vaultValue = null;
            f.post("request", "email", "known@example.test");
            assertEquals("knora-reset-otp.ftl", f.template);
            if (expected == null) expected = new HashMap<>(f.attributes);
            else assertEquals(expected, f.attributes);
            assertFalse(f.succeeded);
            assertNull(f.attachedUser);
            if (List.of("unknown", "disabled", "store", "missing-key").contains(mode)) assertFalse(f.events.contains("mail"));
        }
    }

    @Test
    void offlineLeadingZeroIsPassedUnchangedAndResendUsesServerGenerationAndCooldown() throws Exception {
        var f = new Fixture();
        f.post("request", "email", "known@example.test");
        var original = f.sent;
        f.sendOutcome = OtpChallengeStore.SendOutcome.COOLDOWN;
        f.post("resend", "generation", "999");
        assertEquals(original.reference(), f.sent.previous());
        assertEquals(2, f.sent.reference().generation());
        assertFalse(f.events.contains("mail"));
        f.post("verify", "code", "000042");
        assertEquals(original.codeDigest(), f.submittedDigest);
        assertTrue(f.succeeded);
    }

    @Test
    void offlineMalformedNotesAndDuplicateIntentCannotAuthorizeWork() throws Exception {
        var f = new Fixture();
        f.post("request", "email", "known@example.test");
        f.notes.put("knora.emailOtp.generation", "malformed");
        f.post("verify", "code", "000042");
        assertTrue(f.events.isEmpty());
        assertEquals("knora-reset-email.ftl", f.template);
        f.parameters.add("intent", "request");
        f.authenticator.action(f.context);
        assertTrue(f.events.isEmpty());
        assertFalse(f.succeeded);
    }

    static final class Fixture {
        final Map<String, String> notes = new HashMap<>();
        final Map<String, Object> attributes = new HashMap<>();
        final List<String> events = new ArrayList<>();
        final MultivaluedHashMap<String, String> parameters = new MultivaluedHashMap<>();
        String vaultValue = Base64.getEncoder().encodeToString(new byte[32]);
        String vaultExpression;
        int vaultClosed;
        String template;
        boolean enabled = true;
        boolean known = true;
        boolean mailFails;
        boolean nativeRendererMutations;
        String realmId = "realm-id";
        String remoteAddress = "192.0.2.5";
        String email = "known@example.test";
        boolean succeeded;
        UserModel attachedUser;
        OtpChallengeStore.SendRequest sent;
        String submittedDigest;
        OtpChallengeStore.SendOutcome sendOutcome = OtpChallengeStore.SendOutcome.SENT;
        OtpChallengeStore.VerifyOutcome outcome = OtpChallengeStore.VerifyOutcome.VERIFIED;
        final UserModel user = fake(UserModel.class, (method, args) -> switch (method) {
            case "getId" -> "user-id";
            case "getEmail" -> email;
            case "isEnabled" -> enabled;
            default -> unsupported(method);
        });
        final RealmModel realm = fake(RealmModel.class, (method, args) -> switch (method) {
            case "getId" -> realmId;
            case "getName" -> "realm-name";
            default -> unsupported(method);
        });
        final ClientModel client = fake(ClientModel.class, (method, args) -> switch (method) {
            case "getId", "getClientId" -> "client-id";
            default -> unsupported(method);
        });
        final RootAuthenticationSessionModel root = fake(RootAuthenticationSessionModel.class,
                (method, args) -> "getId".equals(method) ? "root-id" : unsupported(method));
        final AuthenticationSessionModel auth = fake(AuthenticationSessionModel.class, (method, args) -> switch (method) {
            case "getParentSession" -> root;
            case "getTabId" -> "tab-id";
            case "getClient" -> client;
            case "getAuthNote" -> notes.get((String) args[0]);
            case "setAuthNote" -> { notes.put((String) args[0], (String) args[1]); yield null; }
            case "removeAuthNote" -> { notes.remove((String) args[0]); yield null; }
            default -> unsupported(method);
        });
        final ClientConnection connection = fake(ClientConnection.class,
                (method, args) -> "getRemoteAddr".equals(method) ? remoteAddress : unsupported(method));
        final KeycloakContext keycloakContext = fake(KeycloakContext.class, (method, args) -> switch (method) {
            case "resolveLocale" -> java.util.Locale.ENGLISH;
            case "getRealm" -> realm;
            case "getConnection" -> connection;
            default -> unsupported(method);
        });
        final UserProvider users = fake(UserProvider.class, (method, args) -> switch (method) {
            case "getUserByEmail" -> known && email.equals(args[1]) ? user : null;
            case "getUserById" -> known && "user-id".equals(args[1]) ? user : null;
            default -> unsupported(method);
        });
        final VaultTranscriber vault = fake(VaultTranscriber.class, (method, args) -> {
            if (!"getStringSecret".equals(method)) return unsupported(method);
            vaultExpression = (String) args[0];
            return new VaultStringSecret() {
                public Optional<String> get() { return Optional.ofNullable(vaultValue); }
                public void close() { vaultClosed++; }
            };
        });
        final EmailTemplateProvider mail = fake(EmailTemplateProvider.class, (method, args) -> {
            if (method.equals("setRealm")) { assertSame(realm, args[0]); return this.mail; }
            if (method.equals("setUser")) { assertSame(user, args[0]); return this.mail; }
            if (method.equals("setAuthenticationSession")) { assertSame(auth, args[0]); return this.mail; }
            if ("send".equals(method)) {
                events.add("mail");
                assertEquals("knoraResetOtpSubject", args[0]);
                assertEquals("knora-reset-otp.ftl", args[1]);
                assertEquals("000042", ((Map<?, ?>) args[2]).get("code"));
                if (nativeRendererMutations) {
                    @SuppressWarnings("unchecked")
                    var body = (Map<String, Object>) args[2];
                    var renderer = new NativeAttributeProbe(this.session);
                    renderer.setRealm(realm).setUser(user).setAuthenticationSession(auth);
                    renderer.accept(body);
                }
                if (mailFails) throw new IllegalStateException("Offline mail unavailable");
                return null;
            }
            return unsupported(method);
        });
        final KeycloakSession session = fake(KeycloakSession.class, (method, args) -> switch (method) {
            case "getContext" -> keycloakContext;
            case "users" -> users;
            case "vault" -> vault;
            case "getProvider" -> args[0] == EmailTemplateProvider.class ? mail
                    : args[0] == FreeMarkerProvider.class ? null : unsupported(method);
            default -> unsupported(method);
        });
        final LoginFormsProvider form = fake(LoginFormsProvider.class, (method, args) -> switch (method) {
            case "setAttribute" -> { attributes.put((String) args[0], args[1]); yield this.form; }
            case "createForm" -> { template = (String) args[0]; yield null; }
            default -> unsupported(method);
        });
        final HttpRequest http = fake(HttpRequest.class,
                (method, args) -> "getDecodedFormParameters".equals(method) ? parameters : unsupported(method));
        final AuthenticationFlowContext context = fake(AuthenticationFlowContext.class, (method, args) -> switch (method) {
            case "getSession" -> session;
            case "getRealm" -> realm;
            case "getAuthenticationSession" -> auth;
            case "getConnection" -> connection;
            case "getHttpRequest" -> http;
            case "form" -> form;
            case "challenge", "clearUser" -> null;
            case "setUser" -> { attachedUser = (UserModel) args[0]; yield null; }
            case "success" -> { succeeded = true; yield null; }
            default -> unsupported(method);
        });
        final OtpChallengeStore store = new OtpChallengeStore() {
            public SendResult reserve(SendRequest request) {
                sent = request; events.add("reserve");
                return new SendResult(sendOutcome, sendOutcome == SendOutcome.SENT ? request.reference() : request.previous(),
                        sendOutcome == SendOutcome.COOLDOWN ? 30 : 0);
            }
            public ActivationOutcome activate(ChallengeScope scope, ChallengeReference ref, String op) {
                events.add("activate"); return ActivationOutcome.ACTIVE;
            }
            public ActivationOutcome reconcileActivation(ChallengeScope scope, ChallengeReference ref, String op) {
                events.add("reconcile"); return ActivationOutcome.INVALID;
            }
            public VerifyResult verify(ChallengeScope scope, ChallengeReference ref, String codeDigest) {
                submittedDigest = codeDigest;
                events.add("verify"); return new VerifyResult(outcome, outcome == VerifyOutcome.VERIFIED ? "user-id" : null);
            }
            public boolean deliveryFailed(ChallengeScope scope, ChallengeReference ref) { throw new AssertionError("No invalidation dependency"); }
        };
        final Authenticator authenticator;
        Fixture() throws Exception {
            Class<?> type;
            try { type = Class.forName("com.knora.keycloak.reset.EmailOtpResetAuthenticator"); }
            catch (ClassNotFoundException missing) { throw new AssertionError("Offline provider is not implemented"); }
            var constructor = type.getDeclaredConstructor(Function.class, OtpChallengeService.CodeGenerator.class, Clock.class);
            constructor.setAccessible(true);
            authenticator = (Authenticator) constructor.newInstance((Function<KeycloakSession, OtpChallengeStore>) ignored -> store,
                    (OtpChallengeService.CodeGenerator) () -> "000042", Clock.fixed(Instant.parse("2026-10-06T00:00:00Z"), ZoneOffset.UTC));
        }
        void post(String intent, String field, String value) {
            parameters.clear(); attributes.clear(); events.clear();
            parameters.add("intent", intent);
            parameters.add(field, value);
            parameters.add("ip", "spoofed-ip");
            authenticator.action(context);
        }
    }

    @FunctionalInterface interface Call { Object invoke(String method, Object[] args); }
    @SuppressWarnings("unchecked")
    static <T> T fake(Class<T> type, Call call) {
        return (T) Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[] {type}, (proxy, method, args) -> {
            if (method.getName().equals("toString")) return "offline-" + type.getSimpleName();
            return call.invoke(method.getName(), args == null ? new Object[0] : args);
        });
    }
    static Object unsupported(String method) { throw new AssertionError("Unexpected native call: " + method); }
}
