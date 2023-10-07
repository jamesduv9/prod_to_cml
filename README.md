# prod_to_cml
The goal of this script is to take production Cisco IOS/IOSXE configurations and have them deployed in a CML lab as CSR1000vs using Terraform. This repo could also be used for the early stages of a CI/CD pipeline or quickly throwing together educational material. 

## Why?
prod_to_cml attempts to solve these shortcomings I've found with labbing production network configurations:
- Interface IDs rarely ever match (Virtual appliances use different interface schemes completely)
- Virtual appliances only support a max of 26 interfaces. Meaning you could have devices in your topology that simply have too many interfaces to be properly emulated
- We generally spend too much time setting up a lab to recreate a problem, instead of actually solving a problem

## How It Works
At a high level the script does the following to address this:
- Takes an input directory of network configurations
- With the help of CiscoConfParse, Parses through the configs to find all layer 3 interfaces, no matter the identifier or quantity (FastEthernet, GigabitEthernet, etc)
- Finds common subnets within all configs and assigns them to a unique vlan ID
- Assigns another unique vlan ID to all other layer 3 interfaces without any peers on their lan segment
- Converts and replaces all found layer 3 interfaces with GigabitEthernet1.X, where X is the unique vlan ID
- Creates a vars.tfvars.json and main.tf file that use Cisco DevNet's CML provider to generate a deployable lab 

## Usage
running ```python prod_to_cml.py``` presents a cli tool using the Click library. the only command currently is ```create_configs```
```
> python3 prod_to_cml.py create_configs --help
Usage: prod_to_cml.py create_configs [OPTIONS]

  Takes your passed in directory of configurations with various interfaces,
  maps them all to individual GigabitEthernet1.X subinterfaces. Provides a
  quick way to deploy these configurations to a CML lab through terraform

Options:
  --source_path TEXT      MANDATORY: path to your configuration directory you
                          want to convert  [required]
  --output_path TEXT      MANDATORY: Provide the destination directory for the
                          configs, interface mapping, and tfvars json file.
                          Cannot equal source_path  [required]
  --vlan_seed INTEGER     OPTIONAL: Which vlan to start incrementing at, avoid
                          setting too high. Must be greater than 1
  --config_file_ext TEXT  OPTIONAL: Tells the script which file extension your
                          configs will use inside the source_path directory
  --help                  Show this message and exit.
```

By default the optional options ```vlan_seed``` and ```config_file_ext``` are set to 2 and ".config" respectively. 

You can then run the script by passing it a directory of configurations you want to convert, along with an output directory. In this example I also have my configurations stored as .txt files, and I want to start with a vlan seed of 5

```
> python3 prod_to_cml.py create_configs --source_path example_source/ --output_path example_output --config_file_ext ".txt" --vlan_seed
 5
```

And then inspecting the output directory ./example_output

```
> tree example_output/
example_output/
├── LAB-hub77.txt                               <------ Converted hub77 config
├── LAB-hub78.txt
├── LAB-spoke.txt
├── LAB-transport_router.txt
├── hub77.txt-interface_map.json                <------ hub77 old to new interface mappings
├── hub78.txt-interface_map.json
├── main.tf                                     <------ prebuilt teraform hcl file for CML deployment
├── spoke.txt-interface_map.json
├── transport_router.txt-interface_map.json
└── vars.tfvars.json                            <------ Generated tfvars files to make your new configurations plugable into main.tf

0 directories, 10 files

```
## Deployment Using Terraform
We now have everything we need to deploy the lab in CML via terraform. The main.tf accepts four important variables, cml_lab_name, cml_username, cml_password, and cml_url. You can either set these as environmental variables (TF_VAR_*) before applying or manually answer the prompt at runtime. In this example I'll set them at runtime. 

I'll now going to change directories into the output folder, initiate terraform, apply our terraform plan. This should deploy the complete lab

```
> cd example_output
> terraform init
    --- output omitted ---
> terraform apply -var-file vars.tfvars.json
var.cml_lab_name
  Name of the lab we will create in CML

  Enter a value: some-lab

var.cml_password
  password for your CML Instance

  Enter a value: ****           

var.cml_url
  path to your cml node ex: https://192.168.1.247

  Enter a value: https://192.168.1.247

var.cml_username
  Username for your CML Instance

  Enter a value: jamesduv9

    --- output omitted ---

cml2_lifecycle.start_nodes: Creation complete after 2m51s [id=624b8ca8-a874-47be-9eb6-60d6d21d8327]

Apply complete! Resources: 11 added, 0 changed, 0 destroyed.

Outputs:

outs = "91058e49-6afb-4d5a-a529-b791e606a23d"
```

The Terraform deployment can take 5-10 minutes depends on how many nodes you are running, it doesn't complete until all nodes return with status "STARTED". After that you should have a new CML lab with the name you provided, built out with your configs. 

## Important Notes
- The script removes all aaa commands and credentials and replaces the with admin:admin (username:password)
- The script appends an EEM script to the start of the CSRv configuration to automatically no shut GigabitEthernet1



