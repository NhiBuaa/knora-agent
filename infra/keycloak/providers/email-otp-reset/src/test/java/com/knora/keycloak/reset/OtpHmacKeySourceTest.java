package com.knora.keycloak.reset;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

import java.util.Base64;
import java.util.HashMap;
import java.util.Map;

class OtpHmacKeySourceTest {
    @Test
    void localDevelopmentUsesValidatedEnvironmentKey() {
        byte[] expected = bytes(32);
        var environment = new HashMap<String, String>();
        environment.put(OtpHmacKeySource.LOCAL_DEV_ENABLED, "true");
        environment.put(
                OtpHmacKeySource.ENVIRONMENT_KEY, Base64.getEncoder().encodeToString(expected));

        assertArrayEquals(expected, OtpHmacKeySource.resolve(environment, () -> "vault-value"));
        assertArrayEquals(
                expected, OtpHmacKeySource.resolve(environment, () -> "different-vault-value"));
    }

    @Test
    void productionIgnoresEnvironmentAndUsesVault() {
        byte[] expected = bytes(32);
        var environment = Map.of(OtpHmacKeySource.ENVIRONMENT_KEY, "not-used");

        assertArrayEquals(
                expected,
                OtpHmacKeySource.resolve(
                        environment, () -> Base64.getEncoder().encodeToString(expected)));
    }

    @Test
    void productionPreservesLegacyVaultBase64Decoding() {
        byte[] expected = bytes(32);
        String unpadded = Base64.getEncoder().withoutPadding().encodeToString(expected);
        assertArrayEquals(
                expected, OtpHmacKeySource.resolve(Map.of(), () -> " \n" + unpadded + "\n"));
        assertThrows(
                IllegalStateException.class,
                () -> OtpHmacKeySource.resolve(Map.of(), () -> " ".repeat(4097) + unpadded));
    }

    @Test
    void localDevelopmentRejectsMissingMalformedAndShortKeysWithoutFallback() {
        for (String value :
                new String[] {null, "not-base64", Base64.getEncoder().encodeToString(bytes(31))}) {
            var environment = new HashMap<String, String>();
            environment.put(OtpHmacKeySource.LOCAL_DEV_ENABLED, "true");
            if (value != null) environment.put(OtpHmacKeySource.ENVIRONMENT_KEY, value);

            assertThrows(
                    IllegalStateException.class,
                    () ->
                            OtpHmacKeySource.resolve(
                                    environment,
                                    () -> Base64.getEncoder().encodeToString(bytes(32))));
        }
    }

    @Test
    void malformedModeFailsClosed() {
        var environment = Map.of(OtpHmacKeySource.LOCAL_DEV_ENABLED, "yes");

        assertThrows(
                IllegalStateException.class,
                () ->
                        OtpHmacKeySource.resolve(
                                environment, () -> Base64.getEncoder().encodeToString(bytes(32))));
    }

    @Test
    void localKeyRejectsNonCanonicalBase64AndNeverIncludesInputInErrors() {
        String valid = Base64.getEncoder().encodeToString(bytes(32));
        for (String value :
                new String[] {
                    "",
                    " " + valid,
                    valid + "\n",
                    valid.replace("=", ""),
                    valid + "=",
                    "A".repeat(4097),
                    "c2VjcmV0--invalid"
                }) {
            var environment =
                    Map.of(
                            OtpHmacKeySource.LOCAL_DEV_ENABLED,
                            "true",
                            OtpHmacKeySource.ENVIRONMENT_KEY,
                            value);
            var failure =
                    assertThrows(
                            IllegalStateException.class,
                            () ->
                                    OtpHmacKeySource.resolve(
                                            environment,
                                            () -> {
                                                throw new AssertionError(
                                                        "Unexpected Vault fallback");
                                            }));
            assertTrue("OTP HMAC key is missing or malformed".equals(failure.getMessage()));
            assertTrue(failure.getCause() == null);
        }
    }

    @Test
    void productionRequiresVaultEvenWithValidLocalKey() {
        for (String mode : new String[] {"false", ""}) {
            var environment =
                    Map.of(
                            OtpHmacKeySource.LOCAL_DEV_ENABLED,
                            mode,
                            OtpHmacKeySource.ENVIRONMENT_KEY,
                            Base64.getEncoder().encodeToString(bytes(32)));
            assertThrows(
                    IllegalStateException.class,
                    () -> OtpHmacKeySource.resolve(environment, () -> null));
        }
    }

    @Test
    void localKeyAcceptsLongerSecretsWithoutReadingVault() {
        byte[] expected = bytes(64);
        var environment =
                Map.of(
                        OtpHmacKeySource.LOCAL_DEV_ENABLED,
                        "true",
                        OtpHmacKeySource.ENVIRONMENT_KEY,
                        Base64.getEncoder().encodeToString(expected));
        assertArrayEquals(
                expected,
                OtpHmacKeySource.resolve(
                        environment,
                        () -> {
                            throw new AssertionError("Unexpected Vault access");
                        }));
    }

    private static byte[] bytes(int length) {
        byte[] value = new byte[length];
        for (int i = 0; i < value.length; i++) value[i] = (byte) i;
        return value;
    }
}
