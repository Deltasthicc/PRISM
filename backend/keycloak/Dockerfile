# Hosted variant of the local dev Keycloak (docker-compose.dev.yml's
# `keycloak` service) -- same image, same realm, same test users. The only
# difference is *where* it runs: this bakes prism-realm-export.json into the
# image so a host like Render can build and run it directly from a
# Dockerfile, without a mounted volume. Still not a government-approved
# production IdP -- SIH26101_MASTER_CHECKLIST.md 5.1 tracks that separately
# as BLOCKED-EXTERNAL. See ../keycloak/README.md for the realm/test-user
# contract this image ships unchanged.
FROM quay.io/keycloak/keycloak:26.7.2

COPY prism-realm-export.json /opt/keycloak/data/import/prism-realm-export.json

# start-dev (not `start`) matches the existing local-dev precedent exactly:
# an embedded, non-persistent database is fine here because the entire realm
# is declaratively re-imported from the file above on every boot -- there is
# no runtime state worth keeping across restarts/redeploys. KC_HOSTNAME must
# match this service's real public hostname once deployed, or every issued
# token's `iss` claim won't match what OIDC_ISSUER expects on the backend;
# KC_PROXY_HEADERS tells Keycloak to trust the X-Forwarded-* headers a host
# like Render terminates TLS and proxies through, so it reports itself as
# https:// even though the container only ever speaks plain HTTP internally.
ENV KC_HOSTNAME=CHANGE_ME.onrender.com
ENV KC_PROXY_HEADERS=xforwarded
ENV KC_HTTP_ENABLED=true

EXPOSE 8080

CMD ["start-dev", "--import-realm"]
