"""Build Keycloak's landing shell from the application's shared presentation."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sandhata.presentation import hero_markup,capabilities_markup

TARGET=ROOT/'deploy/keycloak/themes/sandhata/login'
CSS=ROOT/'src/sandhata/assets/theme.css'
shell='''<#macro registrationLayout displayMessage=true displayInfo=false>
<!DOCTYPE html><html lang="${(locale.currentLanguageTag)!'en'}"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SANDHĀTĀ · Career Intelligence</title>
<link rel="stylesheet" href="${url.resourcesPath}/css/landing.css">
<script src="${url.resourcesPath}/js/theme.js" defer></script>
</head><body class="sn-idp-page"><div class="sn-mode-bar"><button type="button" id="sn-mode" aria-pressed="false">Dark mode</button></div><main class="sn-idp-landing st-key-sn_landing">
<div class="sn-idp-top"><div>__HERO__</div><section class="sn-idp-account" aria-label="Sign in">
<div class="sn-account-eyebrow">YOUR NEXT CHAPTER</div><h2>Sign in</h2>
<p class="sn-idp-welcome">Your opportunities. Your progress. One workspace.</p>
<#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
<div class="sn-idp-message" role="alert">${kcSanitize(message.summary)?no_esc}</div></#if>
<#if auth?has_content && auth.showUsername() && !auth.showResetCredentials()>
<div class="sn-idp-account-choice"><strong>${auth.attemptedUsername}</strong> <a id="reset-login" href="${url.loginRestartFlowUrl}">Use a different account</a></div>
</#if>
<#nested "form"><#nested "socialProviders">
<#if displayInfo><#nested "info"></#if>
<p class="sn-account-note">Use your own account. New users need an administrator invitation.</p>
</section></div>__CAPABILITIES__</main></body></html></#macro>'''
(TARGET/'sandhata-layout.ftl').write_text(shell.replace('__HERO__',hero_markup()).replace('__CAPABILITIES__',capabilities_markup()),encoding='utf-8')
extra='''
*{box-sizing:border-box}body.sn-idp-page{margin:0;background:#FFFFFF;color:#123263;font:14px/1.5 Arial,sans-serif}
.sn-idp-landing{max-width:1440px;margin:0 auto;padding:42px 48px 24px}
.sn-idp-top{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(320px,1fr);gap:64px;align-items:start}
.sn-idp-account{margin-top:12px;background:white;border:1px solid #F4C430;border-top:4px solid #F4C430;border-radius:12px;padding:24px 26px;box-shadow:0 8px 28px #164B990A}
.sn-idp-account h2{font-size:24px;letter-spacing:-.02em;text-transform:none;margin:0 0 8px}
.sn-idp-welcome{margin:0 0 22px;color:#506581;font-size:13px}
.sn-idp-account label{display:block;font-size:13px;font-weight:700;margin:14px 0 7px}
.sn-idp-account input[type=text],.sn-idp-account input[type=password]{display:block;width:100%;height:42px;border:1px solid #B6C7DF;border-radius:6px;padding:9px 11px;background:white;color:#123263;font:inherit}
.sn-idp-account .sn-idp-account-choice{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:13px;margin-bottom:12px}.sn-idp-account [dir=ltr]:has(> input[type=password]){display:flex;gap:6px}.sn-idp-account .input-group{display:flex}.sn-idp-account .input-group input{flex:1;min-width:0}
.sn-idp-account button[data-password-toggle]{border:1px solid #B6C7DF;background:white;border-radius:6px;padding:0 10px;color:#164B99;font-size:11px}
.sn-idp-account button[data-password-toggle]::after{content:'Show / hide'}
.sn-idp-account #kc-login{width:100%;min-height:42px;background:#164B99;color:white;border:2px solid #F4C430;border-radius:8px;font-weight:700;font-size:14px;cursor:pointer;margin-top:22px}
.sn-idp-account #kc-login:hover{background:#F4C430;color:#123263}
.sn-idp-account input:focus,.sn-idp-account button:focus-visible,.sn-idp-account a:focus-visible{outline:3px solid #F4C430;outline-offset:2px}
.sn-idp-account .sn-account-note{font-size:12px;margin:22px 0 0;padding-top:15px}
.sn-idp-account .sn-idp-message,.sn-idp-account #input-error{display:block;background:#FFF8DD;color:#123263;border:1px solid #F4C430;border-radius:6px;padding:10px;margin-top:10px;font-size:13px}
.sn-idp-account a{color:#164B99}.sn-idp-account #kc-form-options{margin-top:10px}
.sn-idp-landing .sn-features{margin-top:32px}.sn-idp-landing .sn-feature{padding:8px 0}
.sn-idp-landing .sn-capabilities{margin-top:40px;padding-top:23px}
.sn-idp-landing .sn-capability{padding:16px;min-height:118px}
.sn-idp-landing .sn-capability h3{font-size:15px}.sn-idp-landing .sn-capability p{font-size:12px;line-height:1.5}
@media(max-width:1000px){.sn-idp-top{gap:28px;grid-template-columns:minmax(0,1.4fr) minmax(300px,1fr)}.sn-idp-landing{padding:30px}.sn-idp-landing .sn-features{margin-top:26px}}
@media(max-width:850px){.sn-idp-top{grid-template-columns:1fr;gap:28px}.sn-idp-account{margin:0}.sn-idp-landing .sn-capabilities{margin-top:32px}}
@media(max-width:520px){.sn-idp-landing{padding:24px 18px}.sn-idp-account{padding:20px}.sn-idp-landing .sn-capability{min-height:0}}
'''
extra=extra.replace('background:#FFFFFF','background:var(--sn-white)').replace('background:white','background:var(--sn-white)').replace('color:#123263','color:var(--sn-ink)').replace('color:#506581','color:var(--sn-muted)').replace('color:#164B99','color:var(--sn-blue)').replace('solid #B6C7DF','solid var(--sn-border)').replace('solid #F4C430','solid var(--sn-border)')
extra+='\n.sn-idp-account .sn-idp-message,.sn-idp-account #input-error{background:var(--sn-gold-tint);color:var(--sn-ink)}.sn-mode-bar button:hover{background:var(--sn-sandal);color:#123263!important}.sn-mode-bar{max-width:1440px;margin:0 auto;padding:12px 48px 0;text-align:right}.sn-mode-bar button{background:var(--sn-white);color:var(--sn-ink);border:2px solid var(--sn-border);border-radius:7px;padding:7px 12px;font-weight:700;cursor:pointer}.sn-mode-bar button:focus-visible{outline:3px solid var(--sn-sandal)}.sn-idp-landing{padding-top:14px}.sn-idp-page label,.sn-idp-page input,.sn-idp-page p{font-weight:650}.sn-idp-account #kc-login{color:white}.sn-idp-account #kc-login:hover{color:#123263}\n'
(TARGET/'resources/css/landing.css').write_text(CSS.read_text(encoding='utf-8')+extra,encoding='utf-8')
jsdir=TARGET/'resources/js';jsdir.mkdir(exist_ok=True)
(jsdir/'theme.js').write_text("""(()=>{const root=document.documentElement;const button=document.getElementById('sn-mode');const saved=document.cookie.split('; ').find(v=>v.startsWith('SANDHATA_THEME='));let dark=saved?.split('=')[1]==='dark';function apply(){root.dataset.theme=dark?'dark':'light';if(button){button.setAttribute('aria-pressed',String(dark));button.textContent=dark?'Light mode':'Dark mode';}document.cookie='SANDHATA_THEME='+(dark?'dark':'light')+'; Path=/; Max-Age=31536000; SameSite=Lax';}apply();button?.addEventListener('click',()=>{dark=!dark;apply();});})();""",encoding='utf-8')
print('Built SANDHATA landing shell; Keycloak owns the real login form and authentication flow.')
