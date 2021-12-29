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


def create_list_node():
    execs = []
    new_node_oid = {}
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
                            new_node_oid.clear()

                            # get index exec
                            ind_exec = line.split("=").pop(0)[-2]
                            new_node_oid["exec"] = ind_exec
                            sep = oid_file + ".@exec[" + ind_exec + "]."
                            for line in result.stdout.split("\n"):
                                param_node = line.split(sep)
                                if len(param_node) == 2:
                                    sect_opt = param_node[1].split("=")
                                    new_node_oid[sect_opt[0]] = sect_opt[1].replace("'", "")

                            execs.append(new_node_oid.copy())

    return execs


def create_list_exec_snmpd():
    list_exec_snmpd = []
    try:
        confvalues = ubus.call("uci", "get", {"config": "snmpd"})
    except RuntimeError:
        journal.WriteLog("OWRT-snmp-agent", "Normal", "err",
                         "create_list_exec_snmpd() error get " + snmpd_agent)
        exit_prog(-1)

    for confdict in list(confvalues[0]['values'].values()):
        if confdict['.type'] == "exec":
            list_exec_snmpd.append(confdict.copy())

    return list_exec_snmpd


def diff_netping_snmpd_exec(netping_exec, snmpd_exec):
    for key, value in netping_exec.items():
        if key == "exec":
            continue
        try:
            if value == snmpd_exec[key]:
                continue
            else:
                return True
        except KeyError:
            # nodes diff
            return True

    for key, value in snmpd_exec.items():
        if key.startswith('.'):
            continue
        try:
            if value == netping_exec[key]:
                continue
            else:
                return True
        except KeyError:
            # nodes diff
            return True

    return False


def node_to_snmpd(node):
    fl_change = False
    for key, value in node.items():
        if key == 'exec':
            try:
                run(['uci', 'add', 'snmpd', 'exec'],
                    capture_output=True, check=True, encoding='utf-8')
                fl_change = True
            except CalledProcessError as e:
                journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "ERROR add section " + e.stderr)
                exit_prog(-1)
        elif fl_change:
            str_param = "snmpd.@exec[-1]." + key + "=" + value
            try:
                run(['uci', 'set', str_param],
                    capture_output=True, check=True, encoding='utf-8')
            except CalledProcessError as e:
                journal.WriteLog("OWRT-snmp-agent", "Normal", "err",
                                 "ERROR add option " + e.stderr)
                exit_prog(-1)

    if fl_change:
        try:
            run(['uci', 'commit', 'snmpd'])
        except CalledProcessError as e:
            journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "ERROR commit snmpd " + e.stderr)
            exit_prog(-1)

        run(['/etc/init.d/snmpd', 'restart'])


def update_snmpd_exec(netping_exec, snmpd_exec_name):
    ubus.call("uci", "delete", {"config": "snmpd", "section": snmpd_exec_name})
    ubus.call("uci", "commit", {"config": "snmpd"})
    node_to_snmpd(netping_exec)


def change_config_snmpd(list_exec):
    list_exec_snmpd = create_list_exec_snmpd()
    for netping_exec in list_exec:
        fl_search = False
        for snmpd_exec in list_exec_snmpd:
            try:
                if netping_exec['miboid'] != snmpd_exec['miboid']:
                    continue
            except KeyError:
                continue

            # node found in config snmpd
            fl_search = True
            if diff_netping_snmpd_exec(netping_exec, snmpd_exec):
                update_snmpd_exec(netping_exec, snmpd_exec['.name'])
            break

        if not fl_search:
            # add node snmp to snmpd
            node_to_snmpd(netping_exec)


if __name__ == '__main__':
    journal.WriteLog("OWRT-snmp-agent", "Normal", "notice", "Start module!")

    if not os.path.exists(snmpd_agent):
        journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "ERROR snmpd agent not installed")
        sys.exit(-1)

    if not ubus.connect("/var/run/ubus.sock"):
        journal.WriteLog("OWRT-snmp-agent", "Normal", "err", "Failed connect to ubus")
        sys.exit(-1)

    execs = create_list_node()
    change_config_snmpd(execs)

    journal.WriteLog("OWRT-snmp-agent", "Normal", "notice", "Success finish module")
    exit_prog(0)
