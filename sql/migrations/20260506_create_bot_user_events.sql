CREATE TABLE IF NOT EXISTS bot_user_events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    telegram_id BIGINT,
    event_name TEXT NOT NULL,
    subscription_id BIGINT REFERENCES subscriptions(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bot_user_events_created_at
    ON bot_user_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_bot_user_events_event_created
    ON bot_user_events (event_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_bot_user_events_user_created
    ON bot_user_events (user_id, created_at DESC);
