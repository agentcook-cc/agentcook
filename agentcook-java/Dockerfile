# agentcook-java — single-stage local-build image.
#
# Why single-stage:
#   The CI multi-stage build (Dockerfile.ci) re-runs `mvn package` inside
#   a Maven container and re-pulls every dependency from a cold ~/.m2 —
#   30-40 minutes on the China-mainland network with BuildKit disabled
#   (we disable it to avoid the dockerfile:1.6 frontend mirror TLS fault).
#
#   Local rebuilds are high-frequency (per the "Day 31 rebuild" rule:
#   every D progress closes by re-imaging) so we trade reproducibility
#   for speed: this Dockerfile assumes the host has already run
#   `mvn -pl agentcook-api -am package -DskipTests`, then just COPYs
#   the resulting fat jar into a JRE base image. ~5 seconds.
#
#   CI / GitHub Actions still uses Dockerfile.ci so the published image
#   does not depend on the developer's host having run mvn first.
#
# Usage:
#   mvn -pl agentcook-api -am package -DskipTests   # produces target/agentcook-api-*.jar
#   docker build -t agentcook-java:1.0.0 -t agentcook-java:latest .

FROM eclipse-temurin:17-jre-jammy

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r app && useradd -r -g app app
USER app

WORKDIR /app

# Spring Boot fat jar — the executable artifact emitted by
# spring-boot-maven-plugin's `repackage` goal during `mvn package`.
COPY --chown=app:app agentcook-api/target/agentcook-api-*-SNAPSHOT.jar /app/agentcook-java.jar

EXPOSE 8080 9090

# K8s-aware JVM defaults — see Dockerfile.ci for full rationale.
ENV JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75 -XX:+UseG1GC -XX:+UseStringDeduplication -XX:+ExitOnOutOfMemoryError" \
    SPRING_PROFILES_ACTIVE=docker

HEALTHCHECK --interval=15s --timeout=3s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8080/actuator/health | grep -q '"status":"UP"' || exit 1

# exec form forwards SIGTERM so Spring Boot graceful shutdown gets the
# 30s drain window K8s grants on pod termination.
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/agentcook-java.jar"]
