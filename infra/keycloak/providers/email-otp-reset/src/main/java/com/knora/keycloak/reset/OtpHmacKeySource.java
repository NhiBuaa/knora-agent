package com.knora.keycloak.reset;

import java.util.Arrays;
import java.util.Base64;
import java.util.Map;
import java.util.function.Supplier;

final class OtpHmacKeySource {
    static final String ENVIRONMENT_KEY = "KNORA_OTP_HMAC_KEY";
    static final String LOCAL_DEV_ENABLED = "KNORA_OTP_LOCAL_DEV_ENABLED";
    private static final int MINIMUM_BYTES = 32;
    private static final int MAXIMUM_BASE64_LENGTH = 4096;

    private OtpHmacKeySource() {}

    static boolean localDevelopmentEnabled(Map<String, String> environment) {
        String mode = environment.get(LOCAL_DEV_ENABLED);
        if (mode != null
                && !mode.isBlank()
                && !"true".equalsIgnoreCase(mode.strip())
                && !"false".equalsIgnoreCase(mode.strip())) {
            throw new IllegalStateException("OTP local development mode is malformed");
        }
        return "true".equalsIgnoreCase(mode == null ? "" : mode.strip());
    }

    static byte[] resolve(Map<String, String> environment, Supplier<String> vaultSecret) {
        boolean localDevelopment = localDevelopmentEnabled(environment);
        String encoded = localDevelopment ? environment.get(ENVIRONMENT_KEY) : vaultSecret.get();
        return decode(encoded, localDevelopment);
    }

    private static byte[] decode(String encoded, boolean localDevelopment) {
        if (encoded == null || encoded.isBlank() || encoded.length() > MAXIMUM_BASE64_LENGTH) {
            throw new IllegalStateException("OTP HMAC key is missing or malformed");
        }
        if (!localDevelopment) encoded = encoded.strip();
        try {
            byte[] decoded = Base64.getDecoder().decode(encoded);
            if ((localDevelopment && !Base64.getEncoder().encodeToString(decoded).equals(encoded))
                    || decoded.length < MINIMUM_BYTES) {
                Arrays.fill(decoded, (byte) 0);
                throw new IllegalStateException("OTP HMAC key is missing or malformed");
            }
            return decoded;
        } catch (IllegalArgumentException malformed) {
            throw new IllegalStateException("OTP HMAC key is missing or malformed");
        }
    }
}
