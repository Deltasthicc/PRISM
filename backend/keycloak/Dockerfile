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

# Render's free web-service tier caps the container at 512Mi total -- left to
# its own defaults, the JVM sizes its heap off the host's *visible* memory,
# not the container's cgroup limit, and gets OOM-killed partway through
# realm import. Verified directly, iteratively, against a hard
# `docker run --memory=512m --memory-swap=512m` cap (the exact constraint
# Render enforces):
#   - No tuning at all: reproduced Render's failure exactly (~181s spent in
#     "Quarkus augmentation" instead of ~15s, then OOM-killed before ever
#     reaching "Initializing master realm").
#   - Adding -XX:+UseSerialGC alongside a large heap: hard-failed a
#     different way ("Multiple garbage collectors selected") -- Keycloak's
#     own entrypoint already computes and appends its own GC choice based on
#     detected memory, and JAVA_OPTS_APPEND's value lands *after* that, so an
#     explicit GC flag here conflicts with it outright. Removed.
#   - -Xmx300m: booted, but sat at 94% of the 512Mi limit at rest (482Mi) --
#     survives one boot, not enough headroom to trust under real concurrent
#     use.
#   - -XX:MaxMetaspaceSize=100m (heap cut further, metaspace cut too far):
#     a *different* OOM ("Terminating due to java.lang.OutOfMemoryError:
#     Metaspace") -- Keycloak's own class loading needs more than that.
#   - The values below: boots reliably, survives, and issues real tokens,
#     but still sits around ~90-92% of 512Mi at rest (roughly 460-470Mi) --
#     this appears to be close to this JVM stack's (Quarkus/Infinispan/
#     Hibernate) real fixed floor on this image, not something further flag
#     tuning meaningfully moves. If this proves flaky under real multi
#     -teammate concurrent login load (visible as this service intermittently
#     restarting in Render's dashboard), the actual fix is upgrading
#     prism-keycloak's Render plan to its smallest paid tier for more RAM,
#     not further JVM flag archaeology.
# Disabling health/metrics removes two subsystems this deployment never
# queries but otherwise reserves memory for regardless.
ENV JAVA_OPTS_APPEND="-Xms32m -Xmx180m -XX:MetaspaceSize=64m -XX:MaxMetaspaceSize=180m -XX:ReservedCodeCacheSize=48m -Xss512k"
ENV KC_HEALTH_ENABLED=false
ENV KC_METRICS_ENABLED=false

EXPOSE 8080

CMD ["start-dev", "--import-realm"]
