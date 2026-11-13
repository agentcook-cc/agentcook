package cc.agentcook.api.contract;

import au.com.dius.pact.provider.junit5.HttpTestTarget;
import au.com.dius.pact.provider.junit5.PactVerificationContext;
import au.com.dius.pact.provider.junit5.PactVerificationInvocationContextProvider;
import au.com.dius.pact.provider.junitsupport.Provider;
import au.com.dius.pact.provider.junitsupport.State;
import au.com.dius.pact.provider.junitsupport.loader.PactBroker;
import au.com.dius.pact.provider.junitsupport.loader.PactBrokerAuth;
import cc.agentcook.api.ApiIntegrationTestBase;
import cc.agentcook.api.auth.JwtTokenIssuer;
import cc.agentcook.application.port.out.PasswordHasher;
import cc.agentcook.domain.user.User;
import cc.agentcook.domain.user.UserRepository;
import org.apache.hc.core5.http.HttpRequest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.TestTemplate;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.TestPropertySource;

/** Verifies the admin consumer pact against a real Java HTTP server. */
@Provider("agentcook-java")
@PactBroker(url = "${PACT_BROKER_URL:http://localhost:9292}",
        authentication = @PactBrokerAuth(username = "${PACT_BROKER_USER:pact}",
                password = "${PACT_BROKER_PASSWORD:pact}"))
@Tag("pact-verify")
@TestPropertySource(properties = "agentcook.auth.admins=admin")
@EnabledIfEnvironmentVariable(named = "PACT_BROKER_ENABLE", matches = "true")
class JavaProviderPactBrokerVerifyTest extends ApiIntegrationTestBase {

    @LocalServerPort
    private int port;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private PasswordHasher passwordHasher;

    @Autowired
    private JwtTokenIssuer tokenIssuer;

    private User admin;

    @BeforeEach
    void target(PactVerificationContext context) {
        context.setTarget(new HttpTestTarget("127.0.0.1", port, "/"));
    }

    @TestTemplate
    @ExtendWith(PactVerificationInvocationContextProvider.class)
    void verifyPact(PactVerificationContext context, HttpRequest request) {
        var authorization = request.getFirstHeader("Authorization");
        if (authorization != null && "Bearer admin-access-token".equals(authorization.getValue())) {
            request.setHeader("Authorization", "Bearer " + tokenIssuer.issue(admin).accessToken());
        }
        context.verifyInteraction();
    }

    @State({
            "admin account with a password exists",
            "an administrator and at least one user exist",
            "the plugin version has not been registered"
    })
    void adminExists() {
        admin = User.create("admin@dev.local", "Administrator");
        admin.changePasswordHash(passwordHasher.hash("admin-password-123"));
        admin = userRepository.save(admin);
    }
}
