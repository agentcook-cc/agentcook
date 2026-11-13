package cc.agentcook.api.grpc;

import io.grpc.Context;
import io.grpc.Contexts;
import io.grpc.Metadata;
import io.grpc.ServerCall;
import io.grpc.ServerCallHandler;
import io.grpc.ServerInterceptor;

/** Carries authorization per call; the runtime validates the forwarded access token. */
public final class AuthorizationInterceptor implements ServerInterceptor {
    static final Context.Key<String> AUTHORIZATION = Context.key("authorization");
    private static final Metadata.Key<String> HEADER = Metadata.Key.of("authorization", Metadata.ASCII_STRING_MARSHALLER);

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call, Metadata headers, ServerCallHandler<ReqT, RespT> next) {
        return Contexts.interceptCall(Context.current().withValue(AUTHORIZATION, headers.get(HEADER)), call, headers, next);
    }
}
