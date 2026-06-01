package cc.agentcook.api.config;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.io.IOException;
import java.util.UUID;

/**
 * Observability configuration: request tracing via correlation-id,
 * Micrometer timer per controller path, and structured MDC propagation.
 *
 * <p>Phase 4 replaces this with full OpenTelemetry SDK + OTLP exporter.
 * Current implementation provides:
 * <ul>
 *   <li>X-Correlation-Id header (generated if absent)</li>
 *   <li>MDC correlation_id for structured logging</li>
 *   <li>Micrometer timer per endpoint</li>
 * </ul>
 */
@Configuration
public class ObservabilityConfig {

    @Bean
    public Filter correlationIdFilter(MeterRegistry meterRegistry) {
        return new CorrelationIdFilter(meterRegistry);
    }

    static class CorrelationIdFilter implements Filter {

        private final MeterRegistry meterRegistry;

        CorrelationIdFilter(MeterRegistry meterRegistry) {
            this.meterRegistry = meterRegistry;
        }

        @Override
        public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
                throws IOException, ServletException {
            if (!(request instanceof HttpServletRequest httpRequest)
                    || !(response instanceof HttpServletResponse httpResponse)) {
                chain.doFilter(request, response);
                return;
            }

            String correlationId = httpRequest.getHeader("X-Correlation-Id");
            if (correlationId == null || correlationId.isBlank()) {
                correlationId = UUID.randomUUID().toString();
            }

            MDC.put("correlation_id", correlationId);
            MDC.put("method", httpRequest.getMethod());
            MDC.put("path", httpRequest.getRequestURI());
            httpResponse.setHeader("X-Correlation-Id", correlationId);

            Timer.Sample sample = Timer.start(meterRegistry);
            try {
                chain.doFilter(request, response);
            } finally {
                sample.stop(Timer.builder("http.server.requests.custom")
                        .tag("method", httpRequest.getMethod())
                        .tag("uri", httpRequest.getRequestURI())
                        .tag("status", String.valueOf(httpResponse.getStatus()))
                        .register(meterRegistry));
                MDC.clear();
            }
        }
    }
}
