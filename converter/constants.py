#Attempt to match all common interface types, in shorthand or full notation
ALL_INTERFACE_FLAVORS_REGEX = (
    r"\b(?:Gi(gabitEthernet)|Eth(ernet)|Vl(an)|Fa(stEthernet)|Se(rial)|Te(nGigabitEthernet)|Twe(GigabitEthernet)|Po(rtChannel))\d+(?:\/\d+)*(?:\/\d+)?\b"
)

#Appended to start of config to add our admin:admin
AAA_COMMANDS = """
aaa new-model
aaa authentication login default local
aaa authentication enable default none
username admin privilege 15 secret admin
"""

#Appended to start of config to automatically no shut GigabitEthernet1 on boot
INT_AUTO_NOSHUT = """
event manager applet on-boot
event timer countdown time 15
action 1.0 cli command "enable"
action 1.1 cli command "configure terminal"
action 1.2 cli command "interface gigabitethernet1"
action 1.3 cli command "no shut"
action 1.4 cli command "exit"
"""

#Any line found with these values will be automatically removed from the config
BAD_WORDS = ["aaa", "username"]

#Skeleteon that we will use to create our .tfvars.json data
TFVARS_SKELETON = {
    "nodes": []
}

#This is the main.tf file that will be added to the output path
TF_FILE = """
terraform {
  required_providers {
    cml2 = {
      source  = "CiscoDevNet/cml2"
      version = "0.6.2"
    }
  }
}

variable "nodes" {
  type        = list(any)
  description = "map of node details inherit from tfvars file"
}

variable "cml_username" {
  type        = string
  description = "Username for your CML Instance"
}

variable "cml_password" {
  type        = string
  description = "password for your CML Instance"
}

variable "cml_url" {
  type        = string
  description = "path to your cml node ex: https://192.168.1.247"
}

variable "cml_lab_name" {
  type        = string
  description = "Name of the lab we will create in CML"
}

provider "cml2" {
  address     = var.cml_url
  username    = var.cml_username
  password    = var.cml_password
  skip_verify = true
}

resource "cml2_lab" "staged_lab" {
  description = "Lab created by Terraform"
  title       = var.cml_lab_name
  notes       = "Created by Terraform"
}

resource "cml2_node" "bridge" {
  # Create the bridge network we will connect all nodes on
  lab_id         = cml2_lab.staged_lab.id
  label          = "Bridge"
  nodedefinition = "unmanaged_switch"
  #Set CPU Limit to bypass CML provider bug (still occurs occasionally..)
  cpu_limit = null
  x         = "750"
  y         = "450"
}

resource "cml2_node" "csrv_routers" {
  # Loop over all nodes in our tfvars file and create it's instance
  for_each       = { for idx, node in var.nodes : idx => node }
  lab_id         = cml2_lab.staged_lab.id
  label          = each.value.label
  nodedefinition = each.value.nodedefinition
  x              = each.value.x
  y              = each.value.y
  # Provider bugs caused by not removing \\r explicitly, so using replace() for that
  configuration = replace(file("${each.value.config_file}"), "\\r\\n", "\\n")
}

resource "cml2_link" "gig_links" {
  # Create all the G1 links to the bridge
  for_each = cml2_node.csrv_routers
  lab_id   = cml2_lab.staged_lab.id
  node_a   = each.value.id
  node_b   = cml2_node.bridge.id
  # Slot 0 == GigabitEthernet1
  slot_a = 0
}

resource "cml2_lifecycle" "start_nodes" {
  # Start all the nodes, this will run until the nodes are completely up
  lab_id   = cml2_lab.staged_lab.id
  elements = [for router in cml2_node.csrv_routers : router.id]
  state    = "STARTED"
  #CML tries to start nodes before all links are added, using depends_on to correct the behavior
  depends_on = [cml2_link.gig_links, cml2_node.csrv_routers]
}

output "outs" {
  value = cml2_lab.staged_lab.id
}
"""