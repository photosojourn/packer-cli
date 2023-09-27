files = [
    {
        "location": "/config.yaml",
        "content": """
---
versioning:
  aws:
    source: 'github.com/hashicorp/amazon'
    version: 1.2.7
  azure:
    source: 'github.com/hashicorp/azure'
    version: 2.0.0
cloud: aws
region: us-east-1
ami_name: ami-name
ami_description: "Your AMI"
ami_tags:
    "customer:repo": packer-base-ami
instance_type: t2.small
subnet_id: your-subnet-id
associate_public_ip_address: "false"
custom_kms_key: "alias/your-packer-image-key"
ssm_connection:
  iam_instance_profile: "your-packer-build-instance"
copy_ami:
  regions: ["eu-west-1", "eu-west-2"]
regional_encryption: {
  "eu-west-1": "alias/your-packer-image-key",
}
sources:
  - os: al2
    ami_tags:
      Name: base-al2
    ssh_username: ec2-user
    source_ami: ami-234567dsfsfd1
provisioner:
  ansible:
    dir: base
""",
    },
    {
        "location": "/jinja/provider.j2",
        "content": """packer {
  required_plugins {
    {% for cloud_key, cloud_value in versioning.items() -%}
    {% if cloud_key == "azure" -%}
      azure = {
      {%- if cloud_value.version is not none %}
      version = "{{ cloud_value.version }}"
      {%- else %}
      version = "1.3.1"
      {%- endif %}
      source = "{{ cloud_value.source }}"
    }
    {%- elif cloud_key == "aws" -%}
      amazon = {
      {%- if cloud_value.version is not none %}
      version = "{{ cloud_value.version }}"
      {%- else %}
      version = "1.1.5"
      {%- endif %}
      source = "{{ cloud_value.source }}"
    }
  {%- endif %}
  {% endfor -%}
  }
}
""",
    },
    {
        "location": "/jinja/aws_source.j2",
        "content": """locals {
  {{ ami_name }}timestamp = regex_replace(timestamp(), "[- TZ:]", "")
}
{% for item in sources -%}
source "amazon-ebs" "{{ ami_name }}-{{ item.os }}" {
  ami_name      = "{{ ami_name }}-{{ item.os }}-${local.{{ ami_name }}timestamp}"
  {% if ami_description is defined -%}
  ami_description = "{{ ami_description }}"
  {% endif -%}
  instance_type = "{{ instance_type }}"
  region        = "{{ region }}"
  {% if item.ssh_username is defined -%}
  ssh_username = "{{ item.ssh_username }}"
  {% else -%}
  ssh_username = "ec2-user"
  {% endif -%}
  subnet_id = "{{ subnet_id }}"
  encrypt_boot = "true"
  {% if ssm_connection is defined -%}
  ssh_interface        = "session_manager"
  communicator         = "ssh"
  iam_instance_profile = "{{ ssm_connection.iam_instance_profile }}"
  {% elif local_connection is defined -%}
  security_group_id = "{{ local_connection.security_group_id }}"
  {% else -%}
  temporary_security_group_source_public_ip = true
  {% endif -%}
  {% if tags is defined -%}
  tags = {{ tags|tojson }}
  run_tags = {{ tags|tojson }}
  {% else -%}
  tags = {
    Name: "Packer Builder"
  }
  run_tags = {
    Name: "Packer Builder"
  }
  {% endif -%}
  {% if item.source_ami_filters is defined -%}
  source_ami_filter {
    filters = {
     virtualization-type = "hvm"
     architecture = "{{ item.source_ami_filters.architecture }}"
     root-device-type = "ebs"
     name = "{{ item.source_ami_filters.name }}"
    }
    most_recent = lower("{{ item.source_ami_filters.most_recent }}")
    owners      = ["{{ item.source_ami_filters.owners }}"]
  }
  {% elif item.source_ami is defined -%}
    source_ami    =  "{{ item.source_ami }}"
  {% endif -%}
  {% if sharing is defined-%}
    kms_key_id = "{{ sharing.kms_key }}"
    {% if sharing.account_id is defined -%}
    ami_users = ["{{ sharing.account_id }}"]
    {% endif -%}
    {% if sharing.org_arns is defined -%}
    ami_org_arns = ["{{ sharing.org_arns }}"]
    {% endif -%}
    {% if sharing.org_ou_arns is defined -%}
    ami_ou_arns = ["{{ sharing.org_ou_arns }}"]
    {% endif -%}
  {% endif -%}
}
{% endfor -%}
""",
    },
    {
        "location": "/jinja/build.j2",
        "content": """build {
  name    = "{{ ami_name }}{{ image_name}}"
  sources = [
    {% if cloud == "aws" -%}
      {% for item in sources -%}
    "source.amazon-ebs.{{ ami_name }}-{{ item.os }}" {% if not loop.last -%} , {% endif -%}
      {% endfor -%}
    {% elif cloud == "azure" -%}
      {% for item in images -%}
    "source.azure-arm.{{ image_name }}-{{ item.os }}" {% if not loop.last -%} , {% endif -%}
      {% endfor -%}
    {% endif %}
  ]

  {% if provisioner.ansible is defined -%}
# Run ansible bootstrap process
  provisioner "shell" {
    script       = "scripts/common-bootstrap-ansible.sh"
    pause_before = "10s"
    timeout      = "10s"
  }
  {% if provisioner.ansible.requirements is defined -%}
  {% if provisioner.ansible.requirements.artifacts is defined -%}
# Copy artifacts folder to /tmp
  provisioner "file" {
    source = "artifacts/{{ provisioner.ansible.dir }}/"
    destination = "/tmp"
  }
  {% endif -%}
  {% if provisioner.ansible.requirements.command is defined -%}
# Run specific command for requirements
  provisioner "shell" {
    inline = ["{{ provisioner.ansible.i.command }}"]
  }
  {% elif provisioner.ansible.requirements.script is defined -%}
# Run requirement script before ansible playbooks
  provisioner "shell" {
    script       = "scripts/{{ provisioner.ansible.requirements.script }}"
    pause_before = "10s"
    timeout      = "10s"
  }
  {% endif -%}
  {% endif -%}
# Now run all playbooks within directory.
  provisioner "ansible-local" {
    playbook_files = fileset(".", "ansible-playbooks/{{ provisioner.ansible.dir }}/*.yml")
  }

{% elif provisioner.shell is defined -%}
    {% if provisioner.shell.artifacts is defined -%}
# Copy artifacts folder to /tmp
  provisioner "file" {
    source = "artifacts/{{ provisioner.shell.dir }}/"
    destination = "/tmp"
  }
    {% endif -%}
# Run shell script
  provisioner "shell" {
    script       = "scripts/{{ provisioner.shell.dir }}/{{ provisioner.shell.script }}"
    pause_before = "10s"
    timeout      = "10s"
  }
{% endif -%}

{% if provisioner.update_os is defined -%}
# Run shell script to update the OS
  provisioner "shell" {
    script       = "scripts/common-update-os.sh"
    pause_before = "10s"
    timeout      = "10s"
  }
  {% endif -%}
{% if cloud == "azure" -%}
# Final azure provisioner to deregister the VM
  provisioner "shell" {
   execute_command = "chmod +x {{ '{{ .Path }}' }}; {{ '{{ .Vars }}' }} sudo -E sh '{{ '{{ .Path }}'}}'"
   inline = [
        "/usr/sbin/waagent -force -deprovision+user && export HISTSIZE=0 && sync"
   ]
   inline_shebang = "/bin/sh -x"
  }
{% endif -%}
}
""",
    },
    {
        "location": "/packer/scripts/common-bootstrap-ansible.sh",
        "content": """
#!/bin/sh
sudo amazon-linux-extras install python3
sudo python3 -m pip install --user pipx
sudo python3 -m pipx ensurepath
pipx install ansible-core
""",
    },
]
