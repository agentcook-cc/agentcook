package cc.agentcook.api.config;

import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;

import java.io.IOException;

/**
 * Injects {@code API-Version} response header on every response.
 * Matches the v1.yaml spec version (1.2.0 as of Day 31).
 */
@Component
public class ApiVersionFilter implements Filter {

    private static final String API_VERSION = "1.2.0";

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        if (response instanceof HttpServletResponse httpResponse) {
            httpResponse.setHeader("API-Version", API_VERSION);
        }
        chain.doFilter(request, response);
    }
}
