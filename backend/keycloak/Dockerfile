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

# KC_HOSTNAME must match this service's real public hostname once deployed,
# or every issued token's `iss` claim won't match what OIDC_ISSUER expects on
# the backend; KC_PROXY_HEADERS tells Keycloak to trust the X-Forwarded-*
# headers a host like Render terminates TLS and proxies through, so it
# reports itself as https:// even though the container only ever speaks
# plain HTTP internally.
ENV KC_HOSTNAME=CHANGE_ME.onrender.com
ENV KC_PROXY_HEADERS=xforwarded
ENV KC_HTTP_ENABLED=true

# health/metrics are BUILD-time options (they change which Quarkus features
# get compiled in) -- must be set before `kc.sh build` below, not just at
# runtime, or the build won't actually reflect them. (KC_CACHE below is NOT
# build-time -- `kc.sh build`'s own output confirms it: "kc.cache ... will be
# ignored during build time" -- it only needs to exist as a runtime env var,
# which ENV still guarantees regardless of where it's declared relative to
# the build step; kept alongside the other Keycloak env vars for
# readability, not because ordering matters here.)
ENV KC_HEALTH_ENABLED=false
ENV KC_METRICS_ENABLED=false
# Render only ever runs one instance of this service (WEB_CONCURRENCY=1) --
# there is no second node to ever cluster with. Left on Keycloak's default
# clustered ("ispn") cache, it still starts a JGroups TCP transport and
# spends minutes retrying peer discovery against itself over Render's
# networking before giving up and continuing anyway -- confirmed directly in
# a real deploy log: ~2m20s of `JGRP000006: ... failed accepting connection
# from peer ... cookie ... does not match own cookie` repeating every ~5s,
# directly inflating that boot to started in 339.701s. `local` is the
# correct, documented Keycloak option for exactly this shape of deployment
# (single node, no clustering ever intended) and skips JGroups/Infinispan
# clustering setup entirely.
ENV KC_CACHE=local

# `start-dev` (the local-dev-compose default) re-runs Keycloak's "Quarkus
# augmentation" build step from scratch on every single container boot --
# fine on a laptop, but confirmed live on Render's free tier to take ~199s of
# a ~289s total startup, which blew straight through Render's port-detection
# timeout ("==> Timed Out", the container killed before it ever finished
# booting) even though the memory tuning below worked and it wasn't OOM
# -killed this time. Doing that same build once here, at image-build time --
# not gated by any request timeout -- and starting with `--optimized`
# instead removes that ~199s from every boot. `--import-realm` still applies
# at actual container start (after this build), so the realm/test-user
# import behavior is unchanged.
RUN /opt/keycloak/bin/kc.sh build

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
ENV JAVA_OPTS_APPEND="-Xms32m -Xmx180m -XX:MetaspaceSize=64m -XX:MaxMetaspaceSize=180m -XX:ReservedCodeCacheSize=48m -Xss512k"

EXPOSE 8080
USER 1000
CMD ["start", "--optimized", "--import-realm"]
