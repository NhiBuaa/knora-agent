<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        <#if messageHeader??>
            ${kcSanitize(msg("${messageHeader}"))?no_esc}
        <#else>
        ${kcSanitize(message.summary)?no_esc}
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

    <div id="kc-info-message">
        <p class="instruction">${kcSanitize(message.summary)?no_esc}<#if requiredActions??><#list requiredActions>: <b><#items as reqActionItem>${kcSanitize(msg("requiredAction.${reqActionItem}"))?no_esc}<#sep>, </#items></b></#list><#else></#if></p>
        <#if skipLink??>
        <#else>
            <#if message?? && message.type == "success" && message.summary == msg("accountUpdatedMessage") && !isAppInitiatedAction??>
                <#-- Completion starts a new BFF transaction at the configured application origin.
                     Never carry native action/callback parameters into the new sign-in. -->
                <#assign appBase = (client.baseUrl)!"">
                <#assign realmName = (realm.name)!"">
                <#assign clientId = (client.clientId)!"">
                <#assign resetMarkerKey = "knora:reset-success:" + realmName + ":" + clientId>
                <#assign ipv6 = "([A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}"
                    + "|([A-Fa-f0-9]{1,4}:){1,7}:"
                    + "|([A-Fa-f0-9]{1,4}:){1,6}:[A-Fa-f0-9]{1,4}"
                    + "|([A-Fa-f0-9]{1,4}:){1,5}(:[A-Fa-f0-9]{1,4}){1,2}"
                    + "|([A-Fa-f0-9]{1,4}:){1,4}(:[A-Fa-f0-9]{1,4}){1,3}"
                    + "|([A-Fa-f0-9]{1,4}:){1,3}(:[A-Fa-f0-9]{1,4}){1,4}"
                    + "|([A-Fa-f0-9]{1,4}:){1,2}(:[A-Fa-f0-9]{1,4}){1,5}"
                    + "|[A-Fa-f0-9]{1,4}:((:[A-Fa-f0-9]{1,4}){1,6})"
                    + "|:((:[A-Fa-f0-9]{1,4}){1,7}|:)">
                <#if appBase?matches("^https?://([A-Za-z0-9.-]+|\\[(" + ipv6 + ")\\])(:[0-9]{1,5})?([/?#].*)?$")>
                    <#assign appOrigin = appBase?replace("^(https?://[^/?#]+).*$", "$1", "r")>
                    <#assign appAuthority = appOrigin?keep_after("://")>
                    <#-- IPv6 hextets are host data; its optional port begins after the closing bracket. -->
                    <#assign appPort = appAuthority?starts_with("[")?then(
                        appAuthority?keep_after("]")?remove_beginning(":"), appAuthority?keep_after(":"))>
                    <#if !appPort?has_content || appPort?number lte 65535>
                        <p><a class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonBlockClass!}" <#if knoraPasswordUpdated!false>data-knora-reset-success-link data-knora-reset-success-key="${resetMarkerKey}"</#if> href="${appOrigin}/api/auth/login?prompt=login">${kcSanitize(msg("doLogIn"))?no_esc}</a></p>
                        <#if knoraPasswordUpdated!false>
                            <script src="${url.resourcesPath}/js/knora-login-transition.js" defer></script>
                        </#if>
                    </#if>
                </#if>
            <#elseif pageRedirectUri?has_content>
                <p><a href="${pageRedirectUri}">${kcSanitize(msg("backToApplication"))?no_esc}</a></p>
            <#elseif actionUri?has_content>
                <p><a href="${actionUri}">${kcSanitize(msg("proceedWithAction"))?no_esc}</a></p>
            <#elseif (client.baseUrl)?has_content>
                <p><a href="${client.baseUrl}">${kcSanitize(msg("backToApplication"))?no_esc}</a></p>
            </#if>
        </#if>
    </div>
    </div>
    </#if>
</@layout.registrationLayout>
