BEGIN;

CREATE SCHEMA IF NOT EXISTS minecraft_whitelist
    AUTHORIZATION n8n_gebruiker;

SET LOCAL search_path TO minecraft_whitelist, public;

-- 1. Uitnodigingslinks
CREATE TABLE IF NOT EXISTS minecraft_whitelist.invites (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    token_hash          CHAR(64) NOT NULL UNIQUE,
    status              TEXT NOT NULL DEFAULT 'available'
                        CHECK (status IN (
                            'available', 'used', 'expired', 'revoked'
                        )),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ NOT NULL,
    used_at             TIMESTAMPTZ,
    revoked_at          TIMESTAMPTZ,
    created_by          TEXT,
    registration_id     BIGINT
);

CREATE INDEX IF NOT EXISTS idx_mw_invites_status_expiry
    ON minecraft_whitelist.invites (status, expires_at);

-- 2. Spelersregistraties
CREATE TABLE IF NOT EXISTS minecraft_whitelist.registrations (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    minecraft_username  TEXT NOT NULL
                        CHECK (
                            minecraft_username ~ '^[A-Za-z0-9_]{3,16}$'
                        ),
    real_name           TEXT NOT NULL
                        CHECK (
                            LENGTH(BTRIM(real_name)) BETWEEN 1 AND 150
                        ),
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN (
                            'pending',
                            'active',
                            'expired',
                            'removal_pending',
                            'remove_failed',
                            'add_failed'
                        )),
    invite_id           BIGINT UNIQUE
                        REFERENCES minecraft_whitelist.invites(id),
    registered_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at        TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ,
    removed_at          TIMESTAMPTZ,
    last_error          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        expires_at IS NULL
        OR activated_at IS NOT NULL
    )
);

-- Minecraft-usernames zijn niet hoofdlettergevoelig.
-- Een speler kan geen tweede actieve of nog af te handelen
-- registratie krijgen.
CREATE UNIQUE INDEX IF NOT EXISTS uq_mw_username_in_progress
    ON minecraft_whitelist.registrations (LOWER(minecraft_username))
    WHERE status IN (
        'pending', 'active', 'removal_pending', 'remove_failed'
    );

CREATE INDEX IF NOT EXISTS idx_mw_registrations_expiry
    ON minecraft_whitelist.registrations (expires_at)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_mw_registrations_status
    ON minecraft_whitelist.registrations (status);

-- 3. Log en wachtrij voor Pterodactyl-acties
CREATE TABLE IF NOT EXISTS minecraft_whitelist.operations (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    registration_id     BIGINT NOT NULL
                        REFERENCES minecraft_whitelist.registrations(id),
    action              TEXT NOT NULL
                        CHECK (action IN ('add', 'remove')),
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN (
                            'pending', 'running', 'succeeded', 'failed'
                        )),
    attempts            INTEGER NOT NULL DEFAULT 0
                        CHECK (attempts >= 0),
    next_attempt_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    last_error          TEXT,
    response_summary    TEXT
);

CREATE INDEX IF NOT EXISTS idx_mw_operations_pending
    ON minecraft_whitelist.operations (next_attempt_at, id)
    WHERE status IN ('pending', 'failed');

CREATE INDEX IF NOT EXISTS idx_mw_operations_registration
    ON minecraft_whitelist.operations (registration_id, created_at DESC);

-- Koppeling tussen uitnodiging en registratie.
ALTER TABLE minecraft_whitelist.invites
    ADD CONSTRAINT fk_mw_invite_registration
    FOREIGN KEY (registration_id)
    REFERENCES minecraft_whitelist.registrations(id);

COMMIT;
