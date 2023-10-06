# prod_to_cml
The goal of this script is to take production Cisco IOS/IOSXE configurations and have them deployed in a CML lab as CSR1000vs in minutes with Terraform. This repo could also be used for the early stages of a CI/CD pipeline or education. 


prod_to_cml attempts to solve these shortcomings I've found with labbing production network conigurations
- Interface IDs rarely ever match (Virtual appliances use different interface schemes completely)
- Virtual appliances only support a max of 26 interfaces. Meaning you could have devices in your topology that simply have too many interfaces to be emulated
- I generally spend way too much time setting up a lab to recreate a problem, instead of actually trying to solve the problem

At a high level the script does the following to address this
- Takes an input of a directory of network configurations
- With the help of CiscoConfParse, Parses through the configs to find all layer 3 interfaces, no matter the identifier or quantity (FastEthernet, GigabitEthernet, etc)
- Finds common subnets within all configs and assigns them to a unique vlan ID
- Assigns another unique vlan ID to all other layer 3 interfaces without any peers on the lan segment
- Converts and replaces all interfaces with GigabitEthernet1.X, where X is the unique vlan ID
- Creates a vars.tfvars.json and main.tf file that use Cisco DevNet's CML provider to generate a deployable lab configuration

running python prod_to_cml.py present a cli tool using the Click library. 