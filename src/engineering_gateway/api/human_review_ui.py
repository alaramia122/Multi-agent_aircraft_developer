"""Small browser client for interactive OIDC PKCE and human review."""

HTML = """<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Engineering Gateway — проверка рабочей области</title>
<h1>Проверка рабочей области</h1>
<p>Войдите через IdP, затем введите UUID рабочей области. Решение L3 принимает только уполномоченный человек.</p>
<button id="login">Войти</button> <span id="status"></span>
<p><label>Workspace UUID <input id="workspace" size="40" required></label>
<button id="load">Загрузить пакет</button></p>
<pre id="package"></pre>
<p><label>Причина review <input id="reason" size="55"></label></p>
<p><label>URI проверенного свидетельства <input id="evidence" size="55"></label></p>
<button id="review">Записать независимую проверку</button>
<p><button id="approve">Утвердить baseline (L3)</button></p>
<p><label>Причина отказа <input id="rejection" size="55"></label>
<button id="reject">Отклонить (L3)</button></p>
<script src="ui.js" defer></script></html>"""

SCRIPT = r"""'use strict';
const $ = id => document.getElementById(id);
const status = message => { $('status').textContent = message; };
const b64url = bytes => btoa(String.fromCharCode(...new Uint8Array(bytes)))
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
let config, token;
const redirect = location.origin + '/human/';
async function loadConfig() {
  const response = await fetch('/human/config', {cache: 'no-store'});
  if (!response.ok) throw Error('Не удалось получить настройки IdP');
  config = await response.json();
}
async function login() {
  const verifier = b64url(crypto.getRandomValues(new Uint8Array(32)));
  const state = b64url(crypto.getRandomValues(new Uint8Array(24)));
  sessionStorage.setItem('gateway_pkce', JSON.stringify({verifier, state}));
  const challenge = b64url(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier)));
  const url = new URL(config.issuer + '/protocol/openid-connect/auth');
  url.search = new URLSearchParams({client_id: config.client_id, redirect_uri: redirect,
    response_type: 'code', scope: 'openid', code_challenge_method: 'S256', code_challenge: challenge,
    state}).toString();
  location.assign(url.toString());
}
async function finishLogin() {
  const params = new URLSearchParams(location.search);
  if (!params.has('code') && !params.has('error')) return;
  history.replaceState(null, '', redirect);
  if (params.has('error')) throw Error('IdP отказал во входе: ' + params.get('error'));
  const saved = JSON.parse(sessionStorage.getItem('gateway_pkce') || 'null');
  sessionStorage.removeItem('gateway_pkce');
  if (!saved || params.get('state') !== saved.state) throw Error('OIDC state не совпадает');
  const response = await fetch(config.issuer + '/protocol/openid-connect/token', {
    method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: new URLSearchParams({grant_type:'authorization_code', client_id:config.client_id,
      redirect_uri:redirect, code:params.get('code'), code_verifier:saved.verifier})});
  if (!response.ok) throw Error('Не удалось обменять код входа');
  const data = await response.json();
  token = data.access_token;
  status('Вход выполнен. Токен хранится только в памяти этой вкладки.');
}
async function request(path, method='GET', body) {
  if (!token) throw Error('Сначала войдите через IdP');
  const response = await fetch('/human/workspaces/' + encodeURIComponent($('workspace').value.trim()) + path, {
    method, headers: {Authorization: 'Bearer ' + token, ...(body ? {'Content-Type':'application/json'} : {})},
    body: body ? JSON.stringify(body) : undefined, cache: 'no-store'});
  const data = await response.json();
  if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data));
  return data;
}
function run(fn) { return () => fn().catch(error => status(error.message)); }
window.addEventListener('DOMContentLoaded', run(async () => {
  await loadConfig(); await finishLogin();
  $('login').onclick = run(login);
  $('load').onclick = run(async () => {
    const data = await request(''); $('package').textContent = JSON.stringify(data, null, 2);
    status('Пакет получен. Проверьте версии, хэши и исходные артефакты.');
  });
  $('review').onclick = run(async () => {
    await request('/review', 'POST', {accepted:true, reason:$('reason').value,
      evidence_uri:$('evidence').value}); status('Review записан.');
  });
  $('approve').onclick = run(async () => {
    if (!confirm('Вы лично проверили содержимое и утверждаете baseline?')) return;
    const result = await request('/approve', 'POST');
    status('Baseline: ' + result.baseline_id + ', Git tag: ' + result.git_tag);
  });
  $('reject').onclick = run(async () => {
    if (!confirm('Отклонить рабочую область?')) return;
    await request('/reject', 'POST', {reason:$('rejection').value}); status('Рабочая область отклонена.');
  });
}));
"""
