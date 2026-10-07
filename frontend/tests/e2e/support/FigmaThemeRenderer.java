import freemarker.cache.*;
import freemarker.core.HTMLOutputFormat;
import freemarker.template.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.jar.*;

/** Offline source renderer. No realm, users, sessions, secrets or password verification. */
public class FigmaThemeRenderer {
    static Path repository;
    static Properties messages = new Properties();
    static Properties properties = new Properties();
    static TemplateMethodModelEx text = args -> args.get(0).toString();
    static TemplateMethodModelEx falseMethod = args -> false;
    static Map<String, Object> data(boolean error) {
        var data = new HashMap<String, Object>();
        TemplateMethodModelEx msg = args -> {
            String key = args.get(0).toString();
            Object[] values = args.stream().skip(1).map(Object::toString).toArray();
            return new java.text.MessageFormat(messages.getProperty(key, key), Locale.ENGLISH).format(values);
        };
        data.put("properties", properties);
        data.put("msg", msg); data.put("advancedMsg", msg); data.put("kcSanitize", text);
        data.put("realm", Map.of("internationalizationEnabled", false, "displayName", "Knora", "displayNameHtml", "Knora", "password", true, "loginWithEmailAllowed", true, "registrationEmailAsUsername", false, "resetPasswordAllowed", true, "registrationAllowed", true, "rememberMe", false));
        data.put("url", Map.of("loginAction", "/native/blocked-action", "registrationAction", "/native/blocked-action", "loginUrl", "/native/228-212.html", "registrationUrl", "/native/237-251.html", "loginResetCredentialsUrl", "/native/242-272.html", "resourcesPath", "/resources", "resourcesCommonPath", "/common", "ssoLoginInOtherTabsUrl", "/session"));
        TemplateMethodModelEx errorText = args -> error ? "Please check this field." : "";
        data.put("messagesPerField", Map.of("get", errorText, "getFirstError", errorText, "existsError", (TemplateMethodModelEx) args -> error, "exists", falseMethod));
        data.put("auth", Map.of("showUsername", falseMethod, "showResetCredentials", falseMethod, "showTryAnotherWayLink", falseMethod));
        data.put("lang", "en"); data.put("pageId", "fixture"); data.put("darkMode", true);
        data.put("login", Map.of("username", "")); data.put("social", Map.of("providers", List.of()));
        data.put("passwordRequired", true); data.put("passwordPolicies", Map.of("length", 12));
        var attributes = new ArrayList<Map<String, Object>>();
        for (String name : List.of("username", "email")) attributes.add(Map.of("name", name, "displayName", name, "required", true, "readOnly", false, "multivalued", false, "annotations", Map.of(), "html5DataAnnotations", Map.of(), "validators", Map.of(), "value", ""));
        data.put("profile", Map.of("attributes", attributes, "html5DataAnnotations", Map.of()));
        data.put("maskedEmail", "n***@example.test"); data.put("retryAfterSeconds", 30);
        data.put("otpInvalid", error); data.put("emailInvalid", false);
        if (error) data.put("message", Map.of("type", "error", "summary", "Please check your details and try again."));
        return data;
    }
    public static void main(String[] args) throws Exception {
        repository = Path.of(args[0]); Path output = Path.of(args[1]); Files.createDirectories(output);
        Path jarPath = Path.of(args[2]);
        try (var jar = new JarFile(jarPath.toFile())) {
            // This exact inherited module is referenced by the pinned login parent.
            // Keep base resources explicit to avoid changing resource precedence.
            var visibilityEntry = jar.getJarEntry("theme/base/login/resources/js/passwordVisibility.js");
            if (visibilityEntry == null) throw new IllegalStateException("Pinned password visibility module missing");
            byte[] visibility;
            try (var input = jar.getInputStream(visibilityEntry)) { visibility = input.readAllBytes(); }
            String visibilityHash = HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(visibility));
            if (visibility.length != 698 || !visibilityHash.equals("6df35fb0b98bfc3b78bb9936fceca7d91bb53dcc0cd3df7399b4fa3537c565ed"))
                throw new IllegalStateException("Pinned password visibility module changed");
            Path visibilityTarget = output.resolve("resources/js/passwordVisibility.js");
            Files.createDirectories(visibilityTarget.getParent());
            Files.write(visibilityTarget, visibility);
            for (String resource : List.of("theme/base/login/messages/messages_en.properties", "theme/keycloak/login/messages/messages_en.properties", "theme/keycloak.v2/login/theme.properties")) {
                var entry = jar.getJarEntry(resource);
                if (entry != null) try (var reader = new InputStreamReader(jar.getInputStream(entry), java.nio.charset.StandardCharsets.UTF_8)) { (resource.endsWith("theme.properties") ? properties : messages).load(reader); }
            }
            for (var entry : Collections.list(jar.entries())) {
                if (entry.isDirectory()) continue;
                for (String prefix : List.of("theme/keycloak/login/resources/", "theme/keycloak.v2/login/resources/", "theme/common/keycloak/resources/", "theme/keycloak/common/resources/")) {
                    if (!entry.getName().startsWith(prefix)) continue;
                    Path target = output.resolve(prefix.contains("/common/") ? "common" : "resources").resolve(entry.getName().substring(prefix.length()));
                    Files.createDirectories(target.getParent()); Files.copy(jar.getInputStream(entry), target, StandardCopyOption.REPLACE_EXISTING);
                }
            }
        }
        try (var reader = Files.newBufferedReader(repository.resolve("themes/knora/login/messages/messages_en.properties"))) { messages.load(reader); }
        try (var reader = Files.newBufferedReader(repository.resolve("themes/knora/login/theme.properties"))) { properties.load(reader); }
        try (var files = Files.walk(repository.resolve("themes/knora/login/resources"))) {
            for (Path source : files.filter(Files::isRegularFile).toList()) {
                Path target = output.resolve("resources").resolve(repository.resolve("themes/knora/login/resources").relativize(source));
                Files.createDirectories(target.getParent()); Files.copy(source, target, StandardCopyOption.REPLACE_EXISTING);
            }
        }
        var config = new Configuration(Configuration.VERSION_2_3_32);
        config.setOutputFormat(HTMLOutputFormat.INSTANCE); config.setLogTemplateExceptions(false);
        config.setTemplateExceptionHandler(TemplateExceptionHandler.RETHROW_HANDLER);
        config.setTemplateLoader(new MultiTemplateLoader(new TemplateLoader[]{new FileTemplateLoader(repository.resolve("themes/knora/login").toFile()), new ClassTemplateLoader(FigmaThemeRenderer.class, "/theme/keycloak.v2/login"), new ClassTemplateLoader(FigmaThemeRenderer.class, "/theme/base/login")}));
        for (String[] state : new String[][]{{"228-212", "login.ftl"}, {"228-251", "login.ftl"}, {"237-251", "register.ftl"}, {"237-313", "register.ftl"}, {"242-272", "knora-reset-email.ftl"}, {"242-333", "knora-reset-otp.ftl"}, {"242-389", "login-update-password.ftl"}, {"246-311", "knora-reset-otp.ftl"}, {"246-404", "info.ftl"}}) {
            var data = data(Set.of("228-251", "237-313", "246-311").contains(state[0]));
            if (state[0].equals("242-389")) data.put("pageId", "login-update-password");
            if (state[0].equals("246-404")) { data.put("client", Map.of("baseUrl", "http://127.0.0.1:3300")); data.put("message", Map.of("type", "success", "summary", messages.getProperty("accountUpdatedMessage", "accountUpdatedMessage"))); }
            try (var writer = Files.newBufferedWriter(output.resolve(state[0] + ".html"))) { config.getTemplate(state[1], "UTF-8").process(data, writer); }
            System.out.println(state[0] + " rendered from " + state[1]);
        }
    }
}
