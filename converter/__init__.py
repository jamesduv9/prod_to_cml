
import os
import re
import logging
import json
from configuration import Configuration
from pprint import pprint
from typing import Dict, List
from .constants import *


class Converter:
    def __init__(
        self,
        source_path: str,
        configs: List[object] = None,
        config_file_ext: str = ".config",
        vlan_seed: int = 2,
        output_path: str = "",
    ) -> None:
        if configs is None:
            self.configs = []
        else:
            self.configs = configs
        self.source_path = source_path
        self.config_file_ext = config_file_ext
        self.vlan_seed = vlan_seed
        self.output_path = output_path
        try:
            os.mkdir(self.output_path)
        except FileExistsError:
            logging.info("Output folder already exists")
            pass

    def load_configs(self) -> None:
        """
        With self.source_path, open all configurations and build the config classes associated with each.
        """
        for file_ in os.listdir(self.source_path):
            if file_.endswith(self.config_file_ext) and "NEW" not in file_:
                self.configs.append(
                    Configuration(
                        file_=file_, file_path=os.path.join(self.source_path, file_)
                    )
                )

    def save_interface_mapping(self) -> None:
        """
        Saves the interface mapping to an output file
        """
        overall_mapping = {"devices": {}}
        for config in self.configs:
            overall_mapping["devices"][config.hostname] = config.interface_mapping
        
        self.save_output(file_=f"overall_interface_map.json", save_me=overall_mapping, type_="json")


    def create_tf_files(self) -> None:
        """
        Create the tfiles file that we can reference with our terraform file
        """
        tf_var_template = TFVARS_SKELETON
        for idx, config in enumerate(self.configs):
            working_dict = {}
            working_dict['nodedefinition'] = "csr1000v"
            working_dict['x'], working_dict['y'] = self._calculate_coords(idx + 1)
            working_dict['config_file'] = f"LAB-{config.file_}"
            working_dict['label'] = config.file_

            tf_var_template['nodes'].append(working_dict)
        
        self.save_output(file_=f"vars.tfvars.json", save_me=tf_var_template, type_="json")
        self.save_output(file_="main.tf", save_me=TF_FILE, type_="hcl")

    @staticmethod
    def _calculate_coords(idx):
        """
        Structured way to place the nodes in a pattern around the bridge at (450,450)
        """
        if idx < 15:
            return idx * 100, 0
        else:
            idx = idx - 15
            return idx * 100, 900


        
    def save_output(self, file_: str, save_me, type_="config") -> None:
        """
        Save the configuration to the provided destination path
        """
        if type_ == "config":
            with open(f"{self.output_path}/{file_}", "w") as opened_file:
                final_config = INT_AUTO_NOSHUT + AAA_COMMANDS + ''.join(save_me)
                opened_file.write(final_config)
        
        elif type_ == "json":
            with open(f"{self.output_path}/{file_}", "w") as opened_file:
                final_map = json.dumps(save_me, indent=2)
                opened_file.write(final_map)

        elif type_ == "hcl":
            with open(f"{self.output_path}/{file_}", "w") as opened_file:
                opened_file.write(save_me)

    def subnet_compare(self) -> None:
        """
        Group interfaces by their subnets across all configurations and add appropriate vlan ids
        even I can tell this is O(n^2), surely ways to improve
        """
        all_interfaces = [intf for config in self.configs for intf in config.l3_interfaces]
        processed_ip_addresses = set()

        for interface in all_interfaces:
            if interface["ip_address"] in processed_ip_addresses:
                continue

            #Get all interfaces within the current interface's lan segment
            matched_interfaces = [intf for intf in all_interfaces if intf["ip_address"] in interface["ip_subnet"] and intf != interface]

            # If there are any interfaces in the same lan segment
            # Choose an unique vlan ID
            if matched_interfaces:
                interface["new_vlanid"] = self.vlan_seed
                interface["new_if_name"] = f"GigabitEthernet1.{self.vlan_seed}"
                logging.info(f"Interface {interface['if_name']} is being assigned to new interface GigabitEthernet1.{self.vlan_seed}")
                # Set every matched interface to the same vlan id on same subintf
                for matched_intf in matched_interfaces:
                    matched_intf["new_vlanid"] = self.vlan_seed
                    matched_intf["new_if_name"] = f"GigabitEthernet1.{self.vlan_seed}"
                    logging.info(f"Interface {matched_intf['if_name']} is being assigned to new interface GigabitEthernet1.{self.vlan_seed}")
                    processed_ip_addresses.add(matched_intf["ip_address"])

                self.vlan_seed += 1
                processed_ip_addresses.add(interface["ip_address"])

            # If the interface is lonely in it's own lan segment, still give it an unique vlanid
            else:
                interface["new_vlanid"] = self.vlan_seed
                interface["new_if_name"] = f"GigabitEthernet1.{self.vlan_seed}"
                logging.info(f"Interface {interface['if_name']} is being assigned to new interface GigabitEthernet1.{self.vlan_seed}")
                self.vlan_seed += 1
                processed_ip_addresses.add(interface["ip_address"])

    def replace_in_configs(self) -> None:
        """
        Make new configurations from the old and place them in an output directory
        """
        for configuration in self.configs:
            config_interfaces = [config for config in configuration.l3_interfaces]
            new_config = self._replace_interfaces(configuration, config_interfaces)
            new_config = self._remove_bad_words(new_config)
            new_config = self._add_encap(new_config, config_interfaces)

            self.save_output(file_=f"LAB-{configuration.file_}", save_me=new_config, type_="config")
            configuration.new_configuration = new_config

    
    def _remove_bad_words(self, new_config: List) -> List:
        """
        compares each config line with the list of bad_words. Removes them
        """
        for line in new_config:
            if any(bad_word in line for bad_word in BAD_WORDS):
                new_config.remove(line)
        
        return new_config


    def _add_encap(self, new_config: List, config_interfaces: List[Dict]) -> List:
        """
        With the new configuration, go through and remove all previous instances of "encapsulation" and replace it with the correct vlan encap
        """
        i = 0
        while i < len(new_config):
            line = new_config[i]
            if "encapsulation" in line:
                new_config.remove(line)
                continue  # because we removed a line, continue the loop without incrementing the index
            match = re.search(f"^interface {ALL_INTERFACE_FLAVORS_REGEX}$", line)
            if match:
                for interface in config_interfaces:
                    if f"interface {interface['new_if_name']}" == match.group(0):
                        new_config[
                            i
                        ] += f" encapsulation dot1q {interface['new_vlanid']}\n"  # Modify the actual line in the list
            i += 1
        return new_config

    @staticmethod
    def _replace_interfaces(
        configuration: object, config_interfaces: List[Dict]
    ) -> List:
        """
        Parse through the device configuration and replace the interface IDs with the new addresses
        """
        new_config = []
        with open(configuration.file_path, "r") as file_:
            for line in file_.readlines():
                config_flag = False
                match = re.search(ALL_INTERFACE_FLAVORS_REGEX, line)
                if match:
                    for interface in config_interfaces:
                        if interface["if_name"] == match.group():
                            new_config.append(
                                line.replace(match.group(), interface["new_if_name"])
                                
                            )
                            config_flag = True
                            break
                if not config_flag:
                    new_config.append(line)
        
        return new_config


