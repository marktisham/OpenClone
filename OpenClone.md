# Setting Up OpenCode

This guide sets up OpenCode on a GCP VM with GitHub access via the GitHub MCP server. All GitHub operations (cloning, branching, PRs) are handled through a single Personal Access Token — no SSH keys required.

## Step 1: One-Time Setup (GCP Console + Credentials)

Complete these steps once. They apply to all VMs you create.

### 1.1 Enable Required GCP APIs

1. In the GCP Console, open the **Navigation Menu** (☰) and go to **APIs & Services > Library**
2. Search for and enable:
   - **Compute Engine API**
   - **Vertex AI API**

### 1.2 Gemini API Key

1. Go to [Google AI Studio](https://ai.google.dev/aistudio)
2. Sign in with your Google account
3. Click **Create API key**
4. Copy the key and save it somewhere secure

### 1.3 GitHub Personal Access Token

1. Go to [GitHub Fine-Grained Token Settings](https://github.com/settings/tokens?type=beta)
2. Click **Generate new token**
3. Give it a name (e.g. `opencode-vm-pat`)
4. Set **Expiration** as appropriate
5. Under **Repository access**, select **Only select repositories** and choose the repos OpenCode should have access to
6. Under **Permissions > Repository permissions**, set:
   - **Contents**: Read and write
   - **Pull requests**: Read and write
   - **Issues**: Read and write (optional, if you want OpenCode to manage issues)
7. Click **Generate token** and copy it immediately

### 1.4 Open the Firewall Port

The OpenCode web UI (Step 8) and HTTP server (Step 9) both listen on TCP port `4096`. Open it now in your VPC firewall so every VM you create later can be reached without revisiting this step.

1. Go to **VPC Network > Firewall** in the GCP Console
2. Click **Create Firewall Rule**
3. Configure:
   - **Name**: `opencode-web`
   - **Direction of traffic**: Ingress
   - **Targets**: All instances in the network
   - **Source IPv4 ranges**: `0.0.0.0/0`
   - **Protocols and ports**: TCP, port `4096`
4. Click **Create**

> ⚠️ **Demonstration only.** `0.0.0.0/0` opens the port to the entire internet, which is fine for a throwaway demo VM but **never** appropriate for production. For real workloads, restrict **Source IPv4 ranges** to your home/office IP (or a corporate VPN range), apply a target tag instead of "All instances in the network", and put authentication (e.g. `OPENCODE_SERVER_PASSWORD` plus an authenticated proxy) in front of the server.

## Step 2: Provision the VM (GCP Console)

### 2.1 Create the VM Instance

1. Go to **Compute Engine > VM Instances** and click **Create Instance**
2. Configure the instance:
   - **Name**: e.g. `opencode-gemini`
   - **Region/Zone**: choose one close to you (e.g. `us-central1-a`)
   - **Machine type**: `e2-standard-2` (2 vCPUs, 8 GB RAM)

### 2.2 Configure the Operating System

1. In the left sidebar, click **OS and storage**
2. Click **Change** under Operating System and Storage
3. Set the following:
   - **Operating system**: Ubuntu
   - **Version**: Ubuntu 26.04 LTS Minimal (x86/64)
   - **Type**: New balanced persistent disk
   - **Size**: `30` GB
4. Click **Select**

### 2.3 Configure Networking

Under **Networking > Firewall**, check both boxes:
- ✅ **Allow HTTP traffic**
- ✅ **Allow HTTPS traffic**

### 2.4 Create the Instance

Click **Create** and wait for the green checkmark to appear next to your VM. You may need to wait an additional 30-60 seconds for the initial boot-up to complete before connecting in the next step.

## Step 3: Prepare the VM Environment

SSH into your VM and install all required tools. This may take 1-2 minutes.

```bash
# Update system and install essential tools
sudo apt update
sudo apt install -y git curl nano

# Install Node.js 20.x from NodeSource (apt's default is too old for MCP servers)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install the OpenCode CLI globally
sudo npm install -g opencode-ai

# Verify installations (node should be 20.x)
node --version
opencode --version
git --version
```

## Step 4: Configure GitHub Access

### 4.1 Store the GitHub PAT for git Operations

On the VM, save your PAT to git's credential store so all `git` commands authenticate automatically over HTTPS:

```bash
git config --global credential.helper store
cat > ~/.git-credentials << 'EOF'
https://<your-username>:<your-pat>@github.com
EOF
chmod 600 ~/.git-credentials
```

Replace `<your-username>` and `<your-pat>` with your GitHub username and the PAT from Step 1.2.

### 4.2 Configure Git Identity

```bash
git config --global user.name "opencode-bot"
git config --global user.email "<your-github-email>"
```

The name can be anything; the email must match a verified email on your GitHub account so commits link to it.

### 4.3 Clone a Test Repository

Get the HTTPS clone URL from GitHub (green **Code** button > **HTTPS** tab) and clone it:

```bash
git clone <url>
cd <your-repo>
```

## Step 5: Configure OpenCode with Gemini and GitHub MCP

### 5.1 Connect OpenCode to Gemini

Start OpenCode:

```bash
opencode
```

In the terminal UI, run:

```
/connect
```

Select **Google** as the provider, paste your Gemini API key, and choose your model (e.g. **Gemini 2.5 Flash**). Accept the defaults.

Verify with:

```
What model are you?
```

Exit out of OpenCode `Ctrl+C`


### 5.2 Add the GitHub MCP Server

The MCP config is stored **per project** in `opencode.json` at the repo root. This ensures the GitHub tools are available whether you run OpenCode from the terminal or the web UI. A global config at `~/.config/opencode/opencode.json` is not used here because the web UI does not reliably pick it up.

Create the config file in the project's `.opencode` directory:

```bash
cd ~/<your-repo>
mkdir -p .opencode
nano .opencode/opencode.json
```

Paste the following:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "github": {
      "type": "local",
      "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
      "enabled": true,
      "environment": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "<your-pat>"
      }
    }
  }
}
```

Replace `<your-pat>` with the token from Step 1.2. Save and exit with `Ctrl+O`, `Enter`, `Ctrl+X`.

The `"enabled": true` flag is required — without it OpenCode will not start the server.

### 5.3 Verify the MCP Connection

Restart OpenCode from inside the repo directory:

```bash
cd ~/<your-repo>
opencode
```

In the OpenCode UI, check that the MCP server is loaded by looking for `github` in the tools/MCP list (command varies by version — try `/mcp` or `/tools`). You should see GitHub tool names like `list_pull_requests`, `create_pull_request`, etc.

Then ask, being explicit about using the MCP tool:

```
Use the github MCP tool to list the open pull requests for <your-username>/<your-repo>.
```

The model will default to bash tools if not told otherwise. We'll fix this in the next step.

## Step 6: Configure the AGENTS.md File

OpenCode reads an `AGENTS.md` file from the repo root on startup and uses it as project-level system instructions — analogous to `CLAUDE.md` for Claude Code. This is where you encode standing rules the model should follow on every prompt.

### 6.1 Generate a Baseline AGENTS.md with `/init`

From inside your repo, start OpenCode and run the built-in `/init` command. It scans the codebase and writes a tailored `AGENTS.md` describing the project's structure, conventions, and how to work in it:

In the OpenCode UI:

```
/init
```

Wait for it to finish, then exit OpenCode (`Ctrl+C` or `/exit`).

### 6.2 Add GitHub and Branching Rules

Open the generated file and append the rules OpenCode wouldn't infer from the code alone — how to use the GitHub MCP tool, branch naming, commit style:

```bash
nano AGENTS.md
```

Append the following to the end of the file:

```markdown
## Autonomy
- These agents are designed to run autonomously without a human in the loop. Do not ask follow-up or clarifying questions.
- When requirements are ambiguous, reason through the trade-offs, pick the most reasonable interpretation, and proceed. Document the assumption in the PR description.
- Always finish the task end-to-end: implement the change, commit, push, and open a PR. Do not stop partway and wait for confirmation.

## GitHub Operations
- Always use the `github` MCP tool for pull request and issue operations. Do not fall back to `gh` or `curl` unless explicitly asked.
- Use Conventional Commit prefixes (`feat:`, `fix:`, `chore:`, etc.) in commit messages and PR titles.

## Branching
- Create a new branch when starting a new piece of work. Never commit directly to `main`.
- If a branch already exists for the current task (e.g. follow-up prompts refining an in-progress change or PR), keep committing to that branch instead of creating a new one.
- Branch names: `<type>/<short-description>` (e.g. `feat/add-login`, `fix/null-pointer`).

## Pull Requests
- Write a clear PR title that summarizes the change in one line (under ~70 characters).
- The PR body should include:
  - **Summary**: 1–3 bullets describing what changed and why.
  - **Test plan**: a checklist of how the change was (or should be) verified.
- Reference any related issues with `Closes #<number>` when applicable.
- Do not paste raw diffs or full file contents into the description — link to the changed files instead.
```

Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`). Commit `AGENTS.md` to the repo so every clone (and the cloned VM image) picks it up automatically.

OpenCode loads `AGENTS.md` whenever a session is started inside the repo directory — both for the terminal UI and the HTTP server in Step 9.

## Step 7: Test End-to-End (Branch + PR via OpenCode)

Re-enter the OpenCode TUI:

```bash
cd ~/<your-repo>
opencode
```

Send this prompt:

```
Add a file vm-access-test.txt with "vm access test" and open a PR.
```

OpenCode should create a new branch, add the file, commit with a Conventional Commit message, push, and open a pull request via the github MCP tool. The final response should include the PR URL.

## Step 8: Access OpenCode via the Web UI

> **Optional.** This step sets up the OpenCode web UI for interactive use and is useful for verifying remote connectivity from your laptop. If you're focused on automated orchestration via the HTTP API, skip ahead to Step 9.
>
> ⚠️ **No security is in place.** The web UI has no authentication and the firewall rule below only restricts by source IP. Do **not** open it to `0.0.0.0/0` on a real workload — anyone who can reach the port can drive OpenCode against your repo and credentials.

### 8.1 Start the Web Server

Always start the web server from inside the project directory so it picks up the project-level `opencode.json` (which contains the MCP config):

```bash
cd ~/<your-repo>
opencode web --hostname 0.0.0.0
```

Note the port number (e.g. `4096`) from the printed URL. Leave the terminal open.

### 8.2 Find the VM's External IP

1. Go to **Compute Engine > VM Instances**
2. Copy the **External IP** of your instance

### 8.3 Open the Web UI

Navigate to `http://<EXTERNAL_IP>:<PORT>` in your browser (e.g. `http://34.123.45.67:4096`).

Once loaded, verify the GitHub MCP tools are working by asking:

```
list open PRs
```

You should see a list of PRs returned. If the model falls back to bash, the MCP server didn't load — check that you started the web server with `GITHUB_PERSONAL_ACCESS_TOKEN` set in the environment.

## Step 9: Drive OpenCode via the HTTP Server

In addition to the terminal UI and web UI, OpenCode exposes an HTTP API you can use to script prompts against the instance. This is useful for automating code changes from another machine or CI system.

See the [official server docs](https://opencode.ai/docs/server/) for the full API reference.

> ⚠️ **No security is in place.** The HTTP server has no authentication by default — `OPENCODE_SERVER_PASSWORD` is unset and the server logs `server is unsecured` on startup. Access is only gated by the firewall rule from Step 1.4. Do **not** expose the API to `0.0.0.0/0` or any untrusted network. For real workloads, set `OPENCODE_SERVER_PASSWORD` and put the server behind a proper authenticated proxy.

### 9.1 Start the HTTP Server

From inside your project directory (so the project-level `opencode.json` and MCP config are picked up):

```bash
cd ~/<your-repo>
opencode serve --port 4096 --hostname 0.0.0.0
```

Use `0.0.0.0` if you want to hit the API from your laptop over the VM's external IP (make sure the firewall rule from Step 1.4 covers port `4096`). For local-only access, use `127.0.0.1`.

The server exposes an OpenAPI 3.1 spec at `http://<host>:4096/doc`.

### 9.2 Create a Session

A session is the context in which prompts are sent. Create one and capture its ID:

```bash
curl -X POST http://<EXTERNAL_IP>:4096/session \
  -H "Content-Type: application/json" \
  -d '{"title": "api-driven-change"}'
```

The response is a `Session` object — note its `id` field for the next step.

### 9.3 Stream Events and Send a Prompt

To watch reasoning, message parts, and tool calls as they happen, open the server's Server-Sent Events stream **before** posting your prompt.

In one terminal, open the SSE stream filtered to just the model's reasoning and visible replies — tool calls, file edits, and diff events are dropped so you get a clean running narrative:

```bash
curl -N http://<EXTERNAL_IP>:4096/event \
  | grep --line-buffered '^data:' \
  | sed -u 's/^data: //' \
  | jq --unbuffered -r '
      select(.properties.part.type == "reasoning" or .properties.part.type == "text")
      | .properties.part.text // .properties.part.thinking // empty
    '
```

The `-N` flag disables curl's output buffering so events print as they arrive. Drop the `or .properties.part.type == "text"` clause if you want pure reasoning only, or remove the `jq` filter entirely (`| jq .`) to see every event — useful if your opencode version uses a different field path (e.g. `.part.type` instead of `.properties.part.type`) and you need to adjust the selector.

In a second terminal, POST a prompt to the session from Step 9.2:

```bash
curl -X POST http://<EXTERNAL_IP>:4096/session/<SESSION_ID>/message \
  -H "Content-Type: application/json" \
  -d '{
    "parts": [{"type": "text", "text": "Add a title to the calculator that says \"hello from opencode\". Commit the change on a new branch and open a PR using the github MCP tool."}]
  }'
```

OpenCode will execute the prompt against the working directory just like it would in the UI — editing files, running git, and calling MCP tools — and you'll see the model's reasoning appear in the SSE stream in real time. The synchronous POST also returns the final message when the run completes.

## Step 10: Auto-Start the HTTP Server on Boot

Before snapshotting the VM, bake the Step 9.1 server startup into a systemd service so every cloned instance comes up with the API already listening.

First, find your Linux username and project directory — you'll plug these into the unit file below:

```bash
whoami
# e.g. mtisham — this is <USER>

ls ~
# pick your project directory — this is <your-repo>
```

Create a systemd unit (replace `<USER>` with the `whoami` output and `<your-repo>` with your project directory name — no angle brackets in the final file):

```bash
sudo tee /etc/systemd/system/opencode-serve.service > /dev/null <<'EOF'
[Unit]
Description=OpenCode HTTP Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<USER>
WorkingDirectory=/home/<USER>/<your-repo>
ExecStart=/usr/bin/opencode serve --port 4096 --hostname 0.0.0.0
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

> **Note:** The service will need access to any secrets referenced by your `opencode.json` or MCP config (e.g. the `GITHUB_PERSONAL_ACCESS_TOKEN` from Step 8.2). How you provision those into the service environment is out of scope here — pick whatever secret-management approach fits your setup (systemd `EnvironmentFile`, a cloud secret manager, etc.) and avoid baking plaintext secrets into the machine image.

Confirm the `opencode` binary path matches `ExecStart`.

```bash
which opencode
# expected: /usr/bin/opencode
```

If it points somewhere else (e.g. `/usr/local/bin/opencode` from a manual install, or `~/.local/bin/opencode` from a user-level install), update the `ExecStart=` line in the unit to match the path you see.

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now opencode-serve
sudo systemctl status opencode-serve --no-pager
```

Tail the logs to verify it's serving on port `4096`:

```bash
journalctl -u opencode-serve -f
```

Once the service is healthy, proceed to create the machine image — the service is enabled, so every cloned VM will start `opencode serve` automatically on boot.

## Step 11: Cloning Worker Instances

Once your VM is fully configured, you can snapshot it as a machine image and spin up additional instances without repeating the setup.

### 11.1 Create a Machine Image

1. Go to **Compute Engine > VM Instances**
2. Click the triple-dot menu (⋮) next to your configured VM instance
3. Select **Create new machine instance**
4. Give it a descriptive name, e.g. `opencode-baseline`

### 11.2 Provision a New Instance from the Image

1. Go to **Compute Engine > VM Instances** and click **Create Instance**
2. Select **Create VM from...** and choose the **Machine Images** option
3. Select the image you just created (`opencode-baseline`)
4. Optionally select **Customize** to change the instance name, for example `opencode-1`, `opencode-2`, etc.
4. Click **Create**

Repeat as needed to spin up additional worker instances.

## Step 12: Test Multiple Workers in Parallel with the Reasoning Tester

Once you have multiple cloned VMs running from the machine image in Step 11, you can drive each one in parallel from your laptop using the `reasoning-tester/` web tool in this repo. It calls the `/session` and `/event` endpoints from Step 9.2 / 9.3 and streams reasoning events to a browser tab.

### 12.1 Clone One or More Worker Instances

Follow Step 11.2 to provision additional VMs from the `opencode-baseline` machine image. Each instance comes up with `opencode-serve` already running on port `4096` (thanks to the systemd unit from Step 10).

For each new instance, grab its **External IP** from **Compute Engine > VM Instances**.

### 12.2 Launch the Reasoning Tester

Open this repo in VS Code, then in the **Run & Debug** panel select **Reasoning Tester (Flask)** and press **F5**. VS Code starts the Flask app and opens `http://127.0.0.1:5055` in your default browser.

If this is your first run, install dependencies into the venv:

```bash
cd reasoning-tester
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 12.3 Drive Multiple Workers Simultaneously

1. Copy `http://127.0.0.1:5055` into a separate browser tab (or window) for each worker VM you want to test.
2. In each tab, paste a different VM's external IP into the **External IP** field.
3. Enter a prompt for each tab — different prompts per tab let you test independent tasks in parallel.
4. Click **Send** in each tab. Each tab opens its own session and SSE stream against its target VM, so reasoning events from all workers stream in concurrently.

The session ID rendered under the curl command is reused for follow-up prompts in the same tab, so you can iterate against the same session per worker without losing context.
