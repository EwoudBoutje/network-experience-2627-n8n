# Build-context: ansible-terraform-agent/ (zie n8n-vm/compose.yaml)
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-client \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "ansible-core>=2.17,<2.18" "fastmcp>=2.12,<3"

COPY ansible/requirements.yml /tmp/requirements.yml
RUN ansible-galaxy collection install -r /tmp/requirements.yml -p /usr/share/ansible/collections \
 && rm /tmp/requirements.yml

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin runner \
 && mkdir -p /opt/infra-agent/bin /var/lib/infra-agent/jobs /var/lib/infra-agent/logs \
 && chown -R runner:runner /var/lib/infra-agent

COPY n8n-vm/ansible-mcp/server.py /opt/infra-agent/bin/server.py

# Container draait read-only: alles wat Ansible/ssh schrijft gaat naar /tmp (tmpfs).
ENV ANSIBLE_CONFIG=/opt/infra-agent/ansible/ansible.cfg \
    ANSIBLE_HOME=/tmp/ansible-home \
    ANSIBLE_SSH_CONTROL_PATH_DIR=/tmp/ansible-home/cp \
    ANSIBLE_PERSISTENT_CONTROL_PATH_DIR=/tmp/ansible-home/pc \
    HOME=/tmp/home \
    PYTHONUNBUFFERED=1

USER 10001:10001
EXPOSE 8000
CMD ["python", "/opt/infra-agent/bin/server.py"]
