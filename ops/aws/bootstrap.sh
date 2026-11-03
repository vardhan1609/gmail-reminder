#!/usr/bin/env bash
# Ubuntu 24.04 LTS ARM64 EC2 bootstrap. Run as root via EC2 user-data or SSM.
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo/root." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git docker.io docker-compose-v2 awscli
systemctl enable --now docker

# Ubuntu AWS images normally ship with SSM Agent. Enable whichever unit exists.
systemctl enable --now snap.amazon-ssm-agent.amazon-ssm-agent.service 2>/dev/null || \
  systemctl enable --now amazon-ssm-agent 2>/dev/null || true

# Optional emergency swap for Docker build peaks on low-memory test instances.
# Swap does NOT make a 1 GB EC2 instance production-safe.
if ! swapon --show | grep -q /swapfile; then
  if [[ ! -f /swapfile ]]; then
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
  fi
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

install -d -m 0750 /opt
if [[ ! -d /opt/gmail-reminder/.git ]]; then
  git clone --branch main --depth 1 https://github.com/vardhan1609/gmail-reminder.git /opt/gmail-reminder
fi

install -m 0750 /opt/gmail-reminder/ops/aws/deploy.sh /usr/local/bin/gmail-reminder-deploy
install -d -m 0750 /opt/gmail-reminder
echo "Bootstrap complete. Create /opt/gmail-reminder/.env.production before deployment."
