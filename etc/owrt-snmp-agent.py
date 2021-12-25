#!/usr/bin/env python3

import os
import sys
from journal import journal
from subprocess import run, CalledProcessError

try:
    import ubus
except ImportError:
    journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "Failed import ubus.")
    sys.exit(-1)

snmpd_agent = "/etc/config/snmpd"
search_folder = "/etc/"
prefix = "netping_"
oid_folder = "/snmp_oid/"
oid_file = "nodes_oid"

def exit_prog(ret_val):
    ubus.disconnect()
    sys.exit(ret_val)

if __name__ == '__main__':
    change_config_snmpd = False
    journal.WriteLog("OWRT-snmp-agent", "Normal", "notice", "Start module!")

    if not os.path.exists(snmpd_agent):
        journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "ERROR snmpd agent not installed")
        sys.exit(-1)

    if not ubus.connect("/var/run/ubus.sock"):
        journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "Failed connect to ubus")
        sys.exit(-1)

    for file in os.listdir(search_folder):
        # Search netping_* modules
        if not file.startswith(prefix) or not os.path.isdir(search_folder + file):
            continue

        oid_path = search_folder + file + oid_folder
        if os.path.exists(oid_path) and os.path.isdir(oid_path):
            oid_lst = oid_path + oid_file
            if os.path.exists(oid_lst) and os.path.isfile(oid_lst):
                try:
                    result = run(['uci', '-c', oid_path, 'show', oid_file],
                                 capture_output=True, check=True, encoding='utf-8')
                except CalledProcessError as e:
                    journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "ERROR get entry " + oid_lst)
                    continue

                # parsing files resources modules for add to snmpd agent
                for line in result.stdout.split("\n"):
                    if line:
                        if line.split("=").pop(1) == "exec":
                            try:
                                run(['uci', 'add', 'snmpd', 'exec'],
                                    capture_output=True, check=True, encoding='utf-8')
                                change_config_snmpd = True
                            except CalledProcessError as e:
                                journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "ERROR add section " + e.stderr)
                                exit_prog(-1)

                            ind_exec = line.split("=").pop(0)[-2]
                            sep = oid_file + ".@exec[" + ind_exec + "]."
                            for line in result.stdout.split("\n"):
                                param_node = line.split(sep)
                                if len(param_node) == 2:
                                    str_param = "snmpd.@exec[-1]." + param_node[1].replace("'", "")

                                    try:
                                        run(['uci', 'set', str_param],
                                            capture_output=True, check=True, encoding='utf-8')
                                    except CalledProcessError as e:
                                        journal.WriteLog("OWRT-snmp-agent", "Normal", "err",
                                                         "ERROR add option " + e.stderr)
                                        exit_prog(-1)
                            try:
                                run(['uci', 'commit', 'snmpd'])
                            except CalledProcessError as e:
                                journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "ERROR commit snmpd " + e.stderr)
                                exit_prog(-1)

    if change_config_snmpd == True:
        run(['/etc/init.d/snmpd', 'restart'])

    journal.WriteLog("OWRT-snmp-agent", "Normal", "notice", "Success finish module")
    exit_prog(0)
