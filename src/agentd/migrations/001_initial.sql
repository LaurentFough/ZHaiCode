--= Phase 0/1 operational authority. No task deletion or generation reset operation.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version integer PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS projects (
    project_id text PRIMARY KEY,
    payload jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS machines (
    machine_id text PRIMARY KEY,
    payload jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS agents (
    agent_id text PRIMARY KEY,
    machine_id text NOT NULL REFERENCES machines(machine_id),
    payload jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    task_id text PRIMARY KEY,
    project_id text NOT NULL REFERENCES projects(project_id),
    generation bigint NOT NULL DEFAULT 0 CHECK (generation >= 0),
    payload jsonb NOT NULL,
    CHECK ((payload->>'generation')::bigint = generation),
    CHECK (payload->>'task_id' = task_id),
    CHECK (payload->>'project_id' = project_id)
);
CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id text PRIMARY KEY,
    task_id text NOT NULL REFERENCES tasks(task_id),
    generation bigint NOT NULL CHECK (generation > 0),
    payload jsonb NOT NULL,
    handoff jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id text NOT NULL REFERENCES tasks(task_id),
    generation bigint NOT NULL,
    kind text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO schema_migrations(version) VALUES (1) ON CONFLICT DO NOTHING;
