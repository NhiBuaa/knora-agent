<#import "template.ftl" as layout>
<#import "field.ftl" as field>
<#import "user-profile-commons.ftl" as userProfileCommons>
<#import "register-commons.ftl" as registerCommons>
<#import "password-validation.ftl" as validator>
<@layout.registrationLayout displayMessage=false; section>
<!-- template: register.ftl -->

    <#if section = "header">
        <#if messageHeader??>
            ${kcSanitize(msg("${messageHeader}"))?no_esc}
        <#else>
            ${msg("registerTitle")}
        </#if>
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
        <p class="knora-auth-description"><#if message?has_content && message.type == 'error'>${msg("knoraRegisterErrorDescription")}<#else>${msg("knoraRegisterDescription")}</#if></p>

        <#if message?has_content && message.type == 'error'>
            <div class="knora-notice" role="alert">
                <strong>${msg("knoraRegisterError")}</strong>
                <p>${kcSanitize(message.summary)?no_esc}</p>
            </div>
        </#if>

        <form id="kc-register-form" class="${properties.kcFormClass!}" action="${url.registrationAction}" method="post" novalidate="novalidate">
            <#-- Render real native profile attributes; do not synthesize omitted names. -->
            <#list ['username', 'email'] as fieldName>
                <#list profile.attributes as attribute>
                    <#if attribute.name == fieldName>
                        <@field.group name=attribute.name label=advancedMsg(attribute.displayName!'') error=kcSanitize(messagesPerField.get(attribute.name))?no_esc required=false>
                            <@userProfileCommons.inputFieldByType attribute=attribute />
                        </@field.group>
                    </#if>
                </#list>
            </#list>
            <#list profile.attributes as attribute>
                <#if attribute.name == 'locale' && realm.internationalizationEnabled && locale.currentLanguageTag?has_content>
                    <input type="hidden" name="locale" value="${locale.currentLanguageTag}" />
                <#elseif attribute.required && !['username', 'email', 'firstName', 'lastName', 'locale']?seq_contains(attribute.name)>
                    <#-- Configuration preflight rejects this conflict. Keep the native field if configuration drifts. -->
                    <@field.group name=attribute.name label=advancedMsg(attribute.displayName!'') error=kcSanitize(messagesPerField.get(attribute.name))?no_esc required=true>
                        <@userProfileCommons.inputFieldByType attribute=attribute />
                    </@field.group>
                </#if>
            </#list>
            <#if passwordRequired??>
                <@field.password name="password" label=msg("password") autocomplete="new-password" />
                <@field.password name="password-confirm" label=msg("passwordConfirm") autocomplete="new-password" />
            </#if>
            <#list profile.html5DataAnnotations?keys as key>
                <script type="module" src="${url.resourcesPath}/js/${key}.js"></script>
            </#list>

            <@registerCommons.termsAcceptance/>

            <#if recaptchaRequired?? && (recaptchaVisible!false)>
                <div class="form-group">
                    <div class="${properties.kcInputWrapperClass!}">
                        <div class="g-recaptcha" data-size="compact" data-sitekey="${recaptchaSiteKey}" data-action="${recaptchaAction}"></div>
                    </div>
                </div>
            </#if>

            <#if recaptchaRequired?? && !(recaptchaVisible!false)>
                <script>
                    function onSubmitRecaptcha(token) {
                        document.getElementById("kc-register-form").requestSubmit();
                    }
                </script>
                <div id="kc-form-buttons" class="${properties.kcFormButtonsClass!}">
                    <button class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonBlockClass!} ${properties.kcButtonLargeClass!} g-recaptcha"
                            data-sitekey="${recaptchaSiteKey}" data-callback="onSubmitRecaptcha" data-action="${recaptchaAction}" type="submit" id="kc-submit">
                        ${msg("doRegister")}
                    </button>
                </div>
            <#else>
                <div id="kc-form-buttons" class="${properties.kcFormButtonsClass!}">
                    <button id="kc-submit" class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonBlockClass!} ${properties.kcButtonLargeClass!}" type="submit">${msg("doRegister")}</button>
                </div>
            </#if>

            <p class="knora-secondary">${msg("knoraExistingAccount")} <a href="${url.loginUrl}">${msg("doLogIn")}</a></p>
            <p class="knora-disclaimer">${msg("knoraRegisterDisclaimer")}</p>

        </form>
        <script>
            const registrationPlaceholders = {
                "username": "${msg('knoraRegisterUsernamePlaceholder')?js_string}",
                "email": "${msg('knoraEmailPlaceholder')?js_string}",
                "password": "${msg('knoraPasswordPlaceholder')?js_string}",
                "password-confirm": "${msg('knoraPasswordPlaceholder')?js_string}"
            };
            for (const [id, placeholder] of Object.entries(registrationPlaceholders)) {
                const input = document.getElementById(id);
                if (input && !input.placeholder) input.placeholder = placeholder;
            }
        </script>
        </div>
        <#if passwordRequired??>
            <@validator.templates/>
            <@validator.script field="password"/>
        </#if>
    </#if>
</@layout.registrationLayout>
