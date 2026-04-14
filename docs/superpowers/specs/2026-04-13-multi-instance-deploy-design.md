# Multi-Instance WeChat Deployment Design

## Goal

Support deploying multiple WeChat public-account instances on the same server while keeping each instance fully isolated in configuration, browser login state, ports, logs, and operator-facing scan/login instructions.

## Decision

Keep the current single-image runtime and add a multi-instance deployment layer around it.

Each public account will run as its own container instance with:

- a custom short name chosen by the operator,
- its own `config.py`,
- its own `.env`,
- its own browser profile volume,
- its own log directory,
- its own noVNC and VNC host ports,
- its own Bark title prefix for scan/login prompts.

The short name becomes the stable identity for operations. The runtime must never rely on one shared browser profile or one shared API config for multiple accounts.

## Scope

- Keep the existing single-instance Docker flow working.
- Add a multi-instance Docker Compose deployment path.
- Add instance template files so new accounts can be added consistently.
- Document how operators create, name, deploy, and scan-login each instance.
- Ensure port mapping can be customized per instance.

## Non-Goals

- No attempt in this change to route one running process between multiple accounts.
- No automatic generation of multiple compose services from a registry file.
- No implementation of runtime account switching inside Python business logic.
- No attempt to merge or share browser login state across accounts.

## Instance Model

Each instance is identified by a user-defined short name such as `foo`, `bar`, or a public-account shorthand.

Recommended directory layout:

```text
.
├─ docker-compose.yml
├─ docker-compose.multi.yml
├─ instances/
│  ├─ _template/
│  │  ├─ .env.example
│  │  └─ config.py.example
│  ├─ foo/
│  │  ├─ .env
│  │  ├─ config.py
│  │  └─ README.md
│  └─ bar/
│     ├─ .env
│     ├─ config.py
│     └─ README.md
└─ logs/
   ├─ foo/
   └─ bar/
```

The short name must flow through:

- compose service name,
- container name,
- instance directory name,
- log directory,
- browser profile volume name,
- Bark login/publish titles,
- operator-facing access table.

## Docker Architecture

### Image

Continue using one shared Docker image from the existing `Dockerfile`.

The image remains generic:

- no instance-specific config baked into the image,
- no per-account credentials copied into build context,
- runtime behavior still driven by mounted config and env files.

### Compose

Add a new `docker-compose.multi.yml` for multi-instance deployment.

Each instance becomes a separate service that mounts:

- `./instances/<slug>/config.py` to `/app/config/config.py`,
- `./logs/<slug>` to `/app/logs`,
- a dedicated named volume to `/data/wechat-profile`.

Each service also reads:

- `./instances/<slug>/.env`

Example shape:

```yaml
services:
  wechat-foo:
    container_name: wechat-publisher-foo
    image: wechat-ai-publisher:latest
    env_file:
      - ./instances/foo/.env
    volumes:
      - ./instances/foo/config.py:/app/config/config.py:ro
      - ./logs/foo:/app/logs
      - wechat-profile-foo:/data/wechat-profile
    ports:
      - "16080:6080"
      - "15900:5900"

  wechat-bar:
    container_name: wechat-publisher-bar
    image: wechat-ai-publisher:latest
    env_file:
      - ./instances/bar/.env
    volumes:
      - ./instances/bar/config.py:/app/config/config.py:ro
      - ./logs/bar:/app/logs
      - wechat-profile-bar:/data/wechat-profile
    ports:
      - "16081:6080"
      - "15901:5900"
```

## Environment Contract

Each instance `.env` should support at least:

```env
INSTANCE_SLUG=foo
INSTANCE_NAME=公众号A
VNC_PASSWORD=replace-with-a-strong-password
AUTO_OPEN_BROWSER=true
NOVNC_HOST_PORT=16080
VNC_HOST_PORT=15900
BARK_TITLE_PREFIX=[公众号A]
```

Definitions:

- `INSTANCE_SLUG`: machine-stable identifier used in naming and docs
- `INSTANCE_NAME`: operator-facing display name
- `NOVNC_HOST_PORT`: host port mapped to container `6080`
- `VNC_HOST_PORT`: host port mapped to container `5900`
- `BARK_TITLE_PREFIX`: title prefix so scan/login alerts show which account needs attention

## Scan/Login Identification

The operator must always be able to answer: "Which QR code belongs to which account?"

The design solves that by requiring four identifiers to align:

1. Bark title prefix, for example `[公众号A] 微信扫码登录`
2. noVNC URL, for example `http://server-ip:16080/vnc.html`
3. container name, for example `wechat-publisher-foo`
4. instance directory, for example `instances/foo/`

README should require operators to maintain or generate a simple mapping table:

```text
简称   显示名    noVNC端口  VNC端口  容器名
foo    公众号A   16080      15900    wechat-publisher-foo
bar    公众号B   16081      15901    wechat-publisher-bar
```

This avoids relying on the QR image alone to identify the target account.

## Deployment Workflow

### Add a New Account

1. Copy `instances/_template/` to `instances/<slug>/`
2. Fill `instances/<slug>/.env`
3. Fill `instances/<slug>/config.py`
4. Add one service to `docker-compose.multi.yml`
5. Ensure host ports are unique
6. Start only the target service or bring up the full stack

### First Login

1. Look up the short name and port in the mapping table
2. Open `http://<server-ip>:<NOVNC_HOST_PORT>/vnc.html`
3. Enter the instance-specific `VNC_PASSWORD`
4. Scan login in that instance's Chromium window
5. Close Chromium after login so the Playwright profile lock does not linger

### Ongoing Operation

- Logs stay under `logs/<slug>/`
- Browser state stays in the dedicated named volume
- Bark alerts identify the instance by title prefix
- Restarting one instance does not touch another instance's profile volume

## README Changes Required

README should gain a new multi-instance deployment section that covers:

- why each public account must be isolated,
- how to create a new instance from template,
- how to assign a short name,
- how to allocate ports,
- how to use `docker-compose.multi.yml`,
- how to know which QR code to scan,
- how to inspect a specific instance's logs and status.

README should keep the single-instance flow, but clearly label it as the simple path.

## Verification

Minimum verification for this change:

- tests asserting compose/examples support host-port overrides,
- tests asserting instance template files exist and document required fields,
- manual `docker compose -f docker-compose.multi.yml config` verification,
- manual smoke run for at least one instance using a non-default host noVNC port.
