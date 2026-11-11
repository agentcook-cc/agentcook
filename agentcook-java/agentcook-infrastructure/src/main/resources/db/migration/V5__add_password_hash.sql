-- V5: password authentication.
--   password_hash — opaque hash produced by the application's PasswordHasher
--                   port (BCrypt today, ~60 chars; 255 leaves room for a
--                   future algorithm prefix / format without another ALTER).
--                   NULL means "no password set": rows created before this
--                   migration (V2 seed admin, users auto-provisioned by the
--                   old any-password dev login, admin-created users) keep
--                   NULL until they register / claim the account.
ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) DEFAULT NULL;
