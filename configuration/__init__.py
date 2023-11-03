import ipaddress
import re
from ciscoconfparse import CiscoConfParse


class Configuration:
    def __init__(self, file_: str, file_path: str) -> None:
        self.file_path = file_path
        self.file_ = file_
        self.l3_interfaces = []
        self.new_configuration = str()
        self.current_parsed_config = str()
        self.interface_mapping = dict()
        self.hostname = str()

    def get_current_config(self) -> None:
        """
        Turn the current network configuration into a parsed CiscoConfParse Object
        """
        self.current_parsed_config = CiscoConfParse(self.file_path)

    def get_hostname(self) -> None:
        """
        Look at current config and find hostname
        """
        hn = self.current_parsed_config.find_lines("hostname")
        if hn:
            hn_line = hn[0]
            self.hostname = hn_line.split(" ")[1]

    def get_l3_interfaces(self) -> None:
        """
        Parses through the config to find existing layer 3 interfaces
        Retrieves the Primary IP and will use that in the future for comparison
        Appends a dictionary to the l3_interfaces array
        """
        interfaces = self.current_parsed_config.find_lines("^int(erface) (Gi|Fa|Se|Te|Tw|Eth|Fo|Vlan|BDI|Po)")
        for interface in interfaces:
            ip_config = self.current_parsed_config.find_children_w_parents(
                f"^{interface}$",
                "ip address \d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3} \d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",
            )
            # if we do not find an ip address on the interface, go to the next iteration
            if ip_config:
                ip_addr = ip_config[0]
            else:
                continue

            int_dict = {
                "config": self.file_path,
                "if_name": re.search("interface (.*)", interface).group(1),
                "ip_subnet": self._build_ip_network(ip_addr),
                "ip_address": self._build_ip_addr(ip_addr),
            }
            self.l3_interfaces.append(int_dict)

    def create_interface_mapping(self) -> None:
        """
        Look at the current Configurations and determine 1:1 old intf to subintf mapping
        """   
        retdict = dict()
        for config in self.l3_interfaces:
            retdict[config['if_name']] = config['new_if_name']
        
        self.interface_mapping = retdict


    @staticmethod
    def _build_ip_addr(ip: str) -> ipaddress.IPv4Address:
        """
        helper function to take a ip address and convert it to a IPv4Address Object
        """
        ip = re.search("\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", ip).group(0)
        return ipaddress.IPv4Address(ip)

    @staticmethod
    def _build_ip_network(ip: str) -> ipaddress.IPv4Network:
        """
        helper function to take a create a network from the cisco router ip address format
        """
        ip = ip.split("ip address")[1]
        ip = ip.strip()
        ip = ip.split(" ")
        ip = "/".join(ip)
        return ipaddress.IPv4Network(ip, strict=False)
    
    def __str__(self):
        return str(self.l3_interfaces)
