# Gitea Actions runners (workers)

Instructions to run Gitea Act Runner on **campusrose-staging** and on a **Raspberry Pi with Docker**. Fill in the placeholders before running.

## Prerequisites

1. **Gitea URL** – `https://git.ncdlabs.com`
2. **Runner token** – In Gitea: **Site administration → Actions → Runners** → “Register a new runner” and copy the registration token.
3. **Network** – Both hosts must reach the Gitea server (and Gitea must reach the runner callback URL if behind NAT; see Gitea docs).

Set these once (replace with your values):

```bash
export GITEA_URL="https://git.ncdlabs.com"
export RUNNER_TOKEN="yVpxFOJzEjKjvPHaqU9q9Zix95L4sioS6XTtS3ix"
```

---

## 1. campusrose-staging

SSH to the server, then use either **native** or **Podman**.

### Option A: Native act_runner (no containers)

```bash
# Install (Linux example; adjust for your OS)
# See https://gitea.com/gitea/act_runner/releases
curl -sL https://dl.gitea.com/act_runner/act_runner-linux-amd64 -o act_runner
chmod +x act_runner
sudo mv act_runner /usr/local/bin/

# Run (interactive registration first time)
act_runner register --instance "$GITEA_URL" --token "$RUNNER_TOKEN"

# Run worker (foreground; use systemd/screen/tmux for production)
act_runner daemon
```

### Option B: Podman on campusrose-staging

```bash
# One-time registration (creates config in ./config)
podman run --rm -v ./config:/config gitea/act_runner:latest \
  register --instance "$GITEA_URL" --token "$RUNNER_TOKEN"

# Run worker (daemon)
podman run -d --name gitea-runner \
  -v ./config:/config \
  -v /var/run/docker.sock:/var/run/docker.sock \
  gitea/act_runner:latest daemon
```

If you use Podman’s socket instead of Docker’s, bind that socket in the second command (e.g. `-v /run/podman/podman.sock:/var/run/docker.sock`).

---

## 2. Raspberry Pi (Docker)

SSH to the RPI that has Docker. Use the same `GITEA_URL` and `RUNNER_TOKEN`.

### One-time registration

```bash
mkdir -p ./gitea-runner-config
docker run --rm -v "$(pwd)/gitea-runner-config:/config" gitea/act_runner:latest \
  register --instance "$GITEA_URL" --token "$RUNNER_TOKEN"
```

### Run worker (daemon)

```bash
docker run -d --name gitea-runner --restart unless-stopped \
  -v "$(pwd)/gitea-runner-config:/config" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  gitea/act_runner:latest daemon
```

Jobs that need Docker (e.g. “run in container”) will use the host’s Docker. Restart policy keeps the runner up across reboots.

---

## Quick reference

| Host                 | Registration (once)        | Daemon (worker)                    |
|----------------------|----------------------------|------------------------------------|
| campusrose-staging   | `act_runner register ...` or podman `register` | `act_runner daemon` or podman `daemon` |
| RPI (Docker)         | docker `register` + volume | docker `daemon` + volume + `--restart unless-stopped` |

After both are running, new Gitea Actions workflows will be able to use these runners.
