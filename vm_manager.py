#!/usr/bin/python27
# -*- coding: utf-8 -*-
from pyvim.connect import SmartConnectNoSSL, Disconnect  # pyvim 2.0.21
from pyVmomi import vim  # pyVmomi 6.7.1
import yaml  # PyYaml 5.4.1
import os
import time
import warnings

current_dir = os.path.dirname(os.path.abspath(__file__)) + "\\"

# json file with all required data
json_config_name = "vmManagerConfig.json"
json_config_path = current_dir + json_config_name


def get_json_vcenter_data(json_file_path):
    """
    Get vCenter connection info
    :param json_file_path: str: full path to json
    :return: str: host_name, str: username, str: password
    """
    with open(json_file_path, "r") as f:
        data = yaml.load(f)
    f.close()

    # params for vCenter connection
    vcenter_host = data["vcenter_data"]["hostname"]
    vcenter_user = data["vcenter_data"]["user"]
    vcenter_password = data["vcenter_data"]["password"]
    return vcenter_host, vcenter_user, vcenter_password


def get_input_vms(data_json):
    """
    Get all required data about VMs (including excluded VMs)
    :param data_json: str: full path to json
    :return: dict: VM's names as keys, VM's power statuses as values
    """
    with open(data_json, "r") as f:
        data = yaml.load(f)
    f.close()

    vm_dict = {}

    for vm_name, vm_status in data["vm_info"].items():
        if vm_name not in data["excludes"]:
            vm_dict[vm_name] = vm_status
        else:
            print("Machine " + vm_name + " is excluded.")
    return vm_dict


def main(json_file):
    """
    Manage VM's by names from json file to turn them on/off
    :param json_file: str: full path to json
    """

    # ignore warnings (especially yaml warnings)
    warnings.filterwarnings("ignore")

    # get required vCenter data
    v_host, v_user, v_pass = get_json_vcenter_data(json_file)
    # connect to vCenter for access
    si = SmartConnectNoSSL(host=v_host, user=v_user, pwd=v_pass)
    content = si.RetrieveContent()

    # get VM's data
    vm_dict = get_input_vms(json_file)

    # get all current available VM's from vCenter
    vmview = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)

    # for all VM's from json
    for vm_name, vm_status in vm_dict.items():
        # check if available in vCenter
        res = [vm for vm in vmview.view if vm_name == vm.name]
        if res:
            vm = res[0]
            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOff and vm_status == "on":
                print("Machine " + vm_name + " gets power on signal.")
                task = vm.PowerOn()
                while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
                    time.sleep(1)
                print("Machine " + vm_name + " turned on.")
            elif vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn and vm_status == "on":
                print("Machine " + vm_name + " is already turned on.")
            elif vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn and vm_status == "off":
                print("Machine " + vm_name + " gets shutdown signal.")
                task = vm.ShutdownGuest()
                print("Machine " + vm_name + " should be turned off.")
            elif vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOff and vm_status == "off":
                print("Machine " + vm_name + " is already turned off.")
        else:
            print("Virtual machine " + vm_name + " wasn't found.")
    # release resources
    vmview.Destroy()

    # disconnect from vCenter
    Disconnect(si)


if __name__ == '__main__':
    try:
        main(json_config_path)
    except Exception as e:
        print(e.args)
