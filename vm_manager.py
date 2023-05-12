#!/usr/bin/python27
# -*- coding: utf-8 -*-
from pyvim.connect import SmartConnectNoSSL, Disconnect  # pyvim 2.0.21
from pyVmomi import vim  # pyVmomi 6.7.1
import yaml  # PyYaml 5.4.1
import os
import time
import warnings
import logging
import tempfile

# log file in TEMP folder
log_path = tempfile.gettempdir()
log = "vm_manager.log"
full_log_path = os.path.join(log_path, log)

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


def get_input_vms(data_json, log_file):
    """
    Get all required data about VMs (including excluded VMs)
    :param log_file: str: full path to log (TEMP)
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
            make_log(log_file, lev=logging.INFO, info="Machine " + vm_name + " is excluded.")
            # print("Machine " + vm_name + " is excluded.")
    return vm_dict


def make_log(log_file, lev=None, error="", info="", warning=""):
    logger = logging.getLogger("vm_manager")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        file_handler = logging.FileHandler(log_file, mode="a")
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s|%(levelname)s|%(message)s', datefmt='%d-%m-%Y %H:%M:%S')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if lev == logging.INFO:
        logger.info(info)
    elif lev == logging.ERROR:
        logger.error(error)
    elif lev == logging.WARNING:
        logger.warning(warning)


def main(json_file, log_file):
    """
    Manage VM's by names from json file to turn them on/off
    :param log_file: str: full path to log (TEMP)
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
    vm_dict = get_input_vms(json_file, log_file)

    # get all current available VM's from vCenter
    vmview = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)

    # for all VM's from json
    for vm_name, vm_status in vm_dict.items():
        # check if available in vCenter
        res = [vm for vm in vmview.view if vm_name == vm.name]
        if res:
            vm = res[0]
            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOff and vm_status == "on":
                make_log(log_file, lev=logging.INFO, info="Machine " + vm_name + " gets power on signal.")

                task = vm.PowerOn()

                if task:
                    while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
                        time.sleep(1)
                    if task.info.state == vim.TaskInfo.State.success:
                        make_log(log_file, lev=logging.INFO, info="Machine " + vm_name + " powered on.")
                    elif vim.TaskInfo.State.error:
                        make_log(log_file, lev=logging.ERROR, error=str(task.info.error) + " for " + vm_name + " machine.")
                    else:
                        make_log(log_file, lev=logging.ERROR, error="Unexpected behavior for " + vm_name + " machine while powering on.")
                else:
                    make_log(log_file, lev=logging.ERROR, error="Cannot create task for " + vm_name + " machine.")

            elif vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn and vm_status == "on":
                make_log(log_file, lev=logging.INFO, info="Machine " + vm_name + " is already powered on.")

            elif vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn and vm_status == "off":
                make_log(log_file, lev=logging.INFO, info="Machine " + vm_name + " gets shutdown signal.")

                # nice mode
                task = vm.ShutdownGuest()
                # hard mode
                # task = vm.PowerOff()

                if task:
                    while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
                        time.sleep(1)
                    if task.info.state == vim.TaskInfo.State.success:
                        make_log(log_file, lev=logging.INFO, info="Machine " + vm_name + " powered off.")
                    elif vim.TaskInfo.State.error:
                        make_log(log_file, lev=logging.ERROR, error=str(task.info.error) + " for " + vm_name + " machine.")
                    else:
                        make_log(log_file, lev=logging.ERROR, error="Unexpected behavior for " + vm_name + " machine while powering off.")
                else:
                    make_log(log_file, lev=logging.ERROR, error="Cannot create task for " + vm_name + " machine.")

            elif vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOff and vm_status == "off":
                make_log(log_file, lev=logging.INFO, info="Machine " + vm_name + " is already powered off.")

        else:
            print("Virtual machine " + vm_name + " wasn't found.")
    # release resources
    vmview.Destroy()

    # disconnect from vCenter
    Disconnect(si)


if __name__ == '__main__':
    try:
        main(json_config_path, full_log_path)
    except Exception as e:
        make_log(log_file, lev=logging.ERROR, error=str(e.args))
