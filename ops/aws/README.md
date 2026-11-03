# AWS EC2 deployment (GitHub Actions + SSM)

This adds an AWS deployment path to the existing production Compose setup. It does **not** provision AWS resources, merge itself into `main`, or deploy until you configure AWS and merge this PR.

## Important cost / capacity note

A sustained **₹500/month** EC2 production budget is not realistic for this repository's current stack with WebJS/Chromium and self-hosted Prometheus + Grafana. At minimum, the low-cost trial baseline is a `t4g.micro` (1 GiB RAM), 10–20 GiB gp3, and a public IPv4 address. The public IPv4 charge alone is billed hourly. Actual monthly cost varies by region, usage, tax, data transfer, and storage.

- **Trial / CI smoke test:** `t4g.micro`, 10 GiB gp3, Ubuntu 24.04 ARM64. Expect memory pressure; WebJS may crash/OOM. Not production-approved.
- **More realistic starting point:** `t4g.small` (2 GiB) for app-only, but still tight with Chromium and monitoring.
- **App + Prometheus/Grafana:** plan for at least 4 GiB RAM (`t4g.medium`) and adequate EBS capacity. Re-check AWS pricing before launch.
- Self-hosted monitoring is included as a separate Compose overlay. Do not enable it on the 1 GiB trial host.
- For strict ₹500, keep monitoring in GitHub/AWS free/credit-backed services or use a non-AWS host; don't claim full EC2 production is within that budget.

## AWS configuration

Recommended region for India latency: `ap-south-1` (Mumbai).

### EC2

| Setting | Value |
|---|---|
| AMI | Ubuntu Server 24.04 LTS, ARM64 |
| Instance type | `t4g.small` app-only minimum; `t4g.medium` for app + monitoring (budget overrun) |
| Root EBS | gp3, 20 GiB recommended; encrypted |
| IMDS | IMDSv2 required; hop limit 1 |
| Public IP | Needed for simplest outbound internet access; AWS charges for public IPv4. Cloudflare Tunnel does not remove this charge if IPv4 remains assigned. |
| IAM instance profile | SSM managed instance core only (`AmazonSSMManagedInstanceCore`) |
| User data | Run `ops/aws/bootstrap.sh` as root |
| SSH | Do not open port 22; use Systems Manager Session Manager |

For a test-only micro instance, 10 GiB is a lower-cost disk but Docker image builds and database growth can fill it quickly. Monitor `df -h`.

### Security group

- Inbound: **no rules** when administering with SSM and fronting the app through Cloudflare Tunnel.
- Outbound: allow HTTPS (443) and DNS to required AWS/GitHub/Docker/Cloudflare endpoints. The default outbound-all rule is simpler but less restrictive; narrow it only after validating endpoint needs.
- If instead using Caddy with direct public DNS/HTTPS, inbound TCP 80 and 443 are needed; never expose PostgreSQL 5432 or backend 8000.
- With no public IPv4, SSM and outbound internet require IPv6-compatible endpoint routing or VPC endpoints; VPC endpoints/NAT can cost more than this budget. Do not remove the public IP without a tested egress/SSM path.

### Instance role

Attach `AmazonSSMManagedInstanceCore` to the EC2 instance role. Do not put AWS access keys on the server.

### GitHub OIDC deployment role

Create an IAM role trusted by GitHub OIDC:

- OIDC provider: `token.actions.githubusercontent.com`
- Audience: `sts.amazonaws.com`
- Subject: `repo:vardhan1609/gmail-reminder:environment:production` if the job uses GitHub Environment `production`.
- Add branch restriction via GitHub Environment protection (only `main`) and required reviewers if available.

Suggested trust policy (replace account-specific provider ARN as needed):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": "repo:vardhan1609/gmail-reminder:environment:production"
      }
    }
  }]
}
```

Give this role only:
- `ssm:SendCommand` on the EC2 instance ARN and `arn:aws:ssm:REGION::document/AWS-RunShellScript`
- `ssm:GetCommandInvocation`, `ssm:ListCommandInvocations` (resource scoping varies for these SSM actions; use the narrowest supported resource ARN).

Do not grant `ec2:*`, `iam:*`, or administrator access.

## GitHub repository configuration

After merging this deployment PR, create GitHub Environment **production**, restrict deployments to `main`, and add:

Environment secret:
- `AWS_DEPLOY_ROLE_ARN`: IAM role ARN for the OIDC deployment role.

Environment variables:
- `AWS_REGION`: `ap-south-1`
- `EC2_INSTANCE_ID`: the EC2 instance ID, e.g. `i-...`

No static AWS access keys are needed. The workflow triggers after the existing **CI/CD Pipeline** succeeds on a push to `main`; it skips PR runs.

## Bootstrap the instance

1. Launch the EC2 configuration above with the instance profile and security group.
2. Connect through **Systems Manager Session Manager**, not SSH.
3. Copy/run the bootstrap script from the repository checkout:
   ```bash
   sudo bash ops/aws/bootstrap.sh
   ```
   Alternatively put the script contents in EC2 user-data.
4. Create `/opt/gmail-reminder/.env.production` using the repository's `.env.production.example` and your actual production secrets/domains. Set restrictive permissions:
   ```bash
   sudo chown root:root /opt/gmail-reminder/.env.production
   sudo chmod 600 /opt/gmail-reminder/.env.production
   ```
5. Set `APP_DOMAIN`, `API_DOMAIN`, database credentials, `SECRET_KEY`, `API_KEY`, encryption key, Google OAuth callback URLs, SMTP credentials, and WhatsApp provider to `webjs`. Never commit the env file.
6. Configure DNS to the EC2 public IPv4 for direct Caddy HTTPS. For Cloudflare Tunnel, create the tunnel and route app/API hostnames to the frontend/backend containers; do not expose ports 80/443 on the security group. Keep the tunnel token in a secret env file, not Git.
7. Test the initial deploy manually from SSM:
   ```bash
   sudo /usr/local/bin/gmail-reminder-deploy
   ```

**Important:** WebJS persists its WhatsApp session in the existing `whatsapp_session` Compose volume. Do not delete volumes or run `docker compose down -v`.

## GitHub Actions deployment behavior

`.github/workflows/deploy-ec2.yml`:
1. Waits for the existing CI workflow to pass on `main`.
2. Assumes the AWS deployment role with GitHub OIDC.
3. Uses SSM Run Command to invoke `/usr/local/bin/gmail-reminder-deploy`.
4. Polls command status and fails the workflow if SSM reports failure.

The deployment script fetches `origin/main`, runs database migrations, rebuilds/restarts the Compose services, and prunes unused image/build cache. It does not delete named volumes.

## Self-hosted monitoring (separate overlay)

Files in `ops/monitoring` provide Prometheus, Grafana, node-exporter, and cAdvisor. Start them only on a host with enough RAM and disk:

```bash
cd /opt/gmail-reminder
docker compose --env-file .env.production \
  -f docker-compose.prod.yml \
  -f ops/monitoring/docker-compose.monitoring.yml \
  up -d
```

Set `GRAFANA_ADMIN_PASSWORD` in `.env.production` to a unique password. Prometheus retention is capped at 7 days / 512 MiB. Prometheus and Grafana have no host-published ports; use SSM port forwarding or add a Cloudflare Tunnel route protected by Cloudflare Access. Never publish Grafana (3000) or Prometheus (9090) directly to the internet.

Monitor EC2 CPU credits, RAM, disk, Docker container restarts, PostgreSQL volume size, and backup age. Configure AWS Budget alerts (for example at USD $5 and $10) and billing alerts; budget alerts are not hard spending caps.

## Operational checklist

- [ ] DNS and HTTPS tested
- [ ] Google OAuth redirect URIs updated to production
- [ ] CORS allowlist is production-only
- [ ] Secure cookies / encryption key set
- [ ] SSM works and no SSH inbound rule exists
- [ ] CI passes before production workflow runs
- [ ] Health check, login, Gmail OAuth, reminders, Telegram/WhatsApp verified
- [ ] WhatsApp WebJS session persisted after restart
- [ ] Encrypted database backup copied off-instance and restore tested
- [ ] CloudWatch billing alarm / AWS Budget configured
- [ ] Monitoring is not enabled on a RAM-starved instance

This is a deployment starter, not a production security certification. Review the application security fixes and test the complete workflow before serving real users.
