<#import "template.ftl" as layout>
<#import "field.ftl" as field>
<#import "buttons.ftl" as buttons>
<#import "social-providers.ftl" as identityProviders>
<#import "passkeys.ftl" as passkeys>
<@layout.registrationLayout displayMessage=false; section>
<!-- template: login.ftl -->

    <#if section = "header">
        ${msg("loginAccountTitle")}
    <#elseif section = "form">
        <aside class="knora-brand-panel" aria-label="Knora">
            <div class="knora-brand"><img src="${url.resourcesPath}/images/ad252.svg" width="18" height="18" alt="" /><span>Knora</span></div>
            <div class="knora-brand-copy">
                <p class="knora-eyebrow">${msg("knoraEvidenceFirst")}</p>
                <h2><span>${msg("knoraGroundedAnswers")}</span><span>${msg("knoraVerifiedEvidence")}</span></h2>
                <p class="knora-brand-description">${msg("knoraEvidenceDescription")}</p>
                <div class="knora-evidence-cues"><span>${msg("knoraSources")}</span><span>${msg("knoraPageRanges")}</span><span>${msg("knoraProvenance")}</span></div>
            </div>
            <p class="knora-brand-footnote">${msg("knoraSecureReturn")}</p>
        </aside>
<div class="knora-auth">
        <#assign resetMarkerKey = "knora:reset-success:" + ((realm.name)!"") + ":" + ((client.clientId)!"")>
        <div id="knora-password-updated-notice" class="knora-notice knora-notice-success" data-knora-reset-success-key="${resetMarkerKey}" hidden>
            <strong>${msg("knoraPasswordUpdated")}</strong>
            <p>${msg("knoraPasswordUpdatedDescription")}</p>
        </div>
        <p class="knora-auth-description">${msg("knoraLoginDescription")}</p>

        <#if message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
            <div class="knora-notice" role="alert">
                <#if message.type == 'error'><strong>${msg("knoraLoginError")}</strong></#if>
                <p>${kcSanitize(message.summary)?no_esc}</p>
            </div>
        </#if>

        <div id="kc-form">
          <div id="kc-form-wrapper">
            <#if realm.password>
                <form id="kc-form-login" class="${properties.kcFormClass!}" onsubmit="login.disabled = true; return true;" action="${url.loginAction}" method="post" novalidate="novalidate">
                    <#if !usernameHidden??>
                        <#assign label>
                            <#if !realm.loginWithEmailAllowed>${msg("username")}<#elseif !realm.registrationEmailAsUsername>${msg("usernameOrEmail")}<#else>${msg("email")}</#if>
                        </#assign>
                        <@field.input name="username" label=label error=kcSanitize(messagesPerField.getFirstError('username','password'))?no_esc
                            autofocus=true autocomplete="${(enableWebAuthnConditionalUI?has_content)?then('username webauthn', 'username')}" value=login.username!'' />
                        <@field.password name="password" label=msg("password") error="" forgotPassword=realm.resetPasswordAllowed autofocus=usernameHidden?? autocomplete="current-password">
                            <#if realm.rememberMe && !usernameHidden??>
                                <@field.checkbox name="rememberMe" label=msg("rememberMe") value=login.rememberMe?? />
                            </#if>
                        </@field.password>
                    <#else>
                        <@field.password name="password" label=msg("password") forgotPassword=realm.resetPasswordAllowed autofocus=usernameHidden?? autocomplete="current-password">
                            <#if realm.rememberMe && !usernameHidden??>
                                <@field.checkbox name="rememberMe" label=msg("rememberMe") value=login.rememberMe?? />
                            </#if>
                        </@field.password>
                    </#if>

                    <input type="hidden" id="id-hidden-input" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>/>
                    <@buttons.loginButton />
                    <p class="knora-disclaimer">${msg("knoraLoginDisclaimer")}</p>
                    <#if realm.registrationAllowed && !registrationDisabled??>
                        <p class="knora-secondary">${msg("noAccount")} <a href="${url.registrationUrl}">${msg("doRegister")}</a></p>
                    </#if>
                </form>
            </#if>
            </div>
        </div>
        <@passkeys.conditionalUIData />
        <script>
            const usernameInput = document.getElementById("username");
            if (usernameInput && !usernameInput.placeholder) {
                usernameInput.placeholder = "${msg('knoraLoginUsernamePlaceholder')?js_string}";
            }
            const passwordInput = document.getElementById("password");
            if (passwordInput && !passwordInput.placeholder) {
                passwordInput.placeholder = "${msg('knoraPasswordPlaceholder')?js_string}";
            }
        </script>
        <script src="${url.resourcesPath}/js/knora-login-transition.js" defer></script>
        </div>
    <#elseif section = "socialProviders" >
        <#if realm.password && social.providers?? && social.providers?has_content>
            <@identityProviders.show social=social/>
        </#if>
    <#elseif section = "info" >
        <#if realm.password && realm.registrationAllowed && !registrationDisabled??>
            <div id="kc-registration-container">
                <div id="kc-registration">
                    <span>${msg("noAccount")} <a href="${url.registrationUrl}">${msg("doRegister")}</a></span>
                </div>
            </div>
        </#if>
    </#if>

</@layout.registrationLayout>
