FROM maven:3.9.9-eclipse-temurin-21 AS provider
WORKDIR /build
COPY infra/keycloak/providers/email-otp-reset/pom.xml ./pom.xml
COPY infra/keycloak/providers/email-otp-reset/src/main ./src/main
RUN mvn -B -ntp -Dmaven.test.skip=true package

FROM quay.io/keycloak/keycloak:26.3.3
COPY --from=provider /build/target/email-otp-reset-0.1.0-SNAPSHOT.jar /opt/keycloak/providers/email-otp-reset.jar
COPY themes/knora /opt/keycloak/themes/knora
RUN /opt/keycloak/bin/kc.sh build --db=postgres --vault=file
