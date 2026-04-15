# Single Account Deploy Parameters Design

## Goal

Keep the application codebase single-account only, while allowing multiple independent deployments on one server through Docker-layer configuration.

## Scope

- Keep one application config file: `config/config.py`
- Remove dependency on multi-instance code or `instances/<name>` layout
- Parameterize Docker deployment resources so multiple isolated single-account stacks can coexist
- Update release packaging and deployment docs to match the parameterized model

## Deployment Model

Each deployed account is an independent single-account stack with:

- its own compose project name
- its own container name
- its own image tag
- its own host noVNC / VNC ports
- its own persistent Chromium profile volume

The application still runs as one scheduler process inside one container and reads one `config/config.py`.

## Configuration Variables

Use `.env` to provide deployment identity and host-level resource isolation:

- `COMPOSE_PROJECT_NAME`
- `CONTAINER_NAME`
- `IMAGE_NAME`
- `HOST_NOVNC_PORT`
- `HOST_VNC_PORT`
- `WECHAT_PROFILE_VOLUME`
- `VNC_PASSWORD`
- `AUTO_OPEN_BROWSER`

Container-internal ports stay fixed at `6080` and `5900` to avoid changing container startup logic.

## File Changes

### `docker-compose.yml`

- Parameterize `container_name`
- Parameterize `image`
- Parameterize host-side port mappings
- Parameterize the named volume used for `/data/wechat-profile`

### `docker-compose.yml.example`

- Mirror the same parameterized compose template

### `.env.example`

- Document the new deployment variables with sensible defaults
- Keep runtime variables such as `VNC_PASSWORD` and `AUTO_OPEN_BROWSER`

### `build_release.bat`

- Read `IMAGE_NAME` from `.env`
- Save the built image tar using the resolved image tag
- Keep copying `.env`, `docker-compose.yml`, `config/config.py`, and `deploy_centos7.sh`

### `deploy_centos7.sh`

- Load variables from `.env`
- Respect parameterized `IMAGE_NAME` and `CONTAINER_NAME`
- Keep deployment flow as `down -> remove old named container if present -> remove old image -> load -> up -d`

### `README.md`

- Replace hard-coded deployment examples where needed
- Add recommended `.env` examples for account A / account B
- Clarify that multiple accounts are handled by multiple independent single-account deployments

## Testing Strategy

Add regression tests for the deployment templates and scripts:

- compose file references the new environment variables
- env example documents the new variables
- build script reads `IMAGE_NAME` from `.env`
- deploy script loads `.env` and honors configurable image / container names

## Risks

- Existing users relying on hard-coded names may need updated `.env`
- If `COMPOSE_PROJECT_NAME` is omitted, Docker Compose may derive a default project name; document that explicit configuration is recommended
- Multiple deployments on one host still require distinct host ports and volume names
