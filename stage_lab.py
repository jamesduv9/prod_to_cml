import converter
import click
import sys
import logging
from pprint import pprint


@click.group(name="main")
def main():
    pass


@click.command(name="create_configs")
@click.option(
    "--source_path",
    help="path to your configuration directory you want to convert",
    default="./",
)
@click.option(
    "--output_path",
    help="Mandatory: Provide the destination directory for the configs, interface mapping, and tfvars json file. Cannot equal source_path",
    required=True,
)
@click.option(
    "--vlan_seed",
    help="Which vlan to start incrementing at, avoid setting too high. Must be greater than 1",
    default=2,
)
@click.option(
    "--config_file_ext",
    help="Tells the script which file extension your configs will use inside the source_path directory",
    default=".config",
)
def create_configs(
    source_path: str, output_path: str, vlan_seed: str, config_file_ext: str
) -> None:
    """
    Takes your passed in directory of configurations with various interfaces, maps them all to individual GigabitEthernet1.X subinterfaces. Provides a quick way to deploy these configurations to a CML lab through terraform
    """
    if output_path == source_path:
        logging.warning(
            "Please provide a unique directory to create for the output files. Hint: Cannot be the same as config source directory"
        )
        sys.exit()
    if vlan_seed <= 1:
        logging.warning("The vlan seed cannot be less than 2.")
        sys.exit()
    conv = converter.Converter(
        source_path=source_path,
        output_path=output_path,
        vlan_seed=vlan_seed,
        config_file_ext=config_file_ext,
    )

    # load all files with specified extension
    conv.load_configs()

    # parse out all l3 interfaces in the config files
    for config in conv.configs:
        config.get_l3_interfaces()

    # Finds common subnets and assigns vlanids
    conv.subnet_compare()

    # replaces the old configuration interfaces with new subintf
    conv.replace_in_configs()
    for config in conv.configs:
        config.create_interface_mapping()

    # Builds the interface mapping to show old vs new
    conv.save_interface_mapping()

    # Creates main.tf and vars.tfvars.json in the destination path
    conv.create_tf_files()


if __name__ == "__main__":
    main.add_command(create_configs)
    main()
