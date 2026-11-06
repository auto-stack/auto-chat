#!/usr/bin/env python3
"""CHAT-003 response contract; use an explicitly owned loopback test service.
Credentials stay in process memory and are never included in failure output.
No reset or existing identity modification is performed.
"""
import json, os, re, secrets, urllib.request

base = os.environ["CHAT_API"].rstrip("/")
if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]+", base):
    raise SystemExit("explicit owned loopback CHAT_API required")

def post(path, body):
    request = urllib.request.Request(base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read()
        return json.loads(body) if body else None

name = "C003-" + secrets.token_hex(8)
registered = post("/api/register", {"name": name})
assert registered.get("ok"), "registration rejected"
nonce1 = registered.get("send_nonce", "")
assert re.fullmatch("[0-9a-f]{64}", nonce1), "register nonce shape"
assert nonce1 not in (registered.get("secret"), registered.get("token")), "nonce must be independent of credentials"
recovered = post("/api/login", {"name": name, "secret": registered["secret"]})
assert recovered.get("ok"), "recovery rejected"
nonce2 = recovered.get("send_nonce", "")
assert re.fullmatch("[0-9a-f]{64}", nonce2), "login nonce shape"
assert nonce2 != nonce1, "recovered session reused intent prefix"
assert nonce2 not in (registered["secret"], recovered.get("token")), "login nonce exposes credential"
denied = post("/api/login", {"name": name, "secret": "invalid-owned-test-credential"})
assert not denied.get("ok") and not denied.get("send_nonce"), "rejected authentication must not issue an intent prefix"
post("/api/logout", {"token": recovered["token"]})
print(json.dumps({"case": "C01", "passed": True, "checks": 8, "credentials_logged": False}))
