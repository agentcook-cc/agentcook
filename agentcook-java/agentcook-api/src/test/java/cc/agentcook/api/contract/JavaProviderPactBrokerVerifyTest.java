package cc.agentcook.api.contract;

import au.com.dius.pact.provider.junit5.HttpTestTarget;
import au.com.dius.pact.provider.junit5.PactVerificationContext;
import au.com.dius.pact.provider.junit5.PactVerificationInvocationContextProvider;
import au.com.dius.pact.provider.junitsupport.Provider;
import au.com.dius.pact.provider.junitsupport.State;
import au.com.dius.pact.provider.junitsupport.loader.PactBroker;
import cc.agentcook.api.ApiIntegrationTestBase;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserRepository;
import org.junit.jupiter.api.TestTemplate;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.server.LocalServerPort;

/**
 * Verifies the Java provider against consumer pacts pulled from the
 * docker-compose pact broker (default URL {@code http://localhost:9292}).
 *
 * <p>Day 24 attempted the {@code @PactFolder} variant of this same
 * machinery and hit a pact-jvm 4.6.10 client-level 401 that did not
 * reproduce against the same endpoint via plain HTTP. The broker code
 * path uses different transport internals; if it still 401s we fall
 * back to {@code ContractScaffoldingTest} (kept in this package) and
 * revisit in Phase 5.</p>
 *
 * <p>Gated by {@code PACT_BROKER_ENABLE=true} so a missing or empty
 * broker (e.g. fresh dev machine without docker-compose up) doesn't
 * fail the default {@code mvn test}. CI sets the var explicitly.</p>
 */
@Provider("agentcook-java")
@PactBroker(url = "http://localhost:9292")
@EnabledIfEnvironmentVariable(named = "PACT_BROKER_ENABLE", matches = "true")
class JavaProviderPactBrokerVerifyTest extends ApiIntegrationTestBase {

    @LocalServerPort
    private int port;

    @Autowired
    private UserRepository userRepository;

    @TestTemplate
    @ExtendWith(PactVerificationInvocationContextProvider.class)
    void verifyPact(PactVerificationContext context) {
        context.setTarget(new HttpTestTarget("localhost", port, "/"));
        context.verifyInteraction();
    }

    // --- Provider states (declared by the agentcook-admin consumer pact) ---

    @State("Java dev profile auth is enabled")
    void devAuthEnabled() {
        // No-op: Phase 3 SecurityConfig opens /** via WebSecurityCustomizer
        // and AuthController.login returns a dev dummy token for any
        // non-blank password. Nothing to seed.
    }

    @State("at least one user exists")
    void atLeastOneUserExists() {
        userRepository.save(User.create("pact-seed@example.com", "Pact Seed"));
    }

    @State("the admin uploader has a valid plugin zip")
    void adminUploaderHasValidZip() {
        // No-op: the consumer drives the upload by attaching a real zip
        // body in its pact interaction. No server-side seed needed —
        // the provider just needs to accept multipart on POST /plugins.
    }
}
