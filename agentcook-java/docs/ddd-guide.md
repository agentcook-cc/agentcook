# `agentcook-java` — DDD Four-Layer Guide

A walk-through of how the DDD four-layer pattern lands in this Spring
Boot module, with the five aggregates as worked examples and the
hexagonal dependency direction as the load-bearing constraint.

> **Audience**: someone who has read about DDD but hasn't built a
> production module with it, OR someone reading 教程第 03 讲 and
> wanting the implementation companion.
> **Prerequisites**: comfortable with Spring Boot 3, JPA, Java 17
> records.

The structure mirrors the way the chapters introduce things — start
with the aggregate, build up to the application boundary, then look
at the adapters that wire it to JPA and HTTP last. Reading top-down
is the recommended order.

---

## 0 · TL;DR diagram

```
            ┌───────────────────────────────────────────────────┐
   incoming │  agentcook-api          (Spring MVC controllers,  │
   HTTP /   │   ▲▲                     Spring Security OAuth2,  │
   gRPC     │   ▲                      gRPC bridge to Python)   │
   request  │   ▲                                               │
            │  agentcook-application  (UseCase + Input/Output  │
            │   ▲                      Ports, @Service +        │
            │   ▲                      @Transactional)          │
            │   ▲                                               │
            │  agentcook-domain       (Aggregates, Value        │
            │   ▲                      Objects, Domain Events,  │
            │   ▲                      Repository ports —       │
            │   ▲                      pure Java, no Spring)    │
            │   ▲                                               │
            │  agentcook-infrastructure (JPA + Flyway + Redis,  │
            │                            adapters implement     │
            │                            domain Repository      │
            │                            ports)                 │
            └───────────────────────────────────────────────────┘
```

Every arrow points **up** towards the domain. Domain depends on
nothing in this project (only on the JDK and Jakarta-validation
annotations). Infrastructure depends on domain — not the other way
round, because if you let JPA leak into the domain, you can't ever
hold an aggregate in your head without also thinking about
constraint cascading, lazy loading, and dirty tracking.

The dependency rule is enforced by the Maven module graph (the
`pom.xml` for `agentcook-domain` lists zero dependencies on
`agentcook-infrastructure` or `agentcook-api`). It's not a guideline,
it's a build-time hard wall.

---

## 1 · The Domain Layer — `agentcook-domain`

Five aggregates fall out of the running user story for this codebase:
*"an authenticated user activates a plugin to talk to a model from
a chat session."*

| Aggregate | Why it's an aggregate root |
|---|---|
| **`User`** | Identity boundary — every other aggregate references the user by ID, never by holding a `User` reference |
| **`Session`** | Independent lifecycle from `User` (deleted users keep sessions for audit; archived sessions don't suspend their user) |
| **`Plugin`** | Has an independent publishing lifecycle (draft → published → deprecated) decoupled from any user |
| **`Connector`** | An instance of a Plugin bound to a config — same Plugin can have many Connectors with different webhook URLs |
| **`Permission`** | Audit-relevant on its own; cannot be a child of User because permission grants/revokes form their own history |

The reasoning here is the classic Evans test: "if I delete the parent,
does it make sense for this thing to keep existing?" For a Session,
the answer is yes (audit logs reference it after user deletion), so
it's its own aggregate.

### 1.1 Aggregate shape — `User` as the template

Every aggregate in this module follows the same shape:

```java
public class User {

    private final UserId id;       // VO, never null, never changes
    private String email;
    private String nickname;
    private UserStatus status;     // enum
    private Instant createdAt;
    private Instant updatedAt;

    private final List<Object> domainEvents = new ArrayList<>();

    // Constructor is private — entry points are the two factory methods
    private User(...) { ... }

    public static User create(String email, String nickname) {
        // Validates inputs, builds the aggregate, RAISES UserCreatedEvent
    }

    public static User reconstitute(UserId id, String email, String nickname,
                                    UserStatus status,
                                    Instant createdAt, Instant updatedAt) {
        // Used by infrastructure when loading from JPA — does NOT raise events
    }

    public void suspend() { /* state transition + invariant check */ }
    public void activate() { /* state transition + invariant check */ }
    public void markDeleted() { /* state transition + invariant check */ }
    public void updateProfile(String nickname) { /* update + validation */ }

    public UserId getId() { return id; }
    public UserStatus getStatus() { return status; }
    public List<Object> getDomainEvents() { return domainEvents; }
    public void clearDomainEvents() { domainEvents.clear(); }

    // equals / hashCode based on id only (entity identity, not value equality)
}
```

Three properties that show up in every aggregate here:

1. **`create()` raises events; `reconstitute()` does not.** When JPA
   pulls a row from `postgres` and builds the aggregate, the entity
   already existed — we don't want to emit `UserCreatedEvent` every
   time we read. The split is the cleanest way to encode that.
2. **State transitions are methods, not setters.** `suspend()` /
   `activate()` carry the business rule ("a deleted user cannot be
   activated") inside the aggregate. There's no `setStatus()` in the
   public surface — that would let callers drive the aggregate
   through illegal transitions.
3. **`equals` / `hashCode` use only the id.** Two `User` instances
   loaded from the database in separate transactions with the same
   id are the same user; the `updatedAt` timestamps will differ but
   that's not identity.

### 1.2 Value Objects — `UserId` as the template

Every aggregate identifier is a wrapped `UUID` value object, not a
raw `UUID`:

```java
public record UserId(UUID value) {
    public UserId { Objects.requireNonNull(value); }
    public static UserId generate() { return new UserId(UUID.randomUUID()); }
    public static UserId from(String s) { return new UserId(UUID.fromString(s)); }
    public static UserId from(UUID u) { return new UserId(u); }
}
```

Why bother? Because once `UserId` is its own type, the compiler stops
you from passing a `SessionId` where a `UserId` was expected —
something that bites every project that types user/session/order ids
all as `UUID`. Java records make the wrapping cost essentially zero
in source and one allocation in runtime.

### 1.3 Domain Events

Four of the five aggregates emit a `*CreatedEvent` from their
`create()` factory:

| Aggregate | Event class |
|---|---|
| `User` | `UserCreatedEvent` |
| `Session` | `SessionCreatedEvent` |
| `Plugin` | `PluginPublishedEvent` |
| `Connector` | `ConnectorEstablishedEvent` |
| `Permission` | (no event today; granted/revoked logs go through `application-event-bus` in Phase 5 backlog) |

Events are plain records. They are **not** Spring events — domain
should never depend on Spring. The application layer (or an
infrastructure adapter) is responsible for draining
`aggregate.getDomainEvents()` after the transaction commits and
publishing them onto whatever bus the deployment uses (Spring
ApplicationEvent for in-process, Kafka for prod, etc.).

The drain pattern lives in
`agentcook-application/src/main/java/cc/agentcook/application/usecase/CreateUserUseCaseImpl.java`:

```java
@Transactional
public User execute(CreateUserCommand cmd) {
    User user = User.create(cmd.email(), cmd.nickname());
    userRepository.save(user);
    user.getDomainEvents().forEach(eventPublisher::publish);
    user.clearDomainEvents();
    return user;
}
```

This is the only place in the codebase that knows events exist — the
domain doesn't, the controller doesn't, the JPA adapter doesn't.

### 1.4 Domain Services — `PluginActivationService`

A *domain service* solves the problem "this operation spans multiple
aggregates and doesn't belong inside any one of them."
`PluginActivationService.activatePlugin(...)` is the only one in this
module:

```java
public Connector activatePlugin(UserId userId, Plugin plugin, String connectorConfig) {
    if (!hasActivatePermission(userId, plugin.getName())) {
        throw new PluginActivationDeniedException(userId, plugin.getName());
    }
    plugin.publish();
    pluginRepository.save(plugin);
    Connector connector = Connector.establish(plugin.getId(), plugin.getKind(), connectorConfig);
    connectorRepository.save(connector);
    return connector;
}
```

It coordinates `Permission` (read) + `Plugin` (state transition) +
`Connector` (create), but lives in `agentcook-domain` because the
business rule "activation = permission-check ∧ publish ∧ establish"
is itself a domain concept, not a UI / wiring concern.

Crucially the constructor takes the **Repository ports** as
dependencies — these are interfaces declared in the domain package,
not Spring `@Repository` interfaces. The infrastructure layer provides
the implementation; the domain doesn't know it's talking to JPA.

---

## 2 · The Application Layer — `agentcook-application`

Thin orchestration on top of domain. Every UseCase is:

- One Input Port interface (named `CreateUserUseCase`, etc.) plus a
  Command record (`CreateUserCommand`)
- One UseCase implementation (`CreateUserUseCaseImpl`) marked
  `@Service @Transactional`
- One `@Test` class that mocks the Repository ports and asserts the
  business outcomes

That's it. No DTOs (those live in `agentcook-api`), no business logic
(that lives in the aggregate), no logging-as-flow-control.

The 17 UseCases in this module add up to about 600 lines of
implementation code — most of them are 15-25 lines, of the shape:

```java
@Service
@Transactional
public class CreateSessionUseCaseImpl implements CreateSessionUseCase {

    private final SessionRepository sessionRepository;
    private final UserRepository userRepository;

    public CreateSessionUseCaseImpl(SessionRepository sessionRepository,
                                    UserRepository userRepository) {
        this.sessionRepository = sessionRepository;
        this.userRepository = userRepository;
    }

    @Override
    public Session execute(CreateSessionCommand cmd) {
        UserId userId = UserId.from(cmd.userId());
        if (!userRepository.existsById(userId)) {
            throw new UserNotFoundException(userId);
        }
        Session session = Session.create(userId, cmd.title());
        return sessionRepository.save(session);
    }
}
```

That's the whole thing. The two reasons it's not thinner are:

1. We have to map `String userId` → `UserId` here because the API
   layer above us deals in strings (HTTP request bodies don't know
   about VOs). The domain stays in VOs throughout; conversion happens
   at the application seam.
2. We do the `existsById` check here, not inside the aggregate,
   because "session must belong to a known user" is an application
   invariant (we could imagine cross-tenant orchestrators that violate
   it intentionally); meanwhile "session status is one of {ACTIVE,
   ARCHIVED, DELETED}" is a domain invariant and lives inside
   `Session`.

The split between application-level and domain-level invariants is
fuzzy but the heuristic above is what we use in this codebase: if you
can imagine a future caller who'd legitimately violate the rule, it's
an application rule.

---

## 3 · The Infrastructure Layer — `agentcook-infrastructure`

JPA + Flyway + Redis + etcd live here. The pattern is:

1. **Entity ≠ Aggregate.** Each aggregate has a sibling
   `*Entity` JPA class that mirrors the table layout. The
   `UserEntity` has `@Id`, `@Column`, `@Version` annotations; the
   `User` aggregate has none of them.
2. **`*RepositoryAdapter` implements the domain Repository port,
   delegates to a `Jpa*Repository` Spring Data interface.** The
   adapter does the entity↔aggregate mapping inline.

Sample shape (`UserRepositoryAdapter.java`):

```java
@Component
public class UserRepositoryAdapter implements UserRepository {

    private final JpaUserRepository jpa;

    @Override
    public User save(User user) {
        UserEntity e = UserEntity.fromAggregate(user);
        UserEntity saved = jpa.save(e);
        return saved.toAggregate();
    }

    @Override
    public Optional<User> findById(UserId id) {
        return jpa.findById(id.value()).map(UserEntity::toAggregate);
    }
}
```

The mapping helpers (`fromAggregate` / `toAggregate`) live on the
entity class. Hand-written, not MapStruct — five aggregates with
6-10 fields each don't justify a code generator, and the mapping
logic is the kind of thing that's clearest at the call site.

### Why no entity-as-aggregate?

Two reasons we keep them separate even though it doubles the row
count:

1. **JPA lifecycle leaks otherwise.** A managed entity wrapped in a
   transaction will silently `UPDATE` if any field changes between
   load and commit. Aggregate methods need to be the only place that
   can mutate state — putting JPA on the aggregate makes "I changed
   this field as a side effect in a query" possible.
2. **Reconstitution stays explicit.** `*Entity.toAggregate()` calls
   `User.reconstitute(...)` (note: not `User.create(...)`) so we
   never accidentally emit a `UserCreatedEvent` for a load. With
   the same class playing both roles, that distinction blurs.

The cost is a layer of boilerplate; the win is being able to read any
aggregate file and know it's pure domain.

---

## 4 · The API Layer — `agentcook-api`

`@RestController` + DTO records + OpenAPI annotations + Spring
Security + gRPC server. This layer:

- Translates HTTP requests → UseCase commands
- Translates UseCase results → HTTP responses (`*Response` DTO records)
- Owns the authentication / authorization chain (Spring Security
  `oauth2ResourceServer().jwt()` — HS256 dev / RS256+JWKS Phase 4
  Day 33-34)
- Owns the gRPC bridge to Python's `/api/v1/chat/stream`
  (`GrpcChatService` — see [gRPC integration](#5-grpc-integration))

Sample controller (`UserController.java`):

```java
@RestController
@RequestMapping("/api/v1/users")
public class UserController {

    private final CreateUserUseCase createUserUseCase;
    private final UserRepository userRepository;

    @PostMapping
    public ResponseEntity<UserResponse> createUser(@Valid @RequestBody CreateUserRequest body) {
        User user = createUserUseCase.execute(new CreateUserCommand(body.email(), body.nickname()));
        return ResponseEntity.created(URI.create("/api/v1/users/" + user.getId().value()))
                .body(UserResponse.from(user));
    }
}
```

DTOs are records with one factory:

```java
public record UserResponse(UUID id, String email, String nickname, String status) {
    public static UserResponse from(User user) {
        return new UserResponse(
            user.getId().value(),
            user.getEmail(),
            user.getNickname(),
            user.getStatus().name());
    }
}
```

The "DTO ≠ entity ≠ aggregate" triplet looks like over-engineering
until the first time you want to expose a different shape over
HTTP than what JPA stores — at which point it's already in the
right place.

---

## 5 · gRPC integration

`agentcook-api/src/main/java/cc/agentcook/api/grpc/` hosts the
`GrpcChatService` that bridges admin-bff chat requests to the Python
`/api/v1/chat/stream` SSE endpoint. The shape is:

```
client → admin-bff /api/v1/chat (REST)
       → admin-bff GrpcChatService.streamChat (gRPC server-side stream)
       → Python /api/v1/chat/stream (SSE)
```

The bridge is plain Java HTTP (no `WebClient` reactive stack) because
the existing code paths are blocking-style and pulling reactive in
would force the rest of the controller layer to follow. The
`GrpcServerConfig` boots the embedded grpc Server alongside the
Spring Boot HTTP server on port 9090 (separate Service in the K8s
chart, see `deploy/helm/agentcook/templates/service.yaml`).

Cross-language JWT handling is tested in
`CrossLangIntegrationIT` (Day 49): the Java-issued Bearer token is
forwarded byte-identical to the Python SSE upstream — this is the
property that lets you mint tokens in one language and validate in
another without splitting the secret-management story.

---

## 6 · Testing the seams

The testing pyramid maps onto the layer split cleanly:

| Layer | Test type | Where it lives | What you assert |
|---|---|---|---|
| Domain | Pure unit | `agentcook-domain/src/test/.../*Test.java` | Aggregate invariants, state transitions, factory rules |
| Domain (cross-aggregate) | Unit with mocks | `PluginActivationServiceTest.java` | Coordination logic with mocked Repository ports |
| Application | Unit with mocks | `agentcook-application/src/test/.../*UseCaseImplTest.java` | UseCase wires aggregate methods correctly |
| Infrastructure | Integration | `*RepositoryAdapterIntegrationTest.java` (`@SpringBootTest` + Testcontainers postgres) | Adapter persists + reconstitutes round-trip |
| API | Integration | `*ControllerIntegrationTest.java` (`@SpringBootTest` + MockMvc) | HTTP shape + status codes + security chain |
| Cross-language | Integration | `CrossLangIntegrationIT.java` | JWT survives Java → Python boundary |

The domain tests need zero infrastructure — they're fast (~3-5 ms
each) and runnable from a clean checkout in one minute. The
infrastructure tests need Docker (Testcontainers boots
`postgres:16-alpine`), so they're slower but still under 10 seconds
per class.

Day 48-49 work raised `agentcook-api` jacoco line coverage to 92.3%
and branch to 74.3% across this layout — the protobuf-generated
classes (`cc.agentcook.grpc.*`) are excluded via the jacoco
configuration in the parent `pom.xml` because there's no meaningful
unit test for `ChatMetadata$Builder`.

---

## 7 · Tracing the dependency graph

If you want to convince yourself the arrows really only point one
way:

```bash
# domain should depend on nothing else in this module
mvn -pl agentcook-domain dependency:tree | grep "cc.agentcook"
# expected: only "cc.agentcook:agentcook-domain"

# application should depend only on domain
mvn -pl agentcook-application dependency:tree | grep "cc.agentcook"
# expected: cc.agentcook:agentcook-application + cc.agentcook:agentcook-domain

# infrastructure depends on domain
mvn -pl agentcook-infrastructure dependency:tree | grep "cc.agentcook"
# expected: + cc.agentcook:agentcook-domain (NOT application)

# api depends on application + infrastructure + domain (transitively)
mvn -pl agentcook-api dependency:tree | grep "cc.agentcook"
# expected: all four modules
```

If any of those grep outputs surprises you (e.g. domain depends on
infrastructure), the build will still compile but you've introduced
a cycle that future refactoring will fight. Fix it before merging.

---

## 8 · Related reading

- `agentcook-cc/docs/adr/ADR-013-java-business-backend.md` — the
  decision to add Java alongside Python and why
- `agentcook-cc/docs/api/CHANGELOG.md` — every additive change to
  the Java spec since 2026-05-31 freeze
- `agentcook-cc/docs/api/VERSIONING-POLICY.md` — when minor vs major
  vs patch bumps
- `agentcook-cc/docs/api/DEPRECATION-POLICY.md` — what to do when a
  field gets removed
- `agentcook/tutorial/chapters/03-from-user-story-to-architecture.md`
  — the chapter this module is the worked example for
